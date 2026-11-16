import React, { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, DuplicatePolicy } from '../types';

export const SettingsPage: React.FC<{
  settings: AppSettings;
  onUpdated: (s: AppSettings) => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ settings, onUpdated, onSuccess, onError }) => {
  const [form, setForm] = useState<AppSettings>(settings);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.updateSettings(form);
      onUpdated(res.settings);
      onSuccess('Settings persisted to local SQLite database.');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to save settings');
    }
  };

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Application Settings</h1>
          <p className="text-sm text-zinc-400">
            Configure local directories, concurrency limits, and custom FFmpeg paths.
          </p>
        </div>
        <button
          type="submit"
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2"
        >
          <Save className="w-4 h-4" /> Save Configuration
        </button>
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-zinc-400 mb-1.5">Default Download Directory</label>
            <input
              type="text"
              value={form.download_dir}
              onChange={(e) => setForm({ ...form, download_dir: e.target.value })}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Default Conversion Directory</label>
            <input
              type="text"
              value={form.conversion_dir}
              onChange={(e) => setForm({ ...form, conversion_dir: e.target.value })}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Max Concurrent Downloads (1–10)</label>
            <input
              type="number"
              min={1}
              max={10}
              value={form.max_concurrent_downloads}
              onChange={(e) =>
                setForm({ ...form, max_concurrent_downloads: Number(e.target.value) })
              }
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Default Duplicate Policy</label>
            <select
              value={form.duplicate_handling}
              onChange={(e) =>
                setForm({ ...form, duplicate_handling: e.target.value as DuplicatePolicy })
              }
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
            >
              <option value="rename">Auto-Rename</option>
              <option value="skip">Skip Duplicates</option>
              <option value="overwrite">Overwrite</option>
            </select>
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Custom FFmpeg Executable Path</label>
            <input
              type="text"
              value={form.ffmpeg_path}
              onChange={(e) => setForm({ ...form, ffmpeg_path: e.target.value })}
              placeholder="Auto-detect from system PATH"
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1.5">Custom FFprobe Executable Path</label>
            <input
              type="text"
              value={form.ffprobe_path}
              onChange={(e) => setForm({ ...form, ffprobe_path: e.target.value })}
              placeholder="Auto-detect from system PATH"
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 font-mono"
            />
          </div>
        </div>
      </div>
    </form>
  );
};
