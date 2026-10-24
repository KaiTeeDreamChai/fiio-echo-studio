/**
 * FiiO Echo Studio - Core TypeScript Definitions
 * Aligned with FIIO_ECHO_AUDIO_SPECIFICATION.md & EchoLibrarySchema v1.0
 */

export type AudioFormat = 'flac' | 'mp3' | 'ncm';
export type CollectionType = 'album' | 'playlist';
export type TrackStatus = 'NEEDS_FIX' | 'COMPLIANT' | 'PROCESSING' | 'NOT_DOWNLOADED';

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
  srcExt: string; // e.g. ".ncm", ".flac", or "--"
  pcm: string; // e.g. "24bit / 96kHz" or "--"
  blockSize: number; // e.g. 8192, 4096, or 0
  coverRes: string; // e.g. "1400×1400", "500×500", or "--"
  coverYuv: string; // e.g. "4:4:4", "4:2:0", or "--"
  coverType: number; // e.g. 3 (Cover front)
  lrcState: 'CLEAN' | 'JSON_DIRTY' | '3DIGIT_MS';
  status: TrackStatus;
  rawLrc: string;
  cleanLrc: string;
  isDownloaded: boolean;
  localFilePath: string;
}

export interface EchoLibraryRegistryTrack {
  seq: string;
  filename: string;
  lrc_filename: string;
  title: string;
  artist: string;
  duration_sec: number;
  sample_rate_hz: number;
  bit_depth: number;
  block_size: number;
  cover_spec: string;
  size_bytes: number;
  compliant: boolean;
}

export interface EchoLibraryCollection {
  id: string;
  type: CollectionType;
  name: string;
  directory: string;
  track_count: number;
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
