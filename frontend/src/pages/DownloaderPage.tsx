import React, { useEffect, useState } from 'react';
import { Search, Download, ListVideo, CheckSquare, Square, Film, Music } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, DuplicatePolicy, MediaProbeResponse } from '../types';
import { formatBytes, formatDuration, validateMediaUrlClient } from '../utils/validation.mjs';

interface DownloaderProps {
  settings: AppSettings;
  onJobCreated: (msg: string) => void;
  onError: (msg: string) => void;
}

export const DownloaderPage: React.FC<DownloaderProps> = ({
  settings,
  onJobCreated,
  onError,
}) => {
  const [url, setUrl] = useState('');
  const [probing, setProbing] = useState(false);
  const [probeData, setProbeData] = useState<MediaProbeResponse | null>(null);
  const [mode, setMode] = useState<'video' | 'audio'>('video');
  const [videoQuality, setVideoQuality] = useState(settings.default_video_quality || '1080p');
  const [customFormatId, setCustomFormatId] = useState('');
  const [audioFormat, setAudioFormat] = useState(settings.default_audio_format || 'mp3');
  const [audioBitrate, setAudioBitrate] = useState(settings.default_audio_bitrate || '320k');
  const [customFilename, setCustomFilename] = useState('');
  const [outputDir, setOutputDir] = useState(settings.download_dir || '');
  const [embedThumbnail, setEmbedThumbnail] = useState(settings.embed_thumbnail);
  const [embedSubtitles, setEmbedSubtitles] = useState(settings.embed_subtitles);
  const [downloadSubsSeparately, setDownloadSubsSeparately] = useState(false);
  const [duplicatePolicy, setDuplicatePolicy] = useState<DuplicatePolicy>(
    settings.duplicate_handling || 'rename'
  );
  const [selectedPlaylistItems, setSelectedPlaylistItems] = useState<number[]>([]);

  useEffect(() => {
    if (settings.download_dir && (!outputDir || outputDir === './downloads')) {
      setOutputDir(settings.download_dir);
    }
  }, [settings.download_dir, outputDir]);

  const handleInspect = async (e: React.FormEvent) => {
    e.preventDefault();
    const check = validateMediaUrlClient(url);
    if (!check.valid) {
      onError(check.error || 'Invalid URL');
      return;
    }
    setProbing(true);
    try {
      const info = await api.probeUrl(check.url);
      setProbeData(info);
      if (info.is_playlist) {
        setSelectedPlaylistItems(info.playlist_entries.map((item) => item.index));
      } else {
        setSelectedPlaylistItems([]);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to inspect URL');
    } finally {
      setProbing(false);
    }
  };

  const handleStartDownload = async () => {
    const check = validateMediaUrlClient(url);
    if (!check.valid) {
      onError(check.error || 'Invalid URL');
      return;
    }
    try {
      const res = await api.enqueueDownloads({
        urls: [check.url],
        mode,
        video_quality: videoQuality,
        custom_format_id: customFormatId || null,
        audio_format: audioFormat,
        audio_bitrate: audioBitrate,
        output_dir: outputDir || null,
        custom_filename: customFilename || null,
        embed_thumbnail: embedThumbnail,
        embed_subtitles: embedSubtitles,
        download_subtitles_separately: downloadSubsSeparately,
        include_playlist: Boolean(probeData?.is_playlist),
        playlist_items: probeData?.is_playlist ? selectedPlaylistItems : null,
        duplicate_policy: duplicatePolicy,
      });
      onJobCreated(`Enqueued ${res.count} download job(s)`);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to enqueue download');
    }
  };

  const togglePlaylistItem = (index: number) => {
    setSelectedPlaylistItems((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Universal Media Downloader</h1>
        <p className="text-sm text-zinc-400">
          Inspect video, audio, and playlists via yt-dlp Python API before downloading.
        </p>
      </div>

      <form
        onSubmit={handleInspect}
        className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4"
      >
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste HTTP/HTTPS media or playlist URL (YouTube, Vimeo, SoundCloud, Archive.org...)"
            className="flex-1 px-4 py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={probing}
            className="px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-xs font-medium flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            <Search className="w-4 h-4" />
            {probing ? 'Inspecting...' : 'Inspect Media'}
          </button>
          <button
            type="button"
            onClick={handleStartDownload}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center justify-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download Now
          </button>
        </div>
      </form>

      {probeData && (
        <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-5">
          <div className="flex flex-col md:flex-row gap-5">
            {probeData.thumbnail && (
              <img
                src={probeData.thumbnail}
                alt={probeData.title}
                className="w-full md:w-56 h-32 object-cover rounded-lg border border-zinc-800"
              />
            )}
            <div className="flex-1 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 text-[11px] font-mono rounded bg-indigo-500/15 text-indigo-300">
                  {probeData.is_playlist ? `PLAYLIST (${probeData.playlist_count})` : probeData.extractor || 'MEDIA'}
                </span>
                {probeData.upload_date && (
                  <span className="text-xs text-zinc-500 font-mono">{probeData.upload_date}</span>
                )}
              </div>
              <h2 className="text-base font-semibold text-zinc-100">{probeData.title}</h2>
              <div className="text-xs text-zinc-400 flex flex-wrap gap-4">
                <span>Uploader: {probeData.uploader || 'Unknown'}</span>
                <span>Duration: {formatDuration(probeData.duration)}</span>
                <span>Est. Max Size: {formatBytes(probeData.estimated_size_bytes)}</span>
              </div>
            </div>
          </div>

          {probeData.is_playlist && probeData.playlist_entries.length > 0 && (
            <div className="space-y-2 border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                  <ListVideo className="w-4 h-4 text-indigo-400" />
                  Select Playlist Items ({selectedPlaylistItems.length} / {probeData.playlist_entries.length})
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedPlaylistItems(probeData.playlist_entries.map((e) => e.index))
                    }
                    className="text-xs text-indigo-400 hover:underline"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedPlaylistItems([])}
                    className="text-xs text-zinc-400 hover:underline"
                  >
                    Clear All
                  </button>
                </div>
              </div>
              <div className="max-h-52 overflow-y-auto divide-y divide-zinc-800/60 border border-zinc-800 rounded-lg bg-zinc-950/60">
                {probeData.playlist_entries.map((item) => {
                  const checked = selectedPlaylistItems.includes(item.index);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => togglePlaylistItem(item.index)}
                      className="w-full px-3 py-2 flex items-center justify-between text-left text-xs hover:bg-zinc-900/80"
                    >
                      <span className="flex items-center gap-2.5 truncate">
                        {checked ? (
                          <CheckSquare className="w-4 h-4 text-indigo-400 shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 text-zinc-600 shrink-0" />
                        )}
                        <span className="font-mono text-zinc-500">#{item.index}</span>
                        <span className="text-zinc-200 truncate">{item.title}</span>
                      </span>
                      <span className="font-mono text-zinc-500 shrink-0">
                        {formatDuration(item.duration)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Download Options Panel */}
      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-5">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMode('video')}
            className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 border ${
              mode === 'video'
                ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                : 'bg-zinc-950 text-zinc-400 border-zinc-800'
            }`}
          >
            <Film className="w-4 h-4" /> Video Stream
          </button>
          <button
            type="button"
            onClick={() => setMode('audio')}
            className={`px-3.5 py-2 rounded-lg text-xs font-medium flex items-center gap-2 border ${
              mode === 'audio'
                ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                : 'bg-zinc-950 text-zinc-400 border-zinc-800'
            }`}
          >
            <Music className="w-4 h-4" /> Audio Only
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {mode === 'video' ? (
            <>
              <div>
                <label className="block text-zinc-400 mb-1.5">Resolution Preset</label>
                <select
                  value={videoQuality}
                  onChange={(e) => setVideoQuality(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
                >
                  <option value="best">Best Available Quality</option>
                  <option value="2160p">2160p / 4K UHD</option>
                  <option value="1440p">1440p QHD</option>
                  <option value="1080p">1080p Full HD</option>
                  <option value="720p">720p HD</option>
                  <option value="480p">480p SD</option>
                  <option value="360p">360p Compact</option>
                </select>
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Custom Format ID (Optional)</label>
                <input
                  type="text"
                  value={customFormatId}
                  onChange={(e) => setCustomFormatId(e.target.value)}
                  placeholder="e.g., 137 or 299"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-zinc-400 mb-1.5">Audio Format</label>
                <select
                  value={audioFormat}
                  onChange={(e) => setAudioFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
                >
                  <option value="best">Best Available Audio</option>
                  <option value="mp3">MP3</option>
                  <option value="m4a">M4A</option>
                  <option value="wav">WAV (Lossless PCM)</option>
                  <option value="flac">FLAC (Lossless)</option>
                </select>
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Target Bitrate</label>
                <select
                  value={audioBitrate}
                  onChange={(e) => setAudioBitrate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
                >
                  <option value="320k">320 kbps</option>
                  <option value="256k">256 kbps</option>
                  <option value="192k">192 kbps</option>
                  <option value="128k">128 kbps</option>
                </select>
              </div>
            </>
          )}

          <div>
            <label className="block text-zinc-400 mb-1.5">Duplicate Handling</label>
            <select
              value={duplicatePolicy}
              onChange={(e) => setDuplicatePolicy(e.target.value as DuplicatePolicy)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="rename">Auto-Rename (e.g., file (1).mp4)</option>
              <option value="skip">Skip Existing Files</option>
              <option value="overwrite">Overwrite Existing Files</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-zinc-400 mb-1.5">Custom Output Filename (Optional)</label>
            <input
              type="text"
              value={customFilename}
              onChange={(e) => setCustomFilename(e.target.value)}
              placeholder="Leave empty to use video title"
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Output Directory</label>
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-6 text-xs text-zinc-300 pt-1">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={embedThumbnail}
              onChange={(e) => setEmbedThumbnail(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950"
            />
            Embed Thumbnail
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={embedSubtitles}
              onChange={(e) => setEmbedSubtitles(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950"
            />
            Embed Subtitles
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={downloadSubsSeparately}
              onChange={(e) => setDownloadSubsSeparately(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950"
            />
            Save Subtitles (.srt/.vtt) Separately
          </label>
        </div>
      </div>
    </div>
  );
};
