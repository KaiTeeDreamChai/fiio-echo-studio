/**
 * API Service for FiiO Echo Studio
 * Communicates with the local engine server (http://127.0.0.1:57123)
 */

const API_BASE =
  typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://127.0.0.1:57123/api'
    : '/api';

export interface BackendStatus {
  success: boolean;
  db_available: boolean;
  db_path: string;
  download_dir: string;
}

export interface RemotePlaylist {
  id: string;
  type: string;
  name: string;
  track_count: number;
  creator: string;
  description: string;
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
  raw_lrc?: string;
  clean_lrc?: string;
}

export interface BuildLibraryResponse {
  success: boolean;
  library_root: string;
  manifest_path: string;
  processed_count: number;
  success_count?: number;
  failed_count?: number;
  results: Array<{
    seq: string;
    title: string;
    artist: string;
    success: boolean;
    dest_audio: string;
    size_bytes: number;
    skipped?: boolean;
    reason?: string;
  }>;
  error?: string;
}

export const StudioApi = {
  async getStatus(): Promise<BackendStatus> {
    const res = await fetch(`${API_BASE}/status`);
    return res.json();
  },

  async pickFolder(): Promise<{ success: boolean; path?: string; cancelled?: boolean }> {
    const res = await fetch(`${API_BASE}/pick-folder`);
    return res.json();
  },

  async getPlaylists(creator = '', onlyMine = false): Promise<{ count: number; playlists: RemotePlaylist[] }> {
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

  async buildLibrary(libraryRoot: string, tracks: any[]): Promise<BuildLibraryResponse> {
    const res = await fetch(`${API_BASE}/build-library`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        library_root: libraryRoot,
        tracks,
      }),
    });
    return res.json();
  },

  async dotClean(targetDir: string): Promise<{ success: boolean; message?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/dot-clean`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_dir: targetDir }),
    });
    return res.json();
  },

  async fatSort(targetDir: string): Promise<{ success: boolean; message?: string; error?: string }> {
    const res = await fetch(`${API_BASE}/fat-sort`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_dir: targetDir }),
    });
    return res.json();
  },
};
