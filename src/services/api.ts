/**
 * API Service for FiiO Echo Studio
 * Communicates with the local engine server (http://127.0.0.1:57123)
 */

const API_BASE =
  typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://127.0.0.1:57123/api'
    : '/api';

export interface SourceDetection {
  db_path: string | null;
  db_source: string;
  db_candidates: string[];
  download_dir: string;
  download_candidates: string[];
  download_matched: number;
  download_sample_size: number;
}

export interface BackendStatus {
  success: boolean;
  version: string;
  db_available: boolean;
  db_path: string | null;
  download_dir: string;
  detection?: SourceDetection;
  ffmpeg_available: boolean;
  ncmdump_available: boolean;
}

export interface ReloadSourcesResponse {
  success: boolean;
  db_path?: string | null;
  download_dir?: string;
  detection?: SourceDetection;
  error?: string;
}

export interface RemotePlaylist {
  id: string;
  type: string;
  name: string;
  track_count: number;
  creator: string;
  description: string;
  create_time?: number;
  update_time?: number;
  creator_id?: number | null;
  relation?: 'created' | 'favorited' | 'cached';
}

export interface RemoteAlbum {
  id: string;
  type: string;
  name: string;
  main_artist: string;
  track_count: number;
  target_folder: string;
}

export interface RemoteTrack {
  tid: string;
  seq: string;
  title: string;
  artist: string;
  album: string;
  duration_sec?: number;
  size_bytes: number;
  local_file_path: string;
  is_downloaded: boolean;
  pic_url?: string;
  cover_local_path?: string;
  raw_lrc?: string;
  clean_lrc?: string;
}

export interface RemoteCover {
  present: boolean | null;
  count: number | null;
  type: number | null;
  format: string | null;
  width: number | null;
  height: number | null;
  meta_width: number | null;
  meta_height: number | null;
  progressive: boolean | null;
  subsampling: string | null;
  compliant: boolean;
  reasons: string[];
  bytes?: number;
}

export interface InspectResult {
  path: string;
  container: 'flac' | 'mp3' | 'ncm' | 'unknown';
  encrypted: boolean;
  sample_rate: number | null;
  bits_per_sample: number | null;
  channels: number | null;
  duration_sec: number | null;
  block_size: number | null;
  needs_reframe: boolean | null;
  cover: RemoteCover;
  error: string | null;
}

export interface BuildTrackResult {
  seq: string;
  title: string;
  artist: string;
  album: string;
  success: boolean;
  skipped: boolean;
  reason: string | null;
  dest_audio: string | null;
  dest_lrc: string | null;
  filename: string | null;
  size_bytes: number;
  container: string | null;
  block_size: number | null;
  sample_rate: number | null;
  bits_per_sample: number | null;
  cover_compliant: boolean;
  cover_width: number | null;
  cover_height: number | null;
  cover_subsampling: string | null;
  cover_format: string | null;
  cover_type: number | null;
  cover_source: string | null;
  cover_reasons: string[];
  target_folder: string;
}

export interface BuildProgress {
  success: boolean;
  job_id: string;
  status: 'running' | 'done' | 'cancelled' | 'error';
  done: number;
  total: number;
  current: string;
  results: BuildTrackResult[];
  success_count: number;
  failed_count: number;
  skipped_count: number;
  library_root: string;
  manifest_path: string | null;
  error: string | null;
}

export const StudioApi = {
  /** Re-scan the local NetEase database and download folder. */
  async reloadSources(): Promise<ReloadSourcesResponse> {
    const res = await fetch(`${API_BASE}/reload-sources`, { method: 'POST' });
    return res.json();
  },

  async getStatus(): Promise<BackendStatus> {
    const res = await fetch(`${API_BASE}/status`);
    return res.json();
  },

  async pickFolder(): Promise<{ success: boolean; path?: string; cancelled?: boolean }> {
    const res = await fetch(`${API_BASE}/pick-folder`);
    return res.json();
  },

  async getPlaylists(
    creator = '',
    onlyMine = false,
  ): Promise<{ count: number; playlists: RemotePlaylist[] }> {
    const params = new URLSearchParams();
    if (creator.trim()) {
      params.append('creator', creator.trim());
      if (onlyMine) {
        params.append('only_mine', 'true');
      }
    }
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/playlists${query}`);
    return res.json();
  },

  async getAlbums(): Promise<{ count: number; albums: RemoteAlbum[] }> {
    const res = await fetch(`${API_BASE}/albums`);
    return res.json();
  },

  async getPlaylistTracks(pid: string): Promise<{ count: number; tracks: RemoteTrack[] }> {
    const res = await fetch(`${API_BASE}/playlist-tracks?pid=${encodeURIComponent(pid)}`);
    return res.json();
  },

  async getAlbumTracks(name: string): Promise<{ count: number; tracks: RemoteTrack[] }> {
    const res = await fetch(`${API_BASE}/album-tracks?name=${encodeURIComponent(name)}`);
    return res.json();
  },

  /** Real container / PCM / cover telemetry, measured server-side by mutagen. */
  async inspectFiles(
    files: string[],
  ): Promise<{ success: boolean; count: number; items: Record<string, InspectResult> }> {
    if (files.length === 0) {
      return { success: true, count: 0, items: {} };
    }
    const res = await fetch(`${API_BASE}/inspect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files }),
    });
    return res.json();
  },

  /** Kick off a background build job; poll {@link getBuildProgress} afterwards. */
  async startBuild(
    libraryRoot: string,
    tracks: Array<Record<string, unknown>>,
  ): Promise<{ success: boolean; job_id?: string; total?: number; library_root?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/build-library`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ library_root: libraryRoot, tracks }),
    });
    return res.json();
  },

  async getBuildProgress(jobId: string): Promise<BuildProgress> {
    const res = await fetch(`${API_BASE}/build-progress?job_id=${encodeURIComponent(jobId)}`);
    return res.json();
  },

  async cancelBuild(jobId: string): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE}/build-cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId }),
    });
    return res.json();
  },

  async dotClean(
    targetDir: string,
  ): Promise<{ success: boolean; message?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/dot-clean`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_dir: targetDir }),
    });
    return res.json();
  },

  async fatSort(
    targetDir: string,
  ): Promise<{ success: boolean; message?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/fat-sort`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_dir: targetDir }),
    });
    return res.json();
  },
};
