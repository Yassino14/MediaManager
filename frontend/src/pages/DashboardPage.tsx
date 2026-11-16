import React from 'react';
import {
  Download,
  CheckCircle2,
  Activity,
  AlertOctagon,
  HardDrive,
  ArrowRight,
  Cpu,
} from 'lucide-react';
import type { EnvironmentDiagnostics, JobRecord, NavSection } from '../types';
import { formatBytes } from '../utils/validation.mjs';

interface DashboardProps {
  stats: {
    total_jobs: number;
    total_downloads: number;
    completed_jobs: number;
    active_jobs: number;
    failed_jobs: number;
    storage_used_bytes: number;
    total_files: number;
    disk_usage: { total_bytes: number; used_bytes: number; free_bytes: number };
  };
  recentJobs: JobRecord[];
  diagnostics: EnvironmentDiagnostics | null;
  onNavigate: (section: NavSection) => void;
}

export const DashboardPage: React.FC<DashboardProps> = ({
  stats,
  recentJobs,
  diagnostics,
  onNavigate,
}) => {
  const freeDiskPct =
    stats.disk_usage.total_bytes > 0
      ? Math.round((stats.disk_usage.free_bytes / stats.disk_usage.total_bytes) * 100)
      : 100;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">System Overview</h1>
          <p className="text-sm text-zinc-400">
            Local media acquisition, transcoding, and metadata sanitation status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onNavigate('downloader')}
            className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            New Download
          </button>
          <button
            type="button"
            onClick={() => onNavigate('video-converter')}
            className="px-3.5 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
          >
            Convert Media
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Total Downloads</span>
            <Download className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-semibold font-mono text-zinc-100">
            {stats.total_downloads}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">{stats.total_jobs} total jobs logged</div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Completed Jobs</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-semibold font-mono text-emerald-400">
            {stats.completed_jobs}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">Persisted in SQLite</div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Active Queue</span>
            <Activity className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 text-2xl font-semibold font-mono text-sky-400">
            {stats.active_jobs}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">Bounded worker pool</div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Failed Jobs</span>
            <AlertOctagon className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 text-2xl font-semibold font-mono text-rose-400">
            {stats.failed_jobs}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">Retryable in queue</div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Library Storage</span>
            <HardDrive className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-semibold font-mono text-zinc-100">
            {formatBytes(stats.storage_used_bytes)}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">
            {stats.total_files} files &bull; {freeDiskPct}% disk free
          </div>
        </div>
      </div>

      {/* Engine Diagnostics & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-200">Recent Activity</h2>
            <button
              type="button"
              onClick={() => onNavigate('batch')}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              Open Queue <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
          {recentJobs.length === 0 ? (
            <div className="py-10 text-center text-sm text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
              No media jobs recorded yet. Paste a URL in Downloader or convert a local file.
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/60">
              {recentJobs.slice(0, 6).map((job) => (
                <div key={job.id} className="py-2.5 flex items-center justify-between gap-4 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-zinc-200 truncate">
                      {job.title}
                      {job.is_historical && (
                        <span className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-zinc-800 text-zinc-400">
                          HISTORY
                        </span>
                      )}
                    </div>
                    <div className="text-zinc-500 truncate font-mono text-[11px]">{job.source}</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono text-zinc-400">{job.progress.toFixed(0)}%</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                        job.status === 'completed'
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : job.status === 'failed'
                          ? 'bg-rose-500/15 text-rose-300'
                          : job.status === 'cancelled'
                          ? 'bg-zinc-800 text-zinc-400'
                          : 'bg-indigo-500/15 text-indigo-300'
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <span>Local Binary Health</span>
          </div>
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800/80">
              <div className="flex items-center justify-between">
                <span className="font-medium text-zinc-300">FFmpeg Engine</span>
                <span
                  className={
                    diagnostics?.ffmpeg.available ? 'text-emerald-400 font-mono' : 'text-rose-400 font-mono'
                  }
                >
                  {diagnostics?.ffmpeg.available ? 'DETECTED' : 'MISSING'}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-zinc-500 truncate font-mono">
                {diagnostics?.ffmpeg.version || diagnostics?.ffmpeg.install_hint}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800/80">
              <div className="flex items-center justify-between">
                <span className="font-medium text-zinc-300">FFprobe Inspector</span>
                <span
                  className={
                    diagnostics?.ffprobe.available ? 'text-emerald-400 font-mono' : 'text-rose-400 font-mono'
                  }
                >
                  {diagnostics?.ffprobe.available ? 'DETECTED' : 'MISSING'}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-zinc-500 truncate font-mono">
                {diagnostics?.ffprobe.version || diagnostics?.ffprobe.install_hint}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800/80">
              <div className="flex items-center justify-between">
                <span className="font-medium text-zinc-300">yt-dlp Extractor</span>
                <span
                  className={
                    diagnostics?.yt_dlp.available ? 'text-emerald-400 font-mono' : 'text-amber-400 font-mono'
                  }
                >
                  {diagnostics?.yt_dlp.available ? `v${diagnostics.yt_dlp.version}` : 'NOT INSTALLED'}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-zinc-500 truncate font-mono">
                {diagnostics?.yt_dlp.available
                  ? 'Python API hook integration active'
                  : 'Run start.bat or pip install -U yt-dlp'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
