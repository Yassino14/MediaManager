const PRIVATE_SUFFIXES = [
  '.localhost',
  '.local',
  '.internal',
  '.intranet',
  '.lan',
  '.home.arpa',
];

export function validateMediaUrlClient(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string' || !rawUrl.trim()) {
    return { valid: false, url: '', error: 'URL cannot be empty.' };
  }
  const trimmed = rawUrl.trim();
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { valid: false, url: trimmed, error: 'Malformed URL format.' };
  }
  const protocol = (parsed.protocol || '').toLowerCase();
  if (protocol !== 'http:' && protocol !== 'https:') {
    return {
      valid: false,
      url: trimmed,
      error: `Unsupported scheme '${protocol.replace(':', '')}'. Only http:// and https:// are permitted.`,
    };
  }
  const host = (parsed.hostname || '').toLowerCase().replace(/\.$/, '');
  if (!host) {
    return { valid: false, url: trimmed, error: 'Missing hostname.' };
  }
  if (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '0.0.0.0' ||
    host === '::1' ||
    host === '[::1]' ||
    PRIVATE_SUFFIXES.some((s) => host.endsWith(s))
  ) {
    return {
      valid: false,
      url: trimmed,
      error: `Local or private host '${host}' is blocked for security.`,
    };
  }
  // Check IPv4 private ranges
  const ipv4Match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (ipv4Match) {
    const [a, b] = [Number(ipv4Match[1]), Number(ipv4Match[2])];
    if (
      a === 10 ||
      a === 127 ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      (a === 169 && b === 254)
    ) {
      return {
        valid: false,
        url: trimmed,
        error: `Private network IP '${host}' is restricted.`,
      };
    }
  } else if (!host.includes('.')) {
    return {
      valid: false,
      url: trimmed,
      error: `Single-label internal host '${host}' is not allowed.`,
    };
  }
  return { valid: true, url: trimmed, error: null };
}

export function parseBatchUrlLines(multilineText) {
  if (!multilineText || typeof multilineText !== 'string') return [];
  return multilineText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('#'))
    .map((line) => validateMediaUrlClient(line));
}

export function estimateConvertedSizeBytes(sourceBytes, durationSec, crf, targetAudioKbps) {
  if (durationSec && durationSec > 0 && targetAudioKbps && !crf) {
    return Math.max(1024, Math.round((targetAudioKbps * 1000 / 8) * durationSec));
  }
  if (typeof crf === 'number') {
    const factor = Math.pow(2, (23 - crf) / 6.0);
    const clamped = Math.min(1.5, Math.max(0.18, 0.65 * factor));
    return Math.max(1024, Math.round(sourceBytes * clamped));
  }
  return Math.max(1024, Math.round(sourceBytes * 0.75));
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return '—';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${mins}:${String(secs).padStart(2, '0')}`;
}
