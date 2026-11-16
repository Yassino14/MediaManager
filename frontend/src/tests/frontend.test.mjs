import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateMediaUrlClient,
  parseBatchUrlLines,
  estimateConvertedSizeBytes,
  formatBytes,
  formatDuration,
} from '../utils/validation.mjs';

test('validateMediaUrlClient accepts valid HTTP/HTTPS media URLs', () => {
  const r1 = validateMediaUrlClient('https://www.youtube.com/watch?v=aqz-KE-bpKQ');
  assert.equal(r1.valid, true);
  assert.equal(r1.error, null);

  const r2 = validateMediaUrlClient('http://vimeo.com/8921234');
  assert.equal(r2.valid, true);
});

test('validateMediaUrlClient rejects unsafe schemes and private network addresses', () => {
  const blocked = [
    'file:///C:/Windows/System32/cmd.exe',
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'http://localhost:8000/api/settings',
    'http://127.0.0.1:5173',
    'http://192.168.1.50/stream.mp4',
    'http://10.0.0.1/internal',
    'http://172.20.0.4/video',
    'http://nas.local/movie.mkv',
  ];
  for (const url of blocked) {
    const res = validateMediaUrlClient(url);
    assert.equal(res.valid, false, `Expected ${url} to be rejected`);
    assert.ok(res.error && res.error.length > 0);
  }
});

test('parseBatchUrlLines splits multiline input, ignores comments, and validates each line', () => {
  const input = `
    # Authorized Creative Commons streams
    https://www.youtube.com/watch?v=aqz-KE-bpKQ
    http://192.168.1.1/private.mp4
    https://archive.org/details/BigBuckBunny_124
  `;
  const parsed = parseBatchUrlLines(input);
  assert.equal(parsed.length, 3);
  assert.equal(parsed[0].valid, true);
  assert.equal(parsed[1].valid, false);
  assert.equal(parsed[2].valid, true);
});

test('estimateConvertedSizeBytes computes expected compression and bitrate estimates', () => {
  // 60 sec audio at 192 kbps -> ~1,440,000 bytes
  const audioSize = estimateConvertedSizeBytes(20_000_000, 60, null, 192);
  assert.equal(audioSize, 1440000);

  // Higher CRF (28) produces smaller estimated output than lower CRF (18)
  const highQuality = estimateConvertedSizeBytes(50_000_000, 120, 18, null);
  const compressed = estimateConvertedSizeBytes(50_000_000, 120, 28, null);
  assert.ok(compressed < highQuality);
});

test('formatBytes and formatDuration format display strings accurately', () => {
  assert.equal(formatBytes(0), '0 B');
  assert.equal(formatBytes(1048576), '1.0 MB');
  assert.equal(formatDuration(125), '2:05');
  assert.equal(formatDuration(3665), '1:01:05');
});
