export interface UrlValidationResult {
  valid: boolean;
  url: string;
  error: string | null;
}

export function validateMediaUrlClient(rawUrl: string): UrlValidationResult;
export function parseBatchUrlLines(multilineText: string): UrlValidationResult[];
export function estimateConvertedSizeBytes(
  sourceBytes: number,
  durationSec?: number | null,
  crf?: number | null,
  targetAudioKbps?: number | null
): number;
export function formatBytes(bytes?: number | null): string;
export function formatDuration(seconds?: number | null): string;

