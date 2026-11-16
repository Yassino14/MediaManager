import React, { useCallback, useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ToastContainer, type ToastMessage } from './components/ToastContainer';
import { useJobStream } from './hooks/useJobStream';
import { DashboardPage } from './pages/DashboardPage';
import { DownloaderPage } from './pages/DownloaderPage';
import { BatchDownloadsPage } from './pages/BatchDownloadsPage';
import { AudioExtractorPage } from './pages/AudioExtractorPage';
import { VideoConverterPage } from './pages/VideoConverterPage';
import { AudioConverterPage } from './pages/AudioConverterPage';
import { MetadataCleanerPage } from './pages/MetadataCleanerPage';
import { MediaLibraryPage } from './pages/MediaLibraryPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';
import type {
  AppSettings,
  EnvironmentDiagnostics,
  JobRecord,
  MediaFileItem,
  NavSection,
} from './types';

export default function App() {
  const [activeNav, setActiveNav] = useState<NavSection>('dashboard');
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [files, setFiles] = useState<MediaFileItem[]>([]);
  const [libraryBytes, setLibraryBytes] = useState(0);
  const [diagnostics, setDiagnostics] = useState<EnvironmentDiagnostics | null>(null);
  const [settings, setSettings] = useState<AppSettings>({
    download_dir: './downloads',
    conversion_dir: './converted',
    max_concurrent_downloads: 3,
    default_video_quality: '1080p',
    default_audio_format: 'mp3',
    default_audio_bitrate: '320k',
    duplicate_handling: 'rename',
    theme: 'dark',
    ffmpeg_path: '',
    ffprobe_path: '',
    ytdlp_check_updates: true,
    enable_browser_cookies: false,
    browser_for_cookies: 'edge',
    embed_thumbnail: true,
    embed_subtitles: false,
  });
  const [stats, setStats] = useState({
    total_jobs: 0,
    total_downloads: 0,
    completed_jobs: 0,
    active_jobs: 0,
    failed_jobs: 0,
    storage_used_bytes: 0,
    total_files: 0,
    disk_usage: { total_bytes: 100, used_bytes: 20, free_bytes: 80 },
  });
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const pushToast = useCallback((type: ToastMessage['type'], title: string, detail?: string) => {
    const id = `${Date.now()}_${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, title, detail }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const [dash, jobRes, fileRes, setRes] = await Promise.all([
        api.getDashboard(),
        api.listJobs(),
        api.listFiles({}),
        api.getSettings(),
      ]);
      setStats(dash.stats);
      setDiagnostics(dash.diagnostics);
      setJobs(jobRes.jobs);
      setFiles(fileRes.files);
      setLibraryBytes(fileRes.library_used_bytes);
      setSettings(setRes.settings);
    } catch {
      // Initial connection may still be booting
    }
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleJobEvent = useCallback(
    (event: string, updatedJob: JobRecord) => {
      setJobs((prev) => {
        const exists = prev.some((j) => j.id === updatedJob.id);
        if (!exists) return [updatedJob, ...prev];
        return prev.map((j) => (j.id === updatedJob.id ? updatedJob : j));
      });
      if (event === 'job_completed' || event === 'job_failed') {
        refreshAll();
      }
    },
    [refreshAll]
  );

  const { connected: sseConnected } = useJobStream(handleJobEvent);

  const activeJobsCount = jobs.filter(
    (j) =>
      j.status === 'waiting' ||
      j.status === 'fetching_info' ||
      j.status === 'downloading' ||
      j.status === 'processing'
  ).length;

  return (
    <div className="min-h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col lg:flex-row overflow-x-hidden">
      <Sidebar
        active={activeNav}
        onSelect={setActiveNav}
        activeJobsCount={activeJobsCount}
        sseConnected={sseConnected}
      />
      <main className="flex-1 min-w-0 w-full p-4 sm:p-6 lg:p-8 overflow-y-auto">
        <div className="w-full max-w-7xl mx-auto">
        {activeNav === 'dashboard' && (
          <DashboardPage
            stats={stats}
            recentJobs={jobs}
            diagnostics={diagnostics}
            onNavigate={setActiveNav}
          />
        )}
        {activeNav === 'downloader' && (
          <DownloaderPage
            settings={settings}
            onJobCreated={(m) => {
              pushToast('success', m);
              refreshAll();
              setActiveNav('batch');
            }}
            onError={(m) => pushToast('error', 'Download Error', m)}
          />
        )}
        {activeNav === 'batch' && (
          <BatchDownloadsPage
            jobs={jobs}
            settings={settings}
            onRefreshJobs={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Queue Error', m)}
          />
        )}
        {activeNav === 'audio-extractor' && (
          <AudioExtractorPage
            files={files}
            settings={settings}
            onRefresh={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Extraction Error', m)}
          />
        )}
        {activeNav === 'video-converter' && (
          <VideoConverterPage
            files={files}
            settings={settings}
            onRefresh={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Conversion Error', m)}
          />
        )}
        {activeNav === 'audio-converter' && (
          <AudioConverterPage
            files={files}
            settings={settings}
            onRefresh={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Conversion Error', m)}
          />
        )}
        {activeNav === 'metadata-cleaner' && (
          <MetadataCleanerPage
            files={files}
            settings={settings}
            onRefresh={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Metadata Error', m)}
          />
        )}
        {activeNav === 'media-library' && (
          <MediaLibraryPage
            files={files}
            libraryBytes={libraryBytes}
            onRefresh={refreshAll}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'File Error', m)}
          />
        )}
        {activeNav === 'settings' && (
          <SettingsPage
            settings={settings}
            onUpdated={setSettings}
            onSuccess={(m) => pushToast('success', m)}
            onError={(m) => pushToast('error', 'Settings Error', m)}
          />
        )}
        </div>
      </main>
      <ToastContainer
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />
    </div>
  );
}
