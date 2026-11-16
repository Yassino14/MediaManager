import React, { useState } from 'react';
import { ShieldCheck, Search, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, MediaFileItem, MetadataInspection } from '../types';

export const MetadataCleanerPage: React.FC<{
  files: MediaFileItem[];
  settings: AppSettings;
  onRefresh: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}> = ({ files, settings, onRefresh, onSuccess, onError }) => {
  const [sourcePath, setSourcePath] = useState('');
  const [beforeMeta, setBeforeMeta] = useState<MetadataInspection | null>(null);
  const [afterMeta, setAfterMeta] = useState<MetadataInspection | null>(null);
  const [cleanedOutputPath, setCleanedOutputPath] = useState<string | null>(null);

  const handleInspect = async () => {
    if (!sourcePath) {
      onError('Select a media file to inspect.');
      return;
    }
    try {
      const info = await api.inspectMetadata(sourcePath);
      setBeforeMeta(info);
      setAfterMeta(null);
      setCleanedOutputPath(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'FFprobe inspection failed');
    }
  };

  const handleClean = async () => {
    if (!sourcePath) return;
    try {
      const res = await api.cleanMetadata({
        source_path: sourcePath,
        output_dir: settings.conversion_dir,
        duplicate_policy: settings.duplicate_handling,
      });
      setBeforeMeta(res.before);
      setAfterMeta(res.after);
      setCleanedOutputPath(res.output_path);
      onRefresh();
      onSuccess(`Saved cleaned copy: ${res.output_filename}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Metadata removal failed');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Metadata Inspector &amp; Cleaner</h1>
        <p className="text-sm text-zinc-400">
          Inspect container and stream tags with FFprobe and strip metadata into a new clean copy.
        </p>
      </div>

      <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 leading-relaxed">
        <strong>Privacy &amp; Technical Notice:</strong> Metadata removal is format-dependent and is
        not a forensic guarantee of complete anonymization. Container muxers may retain basic
        structural headers (e.g., encoder or major_brand), and visible watermarks or burned-in
        frames/audio signals are never altered. Original source files are never overwritten.
      </div>

      <div className="p-5 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-4 text-xs">
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            className="flex-1 px-3 py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200"
          >
            <option value="">-- Choose a file to inspect --</option>
            {files.map((f) => (
              <option key={f.path} value={f.path}>
                {f.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleInspect}
            className="px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-medium flex items-center gap-2"
          >
            <Search className="w-4 h-4" /> Inspect with FFprobe
          </button>
          <button
            type="button"
            onClick={handleClean}
            disabled={!sourcePath}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-2 disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" /> One-Click Remove Metadata
          </button>
        </div>

        {cleanedOutputPath && (
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-mono">
            Cleaned copy saved to: {cleanedOutputPath}
          </div>
        )}

        {beforeMeta && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3">
            <div className="min-w-0 p-4 rounded-lg bg-zinc-950 border border-zinc-800 space-y-2">
              <div className="font-semibold text-zinc-200">
                Original Metadata ({beforeMeta.total_tag_count} tags)
              </div>
              <pre className="text-[11px] font-mono text-zinc-400 overflow-x-auto">
                {JSON.stringify(beforeMeta.normalized_tags, null, 2)}
              </pre>
            </div>
            {afterMeta && (
              <div className="min-w-0 p-4 rounded-lg bg-zinc-950 border border-emerald-500/30 space-y-2">
                <div className="font-semibold text-emerald-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4" /> Reinspect Output ({afterMeta.total_tag_count} tags)
                </div>
                <pre className="text-[11px] font-mono text-zinc-400 overflow-x-auto">
                  {JSON.stringify(afterMeta.normalized_tags, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
