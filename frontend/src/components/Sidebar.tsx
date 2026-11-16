import React, { useState } from 'react';
import {
  LayoutDashboard,
  Download,
  ListOrdered,
  FileAudio,
  Film,
  Music,
  ShieldCheck,
  FolderOpen,
  Settings,
  Terminal,
  Menu,
  X,
} from 'lucide-react';
import type { NavSection } from '../types';

interface SidebarProps {
  active: NavSection;
  onSelect: (section: NavSection) => void;
  activeJobsCount: number;
  sseConnected: boolean;
}

const NAV_ITEMS: { id: NavSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'downloader', label: 'Downloader', icon: Download },
  { id: 'batch', label: 'Batch & Queue', icon: ListOrdered },
  { id: 'audio-extractor', label: 'Audio Extractor', icon: FileAudio },
  { id: 'video-converter', label: 'Video Converter', icon: Film },
  { id: 'audio-converter', label: 'Audio Converter', icon: Music },
  { id: 'metadata-cleaner', label: 'Metadata Cleaner', icon: ShieldCheck },
  { id: 'media-library', label: 'Media Library', icon: FolderOpen },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({
  active,
  onSelect,
  activeJobsCount,
  sseConnected,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleSelect = (section: NavSection) => {
    onSelect(section);
    setMobileOpen(false);
  };

  const navContent = (
    <>
      <div>
        <div className="h-16 px-5 flex items-center justify-between gap-3 border-b border-zinc-800/80">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 shrink-0 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-tight text-zinc-100 truncate">
                UNIVERSAL MEDIA
              </div>
              <div className="text-[11px] font-mono text-zinc-500">
                LOCAL ENGINE v1.0
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isSelected = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isSelected
                    ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/80 border border-transparent'
                }`}
              >
                <span className="flex items-center gap-3 min-w-0">
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </span>
                {item.id === 'batch' && activeJobsCount > 0 && (
                  <span className="px-2 py-0.5 text-[11px] font-mono rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {activeJobsCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-zinc-800/80 space-y-2 text-xs text-zinc-500">
        <div className="flex items-center justify-between">
          <span>Event Stream</span>
          <span className="flex items-center gap-1.5 font-mono text-[11px]">
            <span
              className={`w-2 h-2 rounded-full ${
                sseConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {sseConnected ? 'LIVE (SSE)' : 'LOCAL'}
          </span>
        </div>
        <div className="text-[11px] text-zinc-600 leading-relaxed">
          Bound to 127.0.0.1 &bull; Zero telemetry &bull; FFmpeg + yt-dlp API
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile / Compact Top Bar (< lg) */}
      <header className="lg:hidden sticky top-0 z-30 h-14 px-4 border-b border-zinc-800/80 bg-zinc-950/95 backdrop-blur flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="p-2 -ml-1 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-900"
            aria-label="Open navigation"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="w-7 h-7 shrink-0 rounded-md bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Terminal className="w-4 h-4" />
          </div>
          <span className="text-sm font-semibold text-zinc-100 truncate">
            UNIVERSAL MEDIA
          </span>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          {activeJobsCount > 0 && (
            <button
              type="button"
              onClick={() => handleSelect('batch')}
              className="px-2 py-0.5 text-[11px] font-mono rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
            >
              {activeJobsCount} active
            </button>
          )}
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-zinc-400">
            <span
              className={`w-2 h-2 rounded-full ${
                sseConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {sseConnected ? 'LIVE' : 'LOCAL'}
          </span>
        </div>
      </header>

      {/* Mobile Slide-Over Drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative z-50 w-64 max-w-[80vw] h-full bg-zinc-950 border-r border-zinc-800/80 flex flex-col justify-between overflow-y-auto select-none">
            {navContent}
          </aside>
        </div>
      )}

      {/* Desktop Sticky Sidebar (>= lg) */}
      <aside className="hidden lg:flex lg:w-60 xl:w-64 shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-zinc-800/80 bg-zinc-950 flex-col justify-between overflow-y-auto select-none">
        {navContent}
      </aside>
    </>
  );
};
