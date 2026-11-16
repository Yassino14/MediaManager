import React, { useState } from 'react';
import { Music } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, MediaFileItem } from '../types';

export const AudioConverterPage: React.FC<{
  files: MediaFileItem[];
  settings: AppSettings;
  onRefresh: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ files, settings, onRefresh, onSuccess, onError }) => {
  const [sourcePath, setSourcePath] = useState('');
  const [outputFormat, setOutputFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [sampleRate, setSampleRate] = useState(44100);
  const [channels, setChannels] = useState(2);

  const handleConvert = async () => {
    if (!sourcePath) {
      onError('Select an audio file first.');
      return;
    }
    try {
      await api.enqueueAudioConvert({
        source_path: sourcePath,
        output_format: outputFormat,
        bitrate,
        sample_rate: sampleRate,
        channels,
        output_dir: settings.conversion_dir,
        duplicate_policy: settings.duplicate_handling,
      });
      onRefresh();
      onSuccess('Audio conversion job queued.');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Audio conversion failed');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Audio Format Converter</h1>
        <p className="text-sm text-zinc-400">
          Convert audio files across MP3, WAV, FLAC, AAC, M4A, OGG, and OPUS.
        </p>
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Source File</label>
            <select
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="">-- Select media file --</option>
              {files.map((f) => (
                <option key={f.path} value={f.path}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Output Format</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="mp3">MP3</option>
              <option value="wav">WAV</option>
              <option value="flac">FLAC</option>
              <option value="aac">AAC</option>
              <option value="m4a">M4A</option>
              <option value="ogg">OGG</option>
              <option value="opus">OPUS</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Bitrate</label>
            <select
              value={bitrate}
              onChange={(e) => setBitrate(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="128k">128 kbps</option>
              <option value="192k">192 kbps</option>
              <option value="256k">256 kbps</option>
              <option value="320k">320 kbps</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Channels</label>
            <select
              value={channels}
              onChange={(e) => setChannels(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value={2}>Stereo (2.0)</option>
              <option value={1}>Mono (1.0)</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleConvert}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2"
          >
            <Music className="w-4 h-4" /> Convert Audio
          </button>
        </div>
      </div>
    </div>
  );
};
