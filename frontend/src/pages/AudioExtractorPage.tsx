import React, { useState } from 'react';
import { FileAudio, Upload } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, MediaFileItem } from '../types';

export const AudioExtractorPage: React.FC<{
  files: MediaFileItem[];
  settings: AppSettings;
  onRefresh: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ files, settings, onRefresh, onSuccess, onError }) => {
  const [sourcePath, setSourcePath] = useState('');
  const [outputFormat, setOutputFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('320k');
  const [sampleRate, setSampleRate] = useState(44100);
  const [audioQuality, setAudioQuality] = useState(2);
  const [outputFilename, setOutputFilename] = useState('');
  const [removeOriginal, setRemoveOriginal] = useState(false);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const uploaded = await api.uploadLocalFile(file);
      setSourcePath(uploaded.path);
      onRefresh();
      onSuccess(`Loaded local file: ${uploaded.filename}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleExtract = async () => {
    if (!sourcePath) {
      onError('Select or upload a source media file first.');
      return;
    }
    try {
      await api.enqueueAudioExtract({
        source_path: sourcePath,
        output_format: outputFormat,
        bitrate,
        sample_rate: sampleRate,
        audio_quality: audioQuality,
        output_filename: outputFilename || null,
        output_dir: settings.conversion_dir,
        remove_original: removeOriginal,
        duplicate_policy: settings.duplicate_handling,
      });
      onRefresh();
      onSuccess('Audio extraction job started via FFmpeg.');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Extraction failed');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Audio Extractor</h1>
        <p className="text-sm text-zinc-400">
          Extract lossless or compressed audio streams from local video files using FFmpeg.
        </p>
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Select File from Workspace</label>
            <select
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="">-- Choose a local file --</option>
              {files.map((f) => (
                <option key={f.path} value={f.path}>
                  {f.name} ({f.extension.toUpperCase()})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Or Import File from Disk</label>
            <label className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-zinc-950 border border-dashed border-zinc-700 hover:border-indigo-500 cursor-pointer text-zinc-300">
              <Upload className="w-4 h-4 text-indigo-400" />
              <span>Browse Local File...</span>
              <input type="file" onChange={handleUpload} className="hidden" />
            </label>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Output Format</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="mp3">MP3</option>
              <option value="wav">WAV</option>
              <option value="m4a">M4A</option>
              <option value="flac">FLAC</option>
              <option value="aac">AAC</option>
              <option value="ogg">OGG Vorbis</option>
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
            <label className="block text-zinc-400 mb-1.5">Sample Rate</label>
            <select
              value={sampleRate}
              onChange={(e) => setSampleRate(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value={44100}>44,100 Hz</option>
              <option value={48000}>48,000 Hz</option>
              <option value={22050}>22,050 Hz</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">VBR Quality (0=Best)</label>
            <input
              type="number"
              min={0}
              max={9}
              value={audioQuality}
              onChange={(e) => setAudioQuality(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
          <label className="flex items-center gap-2 text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={removeOriginal}
              onChange={(e) => setRemoveOriginal(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950"
            />
            Remove original source video after verified extraction
          </label>
          <button
            type="button"
            onClick={handleExtract}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2"
          >
            <FileAudio className="w-4 h-4" /> Extract Audio
          </button>
        </div>
      </div>
    </div>
  );
};
