import React, { useState } from 'react';
import { FolderOpen, Trash2, Edit3, Play } from 'lucide-react';
import { api } from '../services/api';
import type { MediaFileItem } from '../types';
import { formatBytes } from '../utils/validation.mjs';

export const MediaLibraryPage: React.FC<{
  files: MediaFileItem[];
  libraryBytes: number;
  onRefresh: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ files, libraryBytes, onRefresh, onSuccess, onError }) => {
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'video' | 'audio' | 'other'>('all');
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size' | 'format'>('date');
  const [previewFile, setPreviewFile] = useState<MediaFileItem | null>(null);
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [newName, setNewName] = useState('');

  const filtered = files
    .filter((f) => (filterType === 'all' ? true : f.category === filterType))
    .filter((f) => f.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'size') return b.size_bytes - a.size_bytes;
      if (sortBy === 'format') return a.extension.localeCompare(b.extension);
      return b.modified_ts - a.modified_ts;
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Media Library</h1>
          <p className="text-sm text-zinc-400">
            {files.length} files in permitted workspace directories &bull; {formatBytes(libraryBytes)} used
          </p>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800/80 flex flex-wrap gap-3 text-xs">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by filename..."
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
        />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as 'all' | 'video' | 'audio' | 'other')}
          className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
        >
          <option value="all">All Formats</option>
          <option value="video">Video Only</option>
          <option value="audio">Audio Only</option>
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'date' | 'name' | 'size' | 'format')}
          className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
        >
          <option value="date">Sort by Date</option>
          <option value="name">Sort by Name</option>
          <option value="size">Sort by Size</option>
          <option value="format">Sort by Format</option>
        </select>
      </div>

      {previewFile && (
        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-zinc-200">Preview: {previewFile.name}</span>
            <button
              type="button"
              onClick={() => setPreviewFile(null)}
              className="text-zinc-400 hover:text-zinc-200"
            >
              Close Preview
            </button>
          </div>
          {previewFile.category === 'video' ? (
            <video
              controls
              src={`/api/files/stream?path=${encodeURIComponent(previewFile.path)}`}
              className="w-full max-h-80 rounded-lg bg-black"
            />
          ) : (
            <audio
              controls
              src={`/api/files/stream?path=${encodeURIComponent(previewFile.path)}`}
              className="w-full"
            />
          )}
        </div>
      )}

      <div className="rounded-xl bg-zinc-900/70 border border-zinc-800/80 overflow-hidden">
        <div className="divide-y divide-zinc-800/60">
          {filtered.map((file) => (
            <div
              key={file.path}
              className="p-3.5 flex items-center justify-between gap-4 text-xs hover:bg-zinc-900"
            >
              <div className="min-w-0 flex-1">
                {renamingPath === file.path ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      className="px-2.5 py-1 rounded bg-zinc-950 border border-zinc-700 text-zinc-100"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await api.renameFile(file.path, newName);
                          setRenamingPath(null);
                          onRefresh();
                          onSuccess('File renamed.');
                        } catch (err) {
                          onError(err instanceof Error ? err.message : 'Rename failed');
                        }
                      }}
                      className="px-2.5 py-1 rounded bg-indigo-600 text-white"
                    >
                      Save
                    </button>
                  </div>
                ) : (
                  <div className="font-medium text-zinc-200 truncate">{file.name}</div>
                )}
                <div className="text-[11px] font-mono text-zinc-500">
                  {file.extension.toUpperCase()} &bull; {formatBytes(file.size_bytes)} &bull;{' '}
                  {new Date(file.modified_at).toLocaleString()}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setPreviewFile(file)}
                  className="p-1.5 rounded-lg bg-zinc-950 hover:bg-zinc-800 text-zinc-300"
                  title="Preview Media"
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRenamingPath(file.path);
                    setNewName(file.name);
                  }}
                  className="p-1.5 rounded-lg bg-zinc-950 hover:bg-zinc-800 text-zinc-300"
                  title="Rename"
                >
                  <Edit3 className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => api.openFileInOs(file.path, true)}
                  className="p-1.5 rounded-lg bg-zinc-950 hover:bg-zinc-800 text-zinc-300"
                  title="Open Folder"
                >
                  <FolderOpen className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await api.deleteFile(file.path);
                    onRefresh();
                    onSuccess(`Deleted ${file.name}`);
                  }}
                  className="p-1.5 rounded-lg bg-zinc-950 hover:bg-rose-500/20 text-zinc-400 hover:text-rose-300"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
