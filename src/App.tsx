import React, { useEffect, useRef, useState } from 'react';
import { SwissHeader } from './components/SwissHeader';
import { QueuePanel } from './components/QueuePanel';
import { InspectorPanel } from './components/InspectorPanel';
import { LocalLibraryPanel } from './components/LocalLibraryPanel';
import { TelemetryFooter } from './components/TelemetryFooter';
import { useAdaptiveLayout } from './hooks/useAdaptiveLayout';
import {
  StudioApi,
  type BuildProgress,
  type BuildTrackResult,
  type InspectResult,
  type RemoteAlbum,
  type RemotePlaylist,
  type RemoteTrack,
} from './services/api';
import type {
  AudioFormat,
  ClassifyMode,
  FilterType,
  TrackItem,
  TrackStatus,
} from './types/library';

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

/** Build a UI track from NetEase metadata + measured telemetry (no invented values). */
function toTrackItem(
  raw: RemoteTrack,
  index: number,
  collectionName: string,
  collectionType: 'album' | 'playlist',
  info?: InspectResult,
): TrackItem {
  const isDownloaded = Boolean(raw.is_downloaded && raw.local_file_path);
  const extensionMatch = isDownloaded ? raw.local_file_path.match(/\.[^.]+$/) : null;
  const extension = extensionMatch ? extensionMatch[0].toLowerCase() : '';

  const encrypted = info?.encrypted ?? extension === '.ncm';
  const container = (info?.container ??
    (extension === '.ncm' ? 'ncm' : extension.replace('.', '') || 'unknown')) as AudioFormat;

  const sampleRate = info?.sample_rate ?? null;
  const bits = info?.bits_per_sample ?? null;
  const pcm = bits && sampleRate
    ? `${bits}bit / ${(sampleRate / 1000).toFixed(1)}kHz`
    : sampleRate
      ? `${(sampleRate / 1000).toFixed(1)}kHz`
      : '—';

  const cover = info?.cover;
  const coverPresent = cover?.present ?? null;
  const coverRes = coverPresent === false
    ? '无封面'
    : cover?.width && cover?.height
      ? `${cover.width}×${cover.height}`
      : '—';
  const coverCompliant = Boolean(cover?.compliant);
  const coverReasons = cover?.reasons ?? [];

  const rawLrc = raw.raw_lrc || '';
  const lrcState: TrackItem['lrcState'] = rawLrc.includes('{"t":')
    ? 'JSON_DIRTY'
    : /\d{2}:\d{2}\.\d{3}\]/.test(rawLrc)
      ? '3DIGIT_MS'
      : 'CLEAN';

  let status: TrackStatus = 'NOT_DOWNLOADED';
  if (isDownloaded) {
    if (!info || encrypted || info.error) {
      status = 'NEEDS_FIX'; // cannot be judged before decryption / successful read
    } else if (info.needs_reframe || !coverCompliant || lrcState !== 'CLEAN') {
      status = 'NEEDS_FIX';
    } else {
      status = 'COMPLIANT';
    }
  }

  return {
    id: index + 1,
    seq: raw.seq,
    title: raw.title,
    artist: raw.artist,
    album: raw.album,
    collectionType,
    collectionName,
    targetFolder: `${collectionType === 'album' ? 'Albums' : 'Playlists'}/${collectionName}`,
    durationSec: info?.duration_sec ?? raw.duration_sec ?? 0,
    sizeBytes: raw.size_bytes || 0,
    container,
    srcExt: extension || '--',
    pcm,
    blockSize: info?.block_size ?? null,
    needsReframe: info?.needs_reframe ?? null,
    coverRes,
    coverYuv: cover?.subsampling ?? '—',
    coverType: cover?.type ?? null,
    coverCompliant,
    coverReasons,
    lrcState,
    status,
    rawLrc: rawLrc || `[00:00.00]${raw.artist} - ${raw.title}`,
    cleanLrc: raw.clean_lrc || `[00:00.00]${raw.artist} - ${raw.title}`,
    isDownloaded,
    localFilePath: raw.local_file_path || '',
    coverUrl: raw.pic_url || '',
    coverLocalPath: raw.cover_local_path || '',
    coverSource: '',
    encrypted,
    inspected: Boolean(info),
  };
}

