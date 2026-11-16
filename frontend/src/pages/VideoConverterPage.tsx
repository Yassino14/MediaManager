import React, { useState } from 'react';
import { Film } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, MediaFileItem } from '../types';

export const VideoConverterPage: React.FC<{
  files: MediaFileItem[];
  settings: AppSettings;
  onRefresh: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ files, settings, onRefresh, onSuccess, onError }) => {
  const [sourcePath, setSourcePath] = useState('');
  const [outputFormat, setOutputFormat] = useState('mp4');
  const [presetProfile, setPresetProfile] = useState('balanced');
  const [videoCodec, setVideoCodec] = useState('libx264');
  const [audioCodec, setAudioCodec] = useState('aac');
  const [resolution, setResolution] = useState('original');
  const [crf, setCrf] = useState(23);
  const [encoderPreset, setEncoderPreset] = useState('medium');
  const [includeAudio, setIncludeAudio] = useState(true);

  const handleConvert = async () => {
    if (!sourcePath) {
      onError('Select a source video file first.');
      return;
    }
    try {
      await api.enqueueVideoConvert({
        source_path: sourcePath,
        output_format: outputFormat,
        preset_profile: presetProfile,
        video_codec: videoCodec,
        audio_codec: audioCodec,
        resolution,
        crf,
        encoder_preset: encoderPreset,
        include_audio: includeAudio,
        output_dir: settings.conversion_dir,
        duplicate_policy: settings.duplicate_handling,
      });
      onRefresh();
      onSuccess('Video conversion job queued.');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Video conversion failed');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Video Converter &amp; Compressor</h1>
        <p className="text-sm text-zinc-400">
          Transcode between MP4, MKV, MOV, AVI, WEBM, and GIF with CRF compression controls.
        </p>
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Source Video</label>
            <select
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="">-- Select video file --</option>
              {files.map((f) => (
                <option key={f.path} value={f.path}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Target Container</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="mp4">MP4</option>
              <option value="mkv">MKV</option>
              <option value="mov">MOV</option>
              <option value="avi">AVI</option>
              <option value="webm">WEBM</option>
              <option value="gif">Animated GIF</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Optimization Preset</label>
            <select
              value={presetProfile}
              onChange={(e) => setPresetProfile(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="original">Original Quality</option>
              <option value="high">High Quality (CRF 19)</option>
              <option value="balanced">Balanced (CRF 23)</option>
              <option value="small">Small File / Compressed (CRF 28)</option>
              <option value="mobile">Mobile 720p</option>
              <option value="web">Web Optimized FastStart</option>
              <option value="custom">Custom Parameters</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Video Codec</label>
            <select
              value={videoCodec}
              onChange={(e) => setVideoCodec(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="libx264">H.264 (libx264)</option>
              <option value="libx265">H.265 / HEVC (libx265)</option>
              <option value="libvpx-vp9">VP9 (libvpx-vp9)</option>
              <option value="copy">Stream Copy (No Re-encode)</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Resolution Scaling</label>
            <select
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="original">Keep Original</option>
              <option value="2160p">3840x2160 (4K)</option>
              <option value="1440p">2560x1440 (1440p)</option>
              <option value="1080p">1920x1080 (1080p)</option>
              <option value="720p">1280x720 (720p)</option>
              <option value="480p">854x480 (480p)</option>
              <option value="360p">640x360 (360p)</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">CRF Quality ({crf})</label>
            <input
              type="range"
              min={14}
              max={36}
              value={crf}
              onChange={(e) => setCrf(Number(e.target.value))}
              className="w-full mt-2"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Encoder Speed</label>
            <select
              value={encoderPreset}
              onChange={(e) => setEncoderPreset(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="ultrafast">Ultrafast</option>
              <option value="fast">Fast</option>
              <option value="medium">Medium</option>
              <option value="slow">Slow (Better Compression)</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <label className="flex items-center gap-2 text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeAudio}
              onChange={(e) => setIncludeAudio(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950"
            />
            Include Audio Stream ({audioCodec.toUpperCase()})
          </label>
          <button
            type="button"
            onClick={handleConvert}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2"
          >
            <Film className="w-4 h-4" /> Start Video Conversion
          </button>
        </div>
      </div>
    </div>
  );
};
