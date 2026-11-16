import React, { useState } from 'react';
import { Play, XCircle, RotateCcw, Trash2, FolderOpen, CheckCheck } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, JobRecord } from '../types';
import { formatBytes, formatDuration, parseBatchUrlLines } from '../utils/validation.mjs';

interface BatchProps {
  jobs: JobRecord[];
  settings: AppSettings;
  onRefreshJobs: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export const BatchDownloadsPage: React.FC<BatchProps> = ({
  jobs,
  settings,
  onRefreshJobs,
  onSuccess,
  onError,
}) => {
  const [batchText, setBatchText] = useState('');
  const [mode, setMode] = useState<'video' | 'audio'>('video');
  const [quality, setQuality] = useState(settings.default_video_quality || '1080p');

  const parsedLines = parseBatchUrlLines(batchText);
  const validUrls = parsedLines.filter((l) => l.valid).map((l) => l.url);

  const handleEnqueueBatch = async () => {
    if (validUrls.length === 0) {
      onError('Please enter at least one valid HTTP/HTTPS URL.');
      return;
    }
    try {
      const res = await api.enqueueDownloads({
        urls: validUrls,
        mode,
        video_quality: quality,
        audio_format: settings.default_audio_format || 'mp3',
        duplicate_policy: settings.duplicate_handling || 'rename',
      });
      setBatchText('');
      onRefreshJobs();
      onSuccess(`Added ${res.count} URLs to the download queue.`);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Batch enqueue failed');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Batch Downloader &amp; Active Queue</h1>
        <p className="text-sm text-zinc-400">
          Paste multiple URLs (one per line) and monitor real-time job progress, speed, and ETA.
        </p>
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4">
        <textarea
          rows={4}
          value={batchText}
          onChange={(e) => setBatchText(e.target.value)}
          placeholder={'https://www.youtube.com/watch?v=aqz-KE-bpKQ\nhttps://vimeo.com/12345678'}
          className="w-full p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-200 focus:outline-none focus:border-indigo-500"
        />
        {parsedLines.some((l) => !l.valid) && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 space-y-1">
            {parsedLines
              .filter((l) => !l.valid)
              .map((bad, idx) => (
                <div key={idx}>
                  Invalid URL <span className="font-mono">{bad.url}</span>: {bad.error}
                </div>
              ))}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-xs">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'video' | 'audio')}
              className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="video">Video Mode</option>
              <option value="audio">Audio Mode</option>
            </select>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="best">Best Quality</option>
              <option value="2160p">2160p / 4K</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
            </select>
            <span className="text-zinc-500 font-mono">{validUrls.length} valid URL(s)</span>
          </div>
          <button
            type="button"
            onClick={handleEnqueueBatch}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2"
          >
            <Play className="w-4 h-4" /> Enqueue All ({validUrls.length})
          </button>
        </div>
      </div>

      {/* Job Queue Table */}
      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">Job Queue ({jobs.length})</h2>
          <button
            type="button"
            onClick={async () => {
              await api.clearCompletedJobs();
              onRefreshJobs();
            }}
            className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 flex items-center gap-1.5"
          >
            <CheckCheck className="w-3.5 h-3.5" /> Clear Completed
          </button>
        </div>

        {jobs.length === 0 ? (
          <div className="py-12 text-center text-sm text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
            Queue is empty. Add URLs above or run a local conversion tool.
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-2.5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-zinc-100 truncate">
                        {job.title}
                      </span>
                      {job.is_historical && (
                        <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-zinc-800 text-zinc-400">
                          HISTORICAL
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] font-mono text-zinc-500 truncate">
                      {job.destination_filename || job.source}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {(job.status === 'waiting' ||
                      job.status === 'fetching_info' ||
                      job.status === 'downloading' ||
                      job.status === 'processing') && (
                      <button
                        type="button"
                        onClick={async () => {
                          await api.cancelJob(job.id);
                          onRefreshJobs();
                        }}
                        className="p-1.5 rounded-lg bg-zinc-900 hover:bg-rose-500/20 text-zinc-400 hover:text-rose-300"
                        title="Cancel Job"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    )}
                    {(job.status === 'failed' || job.status === 'cancelled') && (
                      <button
                        type="button"
                        onClick={async () => {
                          await api.retryJob(job.id);
                          onRefreshJobs();
                        }}
                        className="p-1.5 rounded-lg bg-zinc-900 hover:bg-indigo-500/20 text-zinc-400 hover:text-indigo-300"
                        title="Retry Job"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                    {job.destination_path && job.status === 'completed' && (
                      <button
                        type="button"
                        onClick={() => api.openFileInOs(job.destination_path!, true)}
                        className="p-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                        title="Open Destination Folder"
                      >
                        <FolderOpen className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={async () => {
                        await api.deleteJob(job.id);
                        onRefreshJobs();
                      }}
                      className="p-1.5 rounded-lg bg-zinc-900 hover:bg-rose-500/20 text-zinc-400 hover:text-rose-300"
                      title="Remove from Queue"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-2 rounded-full bg-zinc-900 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      job.status === 'completed'
                        ? 'bg-emerald-500'
                        : job.status === 'failed'
                        ? 'bg-rose-500'
                        : 'bg-indigo-500'
                    }`}
                    style={{ width: `${Math.min(100, Math.max(0, job.progress))}%` }}
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-zinc-400">
                  <span>
                    Status: <strong className="text-zinc-200 uppercase">{job.status}</strong> ({job.progress.toFixed(1)}%)
                  </span>
                  <span>
                    {formatBytes(job.downloaded_bytes)}
                    {job.total_bytes ? ` / ${formatBytes(job.total_bytes)}` : ''}
                  </span>
                  <span>
                    Speed: {job.speed_bps ? `${formatBytes(job.speed_bps)}/s` : '—'} &bull; ETA:{' '}
                    {job.eta_seconds !== null && job.eta_seconds !== undefined
                      ? formatDuration(job.eta_seconds)
                      : '—'}
                  </span>
                </div>
                {job.error_message && (
                  <div className="text-xs text-rose-400 bg-rose-500/10 px-3 py-1.5 rounded border border-rose-500/20">
                    {job.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