export const App: React.FC = () => {
  const [tracks, setTracks] = useState<TrackItem[]>([]);
  const [selectedId, setSelectedId] = useState<number>(1);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [classifyMode, setClassifyMode] = useState<ClassifyMode>('db');
  const [libraryRoot, setLibraryRoot] = useState<string>('~/Music/FiiO_Echo_Library');
  const [logMessage, setLogMessage] = useState<string>(
    '[INITIALIZING] 正在从本地网易云数据库加载专辑与歌单...',
  );
  const [isBuilding, setIsBuilding] = useState<boolean>(false);
  const [normalizingId, setNormalizingId] = useState<number | null>(null);
  const [buildProgress, setBuildProgress] = useState<{ done: number; total: number }>({
    done: 0,
    total: 0,
  });
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isBrowsing, setIsBrowsing] = useState<boolean>(false);

  // DB Filter & Cache State
  const [availableAlbums, setAvailableAlbums] = useState<RemoteAlbum[]>([]);
  const [availablePlaylists, setAvailablePlaylists] = useState<RemotePlaylist[]>([]);
  const [preferredCreator, setPreferredCreator] = useState<string>('');
  const [onlyMine, setOnlyMine] = useState<boolean>(false);
  const [isLoadingDb, setIsLoadingDb] = useState<boolean>(false);
  const [customFolders, setCustomFolders] = useState<string[]>([]);

  const bootstrapped = useRef<boolean>(false);

  const {
    layoutTier,
    splitRightTab,
    setSplitRightTab,
    mobileTab,
    setMobileTab,
    windowDimensions,
  } = useAdaptiveLayout();

  // ---------------------------------------------------------------- DB loading
  const loadDbMetadata = async (): Promise<void> => {
    setIsLoadingDb(true);
    try {
      const [albumRes, plRes] = await Promise.all([
        StudioApi.getAlbums(),
        StudioApi.getPlaylists(preferredCreator, onlyMine),
      ]);
      const albums = albumRes.albums ?? [];
      setAvailableAlbums(albums);
      setAvailablePlaylists(plRes.playlists ?? []);

      const filterSummary = preferredCreator.trim()
        ? ` (筛选作者: ${preferredCreator}${onlyMine ? '，仅看TA' : ''})`
        : '';
      setLogMessage(
        `[DB SYNCED] 识别到 ${albumRes.count ?? albums.length} 张已下载专辑，${
          plRes.count ?? 0
        } 个歌单${filterSummary}。`,
      );

      if (!bootstrapped.current && albums.length > 0) {
        bootstrapped.current = true;
        await handleApplyDbAlbum(albums[0].name);
      }
    } catch (error) {
      setLogMessage(`[DB ERROR] 无法读取本地网易云数据库: ${String(error)}`);
    } finally {
      setIsLoadingDb(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDbMetadata();
    }, 300); // debounce creator typing
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferredCreator, onlyMine]);

  const selectedTrack = tracks.find((track) => track.id === selectedId) ?? tracks[0];
  const okCount = tracks.filter((track) => track.status === 'COMPLIANT').length;

  // ------------------------------------------------------------------- helpers
  const inspectDownloaded = async (items: RemoteTrack[]): Promise<Record<string, InspectResult>> => {
    const paths = items
      .filter((item) => item.is_downloaded && item.local_file_path)
      .map((item) => item.local_file_path);
    const unique = Array.from(new Set(paths));
    if (unique.length === 0) return {};
    try {
      const response = await StudioApi.inspectFiles(unique);
      return response.items ?? {};
    } catch (error) {
      setLogMessage(`[INSPECT WARN] 读取真实音频参数失败: ${String(error)}`);
      return {};
    }
  };

  const registerFolders = (items: TrackItem[]): void => {
    setCustomFolders((previous) => {
      const next = [...previous];
      items.forEach((item) => {
        if (!next.includes(item.targetFolder)) next.push(item.targetFolder);
      });
      return next;
    });
  };

  const applyInspection = async (
    rawTracks: RemoteTrack[],
    collectionName: string,
    collectionType: 'album' | 'playlist',
  ): Promise<TrackItem[]> => {
    const inspected = await inspectDownloaded(rawTracks);
    return rawTracks.map((raw, index) =>
      toTrackItem(raw, index, collectionName, collectionType, inspected[raw.local_file_path]),
    );
  };

  const makePayload = (track: TrackItem): Record<string, unknown> => ({
    src_path: track.localFilePath,
    target_folder: track.targetFolder,
    seq: track.seq,
    title: track.title,
    artist: track.artist,
    album: track.album,
    is_downloaded: track.isDownloaded,
    cover_url: track.coverUrl,
    cover_local_path: track.coverLocalPath,
  });

  const applyResults = (results: BuildTrackResult[]): void => {
    if (results.length === 0) return;
    setTracks((previous) =>
      previous.map((track) => {
        const result = results.find(
          (candidate) => candidate.seq === track.seq && candidate.title === track.title,
        );
        if (!result) return track;
        if (result.skipped) return { ...track, status: 'NOT_DOWNLOADED' };
        if (!result.success) return { ...track, status: 'NEEDS_FIX' };

        const blockOk = result.container !== 'flac' || (result.block_size ?? 0) <= 4096;
        const coverOk = Boolean(result.cover_compliant);
        const pcm = result.bits_per_sample && result.sample_rate
          ? `${result.bits_per_sample}bit / ${(result.sample_rate / 1000).toFixed(1)}kHz`
          : track.pcm;

        return {
          ...track,
          container: (result.container as AudioFormat) ?? track.container,
          srcExt: result.container ? `.${result.container}` : track.srcExt,
          blockSize: result.block_size ?? null,
          needsReframe: false,
          pcm,
          coverRes:
            result.cover_width && result.cover_height
              ? `${result.cover_width}×${result.cover_height}`
              : track.coverRes,
          coverYuv: result.cover_subsampling ?? track.coverYuv,
          coverType: result.cover_type ?? track.coverType,
          coverCompliant: coverOk,
          coverReasons: result.cover_reasons ?? [],
          coverSource: result.cover_source ?? track.coverSource,
          sizeBytes: result.size_bytes || track.sizeBytes,
          encrypted: false,
          inspected: true,
          status: blockOk && coverOk ? 'COMPLIANT' : 'NEEDS_FIX',
        };
      }),
    );
  };

  const pollBuild = async (jobId: string): Promise<BuildProgress> => {
    let applied = 0;
    for (;;) {
      await sleep(500);
      const snapshot = await StudioApi.getBuildProgress(jobId);
      if (!snapshot.success) throw new Error(snapshot.error || 'PROGRESS_FAILED');

      setBuildProgress({ done: snapshot.done, total: snapshot.total });
      if (snapshot.results.length > applied) {
        applyResults(snapshot.results.slice(applied));
        applied = snapshot.results.length;
      }
      setLogMessage(
        `[BUILDING] ${snapshot.done}/${snapshot.total} · ${snapshot.current || '准备中'} · 成功 ${
          snapshot.success_count
        } / 跳过 ${snapshot.skipped_count} / 失败 ${snapshot.failed_count}`,
      );
      if (snapshot.status !== 'running') return snapshot;
    }
  };

  // ------------------------------------------------------------------ handlers
  const handleThemeToggle = (): void => {
    const root = document.documentElement;
    root.classList.toggle('dark');
    root.classList.toggle('light');
  };

  const handleReset = (): void => {
    if (availableAlbums.length > 0) {
      void handleApplyDbAlbum(availableAlbums[0].name);
    }
    setCheckedIds(new Set());
    setIsBuilding(false);
    setBuildProgress({ done: 0, total: 0 });
    setLogMessage('[RESET] 已重新载入初始真实曲目状态。');
  };

  const handleBrowseFolder = async (): Promise<void> => {
    if (isBrowsing) return;
    setIsBrowsing(true);
    try {
      setLogMessage('[BROWSE] 正在调出系统原生文件夹选择窗口...');
      const response = await StudioApi.pickFolder();
      if (response.success && response.path) {
        setLibraryRoot(response.path);
        setLogMessage(`[LIBRARY ROOT] 本地乐库根目录已选择: ${response.path}`);
      } else {
        setLogMessage('[BROWSE] 取消选择或未更改目录。');
      }
    } catch (error) {
      setLogMessage(`[BROWSE ERROR] 无法调出文件夹选择器: ${String(error)}`);
    } finally {
      setIsBrowsing(false);
    }
  };

  const handleSelectTrack = (id: number): void => {
    setSelectedId(id);
    if (layoutTier === 'TIER_2_SPLIT') {
      setSplitRightTab('02');
    } else if (layoutTier === 'TIER_3_MOBILE') {
      setMobileTab('02');
    }
  };

  const handleToggleCheck = (id: number, checked: boolean): void => {
    setCheckedIds((previous) => {
      const next = new Set(previous);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleToggleSelectAll = (checked: boolean): void => {
    if (checked) {
      setCheckedIds(new Set(tracks.map((track) => track.id)));
    } else {
      setCheckedIds(new Set());
    }
  };

  const handleApplyDbAlbum = async (albumName: string): Promise<void> => {
    try {
      setLogMessage(`[LOADING ALBUM] 正在读取《${albumName}》的真实参数与伴随歌词...`);
      const response = await StudioApi.getAlbumTracks(albumName);
      const rawTracks = response.tracks ?? [];
      if (rawTracks.length === 0) {
        setLogMessage(`[EMPTY] 专辑《${albumName}》没有可用曲目。`);
        return;
      }
      const items = await applyInspection(rawTracks, albumName, 'album');
      setTracks(items);
      setSelectedId(1);
      setCheckedIds(new Set());
      registerFolders(items);
      const downloaded = items.filter((item) => item.isDownloaded).length;
      const encrypted = items.filter((item) => item.encrypted).length;
      setLogMessage(
        `[IMPORTED] 《${albumName}》共 ${items.length} 首，已下载 ${downloaded} 首` +
          (encrypted > 0 ? `，其中 ${encrypted} 首为加密 .ncm（构建时解密并复核）` : '') +
          '。',
      );
    } catch (error) {
      setLogMessage(`[ERR] 加载专辑失败: ${String(error)}`);
    }
  };

  const handleApplyDbPlaylist = async (pid: string): Promise<void> => {
    try {
      setLogMessage(`[LOADING PLAYLIST] 正在读取歌单 (ID: ${pid}) 与真实参数...`);
      const response = await StudioApi.getPlaylistTracks(pid);
      const rawTracks = response.tracks ?? [];
      if (rawTracks.length === 0) {
        setLogMessage(`[EMPTY] 歌单 ${pid} 没有可用曲目。`);
        return;
      }
      const playlistName =
        availablePlaylists.find((playlist) => playlist.id === pid)?.name ?? `歌单 ${pid}`;
      const items = await applyInspection(rawTracks, playlistName, 'playlist');
      setTracks(items);
      setSelectedId(1);
      setCheckedIds(new Set());
      registerFolders(items);
      const downloaded = items.filter((item) => item.isDownloaded).length;
      setLogMessage(
        `[IMPORTED] 歌单《${playlistName}》共 ${items.length} 首，已下载 ${downloaded} 首，未下载 ${
          items.length - downloaded
        } 首。`,
      );
    } catch (error) {
      setLogMessage(`[ERR] 加载歌单失败: ${String(error)}`);
    }
  };

  const handleMoveToDest = (targetFolder: string): void => {
    if (checkedIds.size === 0) {
      setLogMessage('[TIP] 请先在左侧表格中勾选需要移动的曲目。');
      return;
    }
    const isAlbum = targetFolder.startsWith('Albums/');
    const collectionName = targetFolder.split('/')[1] || targetFolder;

    setTracks((previous) =>
      previous.map((track) =>
        checkedIds.has(track.id)
          ? { ...track, targetFolder, collectionType: isAlbum ? 'album' : 'playlist', collectionName }
          : track,
      ),
    );
    setLogMessage(`[CLASSIFIED] 已将 ${checkedIds.size} 首曲目手动移入分类：${targetFolder}`);
  };

  const handleAddCustomFolder = (folderName: string): void => {
    if (!customFolders.includes(folderName)) {
      setCustomFolders((previous) => [...previous, folderName]);
    }
  };

  const handleMoveUp = (): void => {
    const index = tracks.findIndex((track) => track.id === selectedId);
    if (index > 0) {
      const next = [...tracks];
      const moved = next[index];
      next[index] = next[index - 1];
      next[index - 1] = moved;
      const reindexed = next.map((track, position) => ({
        ...track,
        seq: String(position + 1).padStart(2, '0'),
      }));
      setTracks(reindexed);
      setLogMessage(`[REORDER] 曲目上移：${moved.seq} ${moved.title}`);
    }
  };

  const handleMoveDown = (): void => {
    const index = tracks.findIndex((track) => track.id === selectedId);
    if (index >= 0 && index < tracks.length - 1) {
      const next = [...tracks];
      const moved = next[index];
      next[index] = next[index + 1];
      next[index + 1] = moved;
      const reindexed = next.map((track, position) => ({
        ...track,
        seq: String(position + 1).padStart(2, '0'),
      }));
      setTracks(reindexed);
      setLogMessage(`[REORDER] 曲目下移：${moved.seq} ${moved.title}`);
    }
  };

  /** Normalize a single track through the real backend pipeline. */
  const handleNormalizeTrack = async (id: number): Promise<void> => {
    if (isBuilding) return;
    const track = tracks.find((item) => item.id === id);
    if (!track) return;
    if (!track.isDownloaded || track.status === 'NOT_DOWNLOADED') {
      setLogMessage(`[WARN] ${track.seq} ${track.title} 未下载本地音频，无法规范化。`);
      return;
    }

    setIsBuilding(true);
    setNormalizingId(id);
    setBuildProgress({ done: 0, total: 1 });
    try {
      const started = await StudioApi.startBuild(libraryRoot, [makePayload(track)]);
      if (!started.success || !started.job_id) throw new Error(started.error || '启动失败');
      setActiveJobId(started.job_id);
      setLogMessage(`[NORMALIZE] 正在规范化 ${track.seq} ${track.title} ...`);
      const snapshot = await pollBuild(started.job_id);
      const result = snapshot.results[0];
      if (!result?.success) throw new Error(result?.reason || '规范化失败');
      const coverSourceLabel =
        result.cover_source === 'local_meta'
          ? '本地 meta'
          : result.cover_source === 'downloaded'
            ? '网络补全'
            : result.cover_source === 'embedded'
              ? '内嵌'
              : '无';
      setLogMessage(
        `[NORMALIZED] ${result.filename} · ${
          result.block_size ? `BlockSize ${result.block_size}` : 'MP3 容器'
        } · 封面 ${result.cover_compliant ? '已合规' : '仍不合规'}（来源: ${coverSourceLabel}） · 输出 ${snapshot.library_root}`,
      );
    } catch (error) {
      setLogMessage(`[NORMALIZE ERROR] ${String(error)}`);
    } finally {
      setIsBuilding(false);
      setNormalizingId(null);
      setActiveJobId(null);
    }
  };

  const handleBuildLibrary = async (): Promise<void> => {
    if (isBuilding || tracks.length === 0) return;

    const downloaded = tracks.filter((track) => track.isDownloaded && track.localFilePath);
    if (downloaded.length === 0) {
      setLogMessage('[WARN] 当前歌单/专辑中暂无已下载的本地音频文件，请先在网易云客户端中下载！');
      return;
    }

    setIsBuilding(true);
    setBuildProgress({ done: 0, total: downloaded.length });

    try {
      setLogMessage(
        `[BUILDING] 启动后台任务，处理 ${downloaded.length} 首已下载音频（未下载 ${
          tracks.length - downloaded.length
        } 首自动跳过）...`,
      );
      const started = await StudioApi.startBuild(libraryRoot, tracks.map(makePayload));
      if (!started.success || !started.job_id) throw new Error(started.error || '启动失败');

      setActiveJobId(started.job_id);
      setBuildProgress({ done: 0, total: started.total ?? tracks.length });
      const snapshot = await pollBuild(started.job_id);

      if (snapshot.status === 'error') {
        throw new Error(snapshot.error || '构建异常终止');
      }
      setLogMessage(
        `[${snapshot.status === 'cancelled' ? 'CANCELLED' : 'SUCCESS'}] 成功 ${
          snapshot.success_count
        } 首，跳过 ${snapshot.skipped_count} 首，失败 ${snapshot.failed_count} 首。清单：${
          snapshot.manifest_path
        }`,
      );
    } catch (error) {
      setLogMessage(`[BUILD ERROR] ${String(error)}`);
    } finally {
      setIsBuilding(false);
      setActiveJobId(null);
    }
  };

  const handleCancelBuild = async (): Promise<void> => {
    if (!activeJobId) return;
    try {
      const response = await StudioApi.cancelBuild(activeJobId);
      setLogMessage(
        response.success
          ? '[CANCEL] 已请求取消，当前曲目处理完成后停止。'
          : '[CANCEL] 任务已结束，无需取消。',
      );
    } catch (error) {
      setLogMessage(`[CANCEL ERROR] ${String(error)}`);
    }
  };

  const handleDotClean = async (): Promise<void> => {
    setLogMessage(`[DOT CLEAN] 正在对 ${libraryRoot} 执行 macOS 幽灵文件净化...`);
    try {
      const response = await StudioApi.dotClean(libraryRoot);
      setLogMessage(
        response.success
          ? `[DOT CLEAN SUCCESS] ${response.message}`
          : `[DOT CLEAN ERROR] ${response.error}`,
      );
    } catch (error) {
      setLogMessage(`[DOT CLEAN ERROR] 执行异常: ${String(error)}`);
    }
  };

  const handleFatSort = async (): Promise<void> => {
    setLogMessage(`[FAT SORT] 正在重建 ${libraryRoot} 的 FAT32 目录项顺序...`);
    try {
      const response = await StudioApi.fatSort(libraryRoot);
      setLogMessage(
        response.success
          ? `[FAT SORT SUCCESS] ${response.message}`
          : `[FAT SORT ERROR] ${response.error}`,
      );
    } catch (error) {
      setLogMessage(`[FAT SORT ERROR] 执行异常: ${String(error)}`);
    }
  };

  // ---------------------------------------------------------------------- view
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      <SwissHeader
        layoutTier={layoutTier}
        windowWidth={windowDimensions.width}
        windowHeight={windowDimensions.height}
        libraryRoot={libraryRoot}
        isBrowsing={isBrowsing}
        onLibraryRootChange={setLibraryRoot}
        onBrowseFolder={handleBrowseFolder}
        onThemeToggle={handleThemeToggle}
        onReset={handleReset}
      />

      {layoutTier !== 'TIER_1_DESKTOP' && (
        <nav className="swiss-border-b bg-[var(--card)] px-4 py-2 flex items-center justify-between shrink-0">
          {layoutTier === 'TIER_3_MOBILE' ? (
            <div className="flex items-center gap-1 w-full swiss-mono text-xs">
              <button
                onClick={() => setMobileTab('01')}
                className={`pane-tab flex-1 py-1.5 px-2 border font-bold cursor-pointer transition-colors ${
                  mobileTab === '01'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)]'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)]'
                }`}
              >
                01 INGEST / CLASSIFY
              </button>
              <button
                onClick={() => setMobileTab('02')}
                className={`pane-tab flex-1 py-1.5 px-2 border font-bold cursor-pointer transition-colors ${
                  mobileTab === '02'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)]'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)]'
                }`}
              >
                02 SPEC MATRIX
              </button>
              <button
                onClick={() => setMobileTab('03')}
                className={`pane-tab flex-1 py-1.5 px-2 border font-bold cursor-pointer transition-colors ${
                  mobileTab === '03'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)]'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)]'
                }`}
              >
                03 LOCAL LIBRARY
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between w-full swiss-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 bg-[#FF3300] text-white font-bold">SPLIT VIEW</span>
                <span className="text-[var(--muted-foreground)]">
                  左侧固定分类队列，右侧切换参数检视与本地乐库结构
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setSplitRightTab('02')}
                  className={`py-1 px-3 border font-bold cursor-pointer transition-colors ${
                    splitRightTab === '02'
                      ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)]'
                      : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)]'
                  }`}
                >
                  02 SPEC MATRIX
                </button>
                <button
                  onClick={() => setSplitRightTab('03')}
                  className={`py-1 px-3 border font-bold cursor-pointer transition-colors ${
                    splitRightTab === '03'
                      ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)]'
                      : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)]'
                  }`}
                >
                  03 LOCAL LIBRARY
                </button>
              </div>
            </div>
          )}
        </nav>
      )}

      <main className="workbench-grid bg-[var(--card)]">
        {(layoutTier === 'TIER_1_DESKTOP' ||
          layoutTier === 'TIER_2_SPLIT' ||
          (layoutTier === 'TIER_3_MOBILE' && mobileTab === '01')) && (
          <QueuePanel
            tracks={tracks}
            selectedId={selectedId}
            checkedIds={checkedIds}
            activeFilter={activeFilter}
            classifyMode={classifyMode}
            availableAlbums={availableAlbums}
            availablePlaylists={availablePlaylists}
            preferredCreator={preferredCreator}
            onlyMine={onlyMine}
            isLoadingDb={isLoadingDb}
            customFolders={customFolders}
            onSelectTrack={handleSelectTrack}
            onToggleCheck={handleToggleCheck}
            onToggleSelectAll={handleToggleSelectAll}
            onFilterChange={setActiveFilter}
            onClassifyModeChange={setClassifyMode}
            onPreferredCreatorChange={setPreferredCreator}
            onOnlyMineToggle={setOnlyMine}
            onRefreshDb={loadDbMetadata}
            onApplyDbAlbum={handleApplyDbAlbum}
            onApplyDbPlaylist={handleApplyDbPlaylist}
            onMoveToDest={handleMoveToDest}
            onAddCustomFolder={handleAddCustomFolder}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
          />
        )}

        {(layoutTier === 'TIER_1_DESKTOP' ||
          (layoutTier === 'TIER_2_SPLIT' && splitRightTab === '02') ||
          (layoutTier === 'TIER_3_MOBILE' && mobileTab === '02')) &&
          (selectedTrack ? (
            <InspectorPanel
              track={selectedTrack}
              isBuilding={isBuilding}
              isNormalizing={normalizingId === selectedTrack.id}
              onNormalizeTrack={handleNormalizeTrack}
            />
          ) : (
            <section
              id="col-02"
              className="col-span-12 md:col-span-6 xl:col-span-4 swiss-border-r flex items-center justify-center text-xs swiss-mono text-[var(--muted-foreground)]"
            >
              请选择或导入专辑曲目以检视硬件规范
            </section>
          ))}

        {(layoutTier === 'TIER_1_DESKTOP' ||
          (layoutTier === 'TIER_2_SPLIT' && splitRightTab === '03') ||
          (layoutTier === 'TIER_3_MOBILE' && mobileTab === '03')) && (
          <LocalLibraryPanel
            tracks={tracks}
            isBuilding={isBuilding}
            buildProgress={buildProgress}
            canCancel={Boolean(activeJobId)}
            onCancelBuild={handleCancelBuild}
            onBuildLibrary={handleBuildLibrary}
            onFatSort={handleFatSort}
            onDotClean={handleDotClean}
          />
        )}
      </main>

      <TelemetryFooter logMessage={logMessage} okCount={okCount} totalCount={tracks.length} />
    </div>
  );
};
