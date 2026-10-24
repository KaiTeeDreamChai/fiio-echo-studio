/**
 * FiiO Echo Studio - Core TypeScript Definitions
 * Aligned with FIIO_ECHO_AUDIO_SPECIFICATION.md & EchoLibrarySchema v1.1
 */

export type AudioFormat = 'flac' | 'mp3' | 'ncm' | 'unknown';
export type CollectionType = 'album' | 'playlist';
export type TrackStatus = 'NEEDS_FIX' | 'COMPLIANT' | 'PROCESSING' | 'NOT_DOWNLOADED';

export interface TrackCover {
  present: boolean | null;
  width: number | null;
  height: number | null;
  format: string | null;
  subsampling: string | null;
  progressive: boolean | null;
  compliant: boolean;
  reasons: string[];
}

export interface TrackItem {
  id: number;
  seq: string; // e.g. "01"
  title: string;
  artist: string;
  album: string;
  collectionType: CollectionType;
  collectionName: string;
  targetFolder: string; // e.g. "Albums/Blonde"
  durationSec: number;
  sizeBytes: number;
  container: AudioFormat;
  srcExt: string; // e.g. ".ncm", ".flac", ".mp3" or "--"
  pcm: string; // e.g. "24bit / 96.0kHz" or "—"
  blockSize: number | null; // real STREAMINFO max frame size, null when unknown
  needsReframe: boolean | null; // null = unknown (encrypted .ncm)
  coverRes: string; // e.g. "1115×1115", "500×500", "无封面"
  coverYuv: string; // e.g. "4:2:0", "4:4:4", "—"
  coverType: number | null; // 3 = cover front
  coverCompliant: boolean;
  coverReasons: string[];
  lrcState: 'CLEAN' | 'JSON_DIRTY' | '3DIGIT_MS';
  status: TrackStatus;
  rawLrc: string;
  cleanLrc: string;
  isDownloaded: boolean;
  localFilePath: string;
  coverUrl: string;
  coverLocalPath: string;
  coverSource: string; // 'embedded' | 'local_meta' | 'downloaded' | ''
  encrypted: boolean;
  inspected: boolean;
}

export interface EchoLibraryRegistryTrack {
  seq: string;
  filename: string;
  lrc_filename: string | null;
  title: string;
  artist: string;
  container: AudioFormat;
  size_bytes: number;
  block_size: number | null;
  sample_rate: number | null;
  bits_per_sample: number | null;
  cover: {
    compliant: boolean;
    width: number | null;
    height: number | null;
    subsampling: string | null;
    format: string | null;
    type?: number | null;
  };
  compliant: boolean;
}

export interface EchoLibraryCollection {
  id: string;
  type: CollectionType;
  name: string;
  directory: string;
  tracks: EchoLibraryRegistryTrack[];
}

export interface EchoLibraryManifest {
  schema_version: string;
  library_root: string;
  target_profile: 'SNOWSKY_FIIO_ECHO';
  updated_at: string;
  total_tracks: number;
  collections: EchoLibraryCollection[];
}

export type LayoutTier = 'TIER_1_DESKTOP' | 'TIER_2_SPLIT' | 'TIER_3_MOBILE';
export type FilterType = 'all' | 'issues' | 'ok' | 'not_downloaded';
export type ClassifyMode = 'db' | 'manual';
