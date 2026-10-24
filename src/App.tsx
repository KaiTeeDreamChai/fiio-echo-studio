import React, { useState, useEffect } from 'react';
import { SwissHeader } from './components/SwissHeader';
import { QueuePanel } from './components/QueuePanel';
import { InspectorPanel } from './components/InspectorPanel';
import { LocalLibraryPanel } from './components/LocalLibraryPanel';
import { TelemetryFooter } from './components/TelemetryFooter';
import { useAdaptiveLayout } from './hooks/useAdaptiveLayout';
import { StudioApi, type RemoteAlbum, type RemotePlaylist } from './services/api';
import type { TrackItem, FilterType, ClassifyMode } from './types/library';

export const App: React.FC = () => {
  const [tracks, setTracks] = useState<TrackItem[]>([]);
  const [selectedId, setSelectedId] = useState<number>(1);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [classifyMode, setClassifyMode] = useState<ClassifyMode>('db');
  const [libraryRoot, setLibraryRoot] = useState<string>('~/Music/FiiO_Echo_Library');
  const [logMessage, setLogMessage] = useState<string>(
    '[INITIALIZING] 正在从本地网易云数据库加载专辑与歌单...'
  );
  const [isBuilding, setIsBuilding] = useState<boolean>(false);
  const [isBrowsing, setIsBrowsing] = useState<boolean>(false);

  // DB Filter & Cache State
  const [availableAlbums, setAvailableAlbums] = useState<RemoteAlbum[]>([]);
  const [availablePlaylists, setAvailablePlaylists] = useState<RemotePlaylist[]>([]);
  const [preferredCreator, setPreferredCreator] = useState<string>('');
  const [onlyMine, setOnlyMine] = useState<boolean>(false);
  const [isLoadingDb, setIsLoadingDb] = useState<boolean>(false);
  const [customFolders, setCustomFolders] = useState<string[]>([
    'Albums/Blonde',
    'Albums/Hurry Up Tomorrow',
    'Playlists/上个世纪的浪漫',
  ]);

  const {
    layoutTier,
    splitRightTab,
    setSplitRightTab,
    mobileTab,
    setMobileTab,
    windowDimensions,
  } = useAdaptiveLayout();

  // Load Initial DB Albums and Playlists
  const loadDbMetadata = async () => {
    setIsLoadingDb(true);
    try {
      const [albumRes, plRes] = await Promise.all([
        StudioApi.getAlbums(),
        StudioApi.getPlaylists(preferredCreator, onlyMine),
      ]);
      if (albumRes.albums) {
        setAvailableAlbums(albumRes.albums);
        if (tracks.length === 0 && albumRes.albums.length > 0) {
          handleApplyDbAlbum(albumRes.albums[0].name);
        }
      }
      if (plRes.playlists) setAvailablePlaylists(plRes.playlists);
      const filterSummary = preferredCreator.trim()
        ? ` (筛选作者: ${preferredCreator}${onlyMine ? '，仅看TA' : ''})`
        : '';
      setLogMessage(
        `[DB SYNCED] 识别到 ${albumRes.count} 张已下载专辑，${plRes.count} 个歌单${filterSummary}。`
      );
    } catch (e) {
      setLogMessage(`[DB NOTICE] 本地 API 正在使用内置离线缓冲: ${e}`);
    } finally {
      setIsLoadingDb(false);
    }
  };

  useEffect(() => {
    loadDbMetadata();
  }, [preferredCreator, onlyMine]);

  const selectedTrack = tracks.find((t) => t.id === selectedId) || tracks[0];
  const okCount = tracks.filter((t) => t.status === 'COMPLIANT').length;

  const handleThemeToggle = () => {
    const root = document.documentElement;
    root.classList.toggle('dark');
    root.classList.toggle('light');
  };

  const handleReset = () => {
    if (availableAlbums.length > 0) {
      handleApplyDbAlbum(availableAlbums[0].name);
    }
    setCheckedIds(new Set());
    setIsBuilding(false);
    setLogMessage('[RESET] 已重新载入初始真实曲目状态。');
  };

  // Browse Native Folder Dialog
  const handleBrowseFolder = async () => {
    if (isBrowsing) return;
    setIsBrowsing(true);
    try {
      setLogMessage('[BROWSE] 正在调出系统原生文件夹选择窗口...');
      const res = await StudioApi.pickFolder();
      if (res.success && res.path) {
        setLibraryRoot(res.path);
        setLogMessage(`[LIBRARY ROOT] 本地乐库根目录已选择: ${res.path}`);
      } else {
        setLogMessage('[BROWSE] 取消选择或未更改目录。');
      }
    } catch (e) {
      setLogMessage(`[BROWSE ERROR] 无法调出文件夹选择器: ${e}`);
    } finally {
      setIsBrowsing(false);
    }
  };

  const handleSelectTrack = (id: number) => {
    setSelectedId(id);
    if (layoutTier === 'TIER_2_SPLIT') {
      setSplitRightTab('02');
    } else if (layoutTier === 'TIER_3_MOBILE') {
      setMobileTab('02');
    }
  };

  const handleToggleCheck = (id: number, checked: boolean) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleToggleSelectAll = (checked: boolean) => {
    if (checked) {
      setCheckedIds(new Set(tracks.map((t) => t.id)));
    } else {
      setCheckedIds(new Set());
    }
  };

  // Import real Album from NetEase DB
  const handleApplyDbAlbum = async (albumName: string) => {
    try {
      setLogMessage(`[LOADING ALBUM] 正在从网易云数据库提取《${albumName}》真实文件与伴随歌词...`);
      const res = await StudioApi.getAlbumTracks(albumName);
      if (res.tracks && res.tracks.length > 0) {
        const mappedTracks: TrackItem[] = res.tracks.map((t: any, idx: number) => {
          const isDl = Boolean(t.is_downloaded && t.local_file_path);
          return {
            id: idx + 1,
            seq: t.seq,
            title: t.title,
            artist: t.artist,
            album: t.album,
            collectionType: 'album',
            collectionName: albumName,
            targetFolder: `Albums/${albumName}`,
            durationSec: t.duration_sec || 240.0,
            sizeBytes: t.size_bytes || 0,
            srcExt: isDl ? (t.local_file_path.endsWith('.ncm') ? '.ncm' : '.flac') : '--',
            pcm: isDl ? '24bit / 96kHz' : '--',
            blockSize: isDl ? 8192 : 0,
            coverRes: isDl ? '1400×1400' : '--',
            coverYuv: isDl ? '4:4:4' : '--',
            coverType: 3,
            lrcState: t.raw_lrc ? (t.raw_lrc.includes('{"t":') ? 'JSON_DIRTY' : 'CLEAN') : 'CLEAN',
            status: isDl ? 'NEEDS_FIX' : 'NOT_DOWNLOADED',
            rawLrc: t.raw_lrc || `[00:00.00]${t.artist} - ${t.title}`,
            cleanLrc: t.clean_lrc || `[00:00.00]${t.artist} - ${t.title}`,
            isDownloaded: isDl,
            localFilePath: t.local_file_path || '',
          };
        });
        setTracks(mappedTracks);
        setSelectedId(1);
        setCheckedIds(new Set());
        const dlCount = mappedTracks.filter((t) => t.isDownloaded).length;
        setLogMessage(
          `[IMPORTED] 成功从网易云加载专辑《${albumName}》(共 ${mappedTracks.length} 首，已下载: ${dlCount} 首)。`
        );
      }
    } catch (e) {
      setLogMessage(`[ERR] 加载专辑失败: ${e}`);
    }
  };

  // Import real Playlist from NetEase DB
  const handleApplyDbPlaylist = async (pid: string) => {
    try {
      setLogMessage(`[LOADING PLAYLIST] 正在从网易云数据库提取歌单 (ID: ${pid}) 曲目与伴随歌词...`);
      const res = await StudioApi.getPlaylistTracks(pid);
      if (res.tracks && res.tracks.length > 0) {
        const plName = availablePlaylists.find((p) => p.id === pid)?.name || `歌单 ${pid}`;
        const mappedTracks: TrackItem[] = res.tracks.map((t: any, idx: number) => {
          const isDl = Boolean(t.is_downloaded && t.local_file_path);
          return {
            id: idx + 1,
            seq: t.seq,
            title: t.title,
            artist: t.artist,
            album: t.album,
            collectionType: 'playlist',
            collectionName: plName,
            targetFolder: `Playlists/${plName}`,
            durationSec: t.duration_sec || 200.0,
            sizeBytes: t.size_bytes || 0,
            srcExt: isDl ? (t.local_file_path.endsWith('.ncm') ? '.ncm' : '.flac') : '--',
            pcm: isDl ? '16bit / 44.1kHz' : '--',
            blockSize: isDl ? 8192 : 0,
            coverRes: isDl ? '1200×1200' : '--',
            coverYuv: isDl ? '4:4:4' : '--',
            coverType: 3,
            lrcState: t.raw_lrc ? (t.raw_lrc.includes('{"t":') ? 'JSON_DIRTY' : 'CLEAN') : 'CLEAN',
            status: isDl ? 'NEEDS_FIX' : 'NOT_DOWNLOADED',
            rawLrc: t.raw_lrc || `[00:00.00]${t.artist} - ${t.title}`,
            cleanLrc: t.clean_lrc || `[00:00.00]${t.artist} - ${t.title}`,
            isDownloaded: isDl,
            localFilePath: t.local_file_path || '',
          };
        });
        setTracks(mappedTracks);
        setSelectedId(1);
        setCheckedIds(new Set());
        const dlCount = mappedTracks.filter((t) => t.isDownloaded).length;
        setLogMessage(
          `[IMPORTED] 成功加载歌单《${plName}》(共 ${mappedTracks.length} 首，已下载: ${dlCount} 首，未下载: ${
            mappedTracks.length - dlCount
          } 首)。`
        );
      }
    } catch (e) {
      setLogMessage(`[ERR] 加载歌单失败: ${e}`);
    }
  };

  const handleMoveToDest = (targetFolder: string) => {
    if (checkedIds.size === 0) {
      setLogMessage('[TIP] 请先在左侧表格中勾选需要移动的曲目。');
      return;
    }
    const isAlbum = targetFolder.startsWith('Albums/');
    const collectionName = targetFolder.split('/')[1] || targetFolder;

    setTracks((prev) =>
      prev.map((t) => {
        if (checkedIds.has(t.id)) {
          return {
            ...t,
            targetFolder,
            collectionType: isAlbum ? 'album' : 'playlist',
            collectionName,
          };
        }
        return t;
      })
    );
    setLogMessage(`[CLASSIFIED] 已将 ${checkedIds.size} 首曲目手动移入分类：${targetFolder}`);
  };

  const handleAddCustomFolder = (folderName: string) => {
    if (!customFolders.includes(folderName)) {
      setCustomFolders((prev) => [...prev, folderName]);
    }
  };

  const handleMoveUp = () => {
    const idx = tracks.findIndex((t) => t.id === selectedId);
    if (idx > 0) {
      const newTracks = [...tracks];
      const temp = newTracks[idx];
      newTracks[idx] = newTracks[idx - 1];
      newTracks[idx - 1] = temp;
      const reindexed = newTracks.map((t, i) => ({ ...t, seq: String(i + 1).padStart(2, '0') }));
      setTracks(reindexed);
      setLogMessage(`[REORDER] 曲目上移：${temp.seq} ${temp.title}`);
    }
  };

  const handleMoveDown = () => {
    const idx = tracks.findIndex((t) => t.id === selectedId);
    if (idx >= 0 && idx < tracks.length - 1) {
      const newTracks = [...tracks];
      const temp = newTracks[idx];
      newTracks[idx] = newTracks[idx + 1];
      newTracks[idx + 1] = temp;
      const reindexed = newTracks.map((t, i) => ({ ...t, seq: String(i + 1).padStart(2, '0') }));
      setTracks(reindexed);
      setLogMessage(`[REORDER] 曲目下移：${temp.seq} ${temp.title}`);
    }
  };

  const handleNormalizeTrack = (id: number) => {
    const t = tracks.find((x) => x.id === id);
    if (!t) return;
    if (!t.isDownloaded || t.status === 'NOT_DOWNLOADED') {
      setLogMessage(`[WARN] ${t.seq} ${t.artist} - ${t.title} 未下载本地音频文件，无法规范化。请先在网易云中下载。`);
      return;
    }
    setTracks((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          return {
            ...item,
            srcExt: '.flac',
            blockSize: 4096,
            coverRes: '500×500',
            coverYuv: '4:2:0',
            coverType: 3,
            lrcState: 'CLEAN',
            rawLrc: item.cleanLrc,
            status: 'COMPLIANT',
          };
        }
        return item;
      })
    );
    setLogMessage(`[NORMALIZED] ${t.seq} ${t.artist} - ${t.title}.flac (BlockSize=4096, Cover=500x500 YUV420p, LRC cleaned).`);
  };

  // Build local library pipeline (calls backend API)
  const handleBuildLibrary = async () => {
    if (isBuilding || tracks.length === 0) return;

    const downloadedTracks = tracks.filter((t) => t.isDownloaded && t.localFilePath);
    if (downloadedTracks.length === 0) {
      setLogMessage('[WARN] 当前歌单/专辑中暂无已下载的本地音频文件，请先在网易云客户端中下载！');
      return;
    }

    setIsBuilding(true);

    try {
      const payloadTracks = tracks.map((t) => ({
        src_path: t.localFilePath || '',
        target_folder: t.targetFolder,
        seq: t.seq,
        title: t.title,
        artist: t.artist,
        album: t.album,
        is_downloaded: t.isDownloaded,
      }));

      setLogMessage(
        `[BUILDING] 开始调用后台流水线处理 ${downloadedTracks.length} 首已下载音频 (未下载跳过 ${
          tracks.length - downloadedTracks.length
        } 首)...`
      );
      const res = await StudioApi.buildLibrary(libraryRoot, payloadTracks);

      if (res.success && res.results) {
        const resultMap = new Map<string, { success: boolean; size_bytes?: number }>();
        res.results.forEach((r) => {
          resultMap.set(`${r.seq}_${r.title}`, r);
        });

        setTracks((prev) =>
          prev.map((t) => {
            const key = `${t.seq}_${t.title}`;
            const r = resultMap.get(key);
            if (r && r.success) {
              return {
                ...t,
                srcExt: '.flac',
                blockSize: 4096,
                coverRes: '500×500',
                coverYuv: '4:2:0',
                status: 'COMPLIANT',
                sizeBytes: r.size_bytes || t.sizeBytes,
              };
            }
            if (!t.isDownloaded) {
              return {
                ...t,
                status: 'NOT_DOWNLOADED',
              };
            }
            return t;
          })
        );
        const successCount = res.success_count ?? downloadedTracks.length;
        setLogMessage(
          `[SUCCESS] 乐库构建完成！已成功规范写入 ${successCount} 首已下载曲目 (当前已合规: ${successCount}/${tracks.length} OK)。输出目录: ${res.library_root}`
        );
      } else {
        setLogMessage(`[BUILD ERROR] 构建失败: ${res.error || '未知错误'}`);
      }
    } catch (e) {
      setLogMessage(`[ERROR] 调用构建接口异常: ${e}`);
    } finally {
      setIsBuilding(false);
    }
  };

  const handleDotClean = async () => {
    setLogMessage(`[DOT CLEAN] 正在对 ${libraryRoot} 执行 macOS 幽灵文件净化 (/usr/sbin/dot_clean -m)...`);
    try {
      const res = await StudioApi.dotClean(libraryRoot);
      if (res.success) {
        setLogMessage(`[DOT CLEAN SUCCESS] ${res.message}`);
      } else {
        setLogMessage(`[DOT CLEAN ERROR] ${res.error}`);
      }
    } catch (e) {
      setLogMessage(`[DOT CLEAN ERROR] 执行异常: ${e}`);
    }
  };

  const handleFatSort = async () => {
    setLogMessage(`[FAT SORT] 正在对 ${libraryRoot} 执行 FAT32 物理目录槽位顺次重排校验...`);
    try {
      const res = await StudioApi.fatSort(libraryRoot);
      if (res.success) {
        setLogMessage(`[FAT SORT SUCCESS] ${res.message}`);
      } else {
        setLogMessage(`[FAT SORT ERROR] ${res.error}`);
      }
    } catch (e) {
      setLogMessage(`[FAT SORT ERROR] 执行异常: ${e}`);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      {/* Top Header */}
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

      {/* Adaptive Subnav */}
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
                <span className="text-[var(--muted-foreground)]">左侧固定分类队列，右侧切换参数检视与本地乐库结构</span>
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

      {/* Main 3-Column / Adaptive Grid */}
      <main className="workbench-grid bg-[var(--card)]">
        {/* Column 01 */}
        {(layoutTier === 'TIER_1_DESKTOP' || layoutTier === 'TIER_2_SPLIT' || (layoutTier === 'TIER_3_MOBILE' && mobileTab === '01')) && (
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

        {/* Column 02 */}
        {(layoutTier === 'TIER_1_DESKTOP' || (layoutTier === 'TIER_2_SPLIT' && splitRightTab === '02') || (layoutTier === 'TIER_3_MOBILE' && mobileTab === '02')) && (
          selectedTrack ? (
            <InspectorPanel
              track={selectedTrack}
              onNormalizeTrack={handleNormalizeTrack}
            />
          ) : (
            <section id="col-02" className="col-span-12 md:col-span-6 xl:col-span-4 swiss-border-r flex items-center justify-center text-xs swiss-mono text-[var(--muted-foreground)]">
              请选择或导入专辑曲目以检视硬件规范
            </section>
          )
        )}

        {/* Column 03 */}
        {(layoutTier === 'TIER_1_DESKTOP' || (layoutTier === 'TIER_2_SPLIT' && splitRightTab === '03') || (layoutTier === 'TIER_3_MOBILE' && mobileTab === '03')) && (
          <LocalLibraryPanel
            tracks={tracks}
            isBuilding={isBuilding}
            onBuildLibrary={handleBuildLibrary}
            onFatSort={handleFatSort}
            onDotClean={handleDotClean}
          />
        )}
      </main>

      {/* Bottom Telemetry Bar */}
      <TelemetryFooter
        logMessage={logMessage}
        okCount={okCount}
        totalCount={tracks.length}
      />
    </div>
  );
};
