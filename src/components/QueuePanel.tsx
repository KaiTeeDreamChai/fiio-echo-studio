import React, { useEffect, useMemo, useState } from 'react';
import type { TrackItem, ClassifyMode, FilterType } from '../types/library';
import type { RemoteAlbum, RemotePlaylist } from '../services/api';
import { fuzzyScore } from '../lib/fuzzy';

interface QueuePanelProps {
  tracks: TrackItem[];
  selectedId: number;
  checkedIds: Set<number>;
  activeFilter: FilterType;
  classifyMode: ClassifyMode;
  availableAlbums: RemoteAlbum[];
  availablePlaylists: RemotePlaylist[];
  preferredCreator: string;
  onlyMine: boolean;
  isLoadingDb: boolean;
  customFolders: string[];
  hideSource?: boolean;
  onSelectTrack: (id: number) => void;
  onToggleCheck: (id: number, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onFilterChange: (filter: FilterType) => void;
  onClassifyModeChange: (mode: ClassifyMode) => void;
  onPreferredCreatorChange: (creator: string) => void;
  onOnlyMineToggle: (onlyMine: boolean) => void;
  onRefreshDb: () => void;
  onApplyDbAlbum: (albumName: string) => void;
  onApplyDbPlaylist: (pid: string) => void;
  onMoveToDest: (targetFolder: string) => void;
  onAddCustomFolder: (name: string) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

export const QueuePanel: React.FC<QueuePanelProps> = ({
  tracks,
  selectedId,
  checkedIds,
  activeFilter,
  classifyMode,
  availableAlbums,
  availablePlaylists,
  preferredCreator,
  onlyMine,
  isLoadingDb,
  customFolders,
  hideSource = false,
  onSelectTrack,
  onToggleCheck,
  onToggleSelectAll,
  onFilterChange,
  onClassifyModeChange,
  onPreferredCreatorChange,
  onOnlyMineToggle,
  onRefreshDb,
  onApplyDbAlbum,
  onApplyDbPlaylist,
  onMoveToDest,
  onAddCustomFolder,
  onMoveUp,
  onMoveDown,
}) => {
  const [dbSourceType, setDbSourceType] = useState<'album' | 'playlist'>('album');
  const [selectedAlbum, setSelectedAlbum] = useState<string>('');
  const [selectedPlaylist, setSelectedPlaylist] = useState<string>('');
  const [manualDest, setManualDest] = useState<string>('');
  const [isCreatingFolder, setIsCreatingFolder] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>('');

  // Keep the pickers aligned with live data instead of hardcoded sample values.
  useEffect(() => {
    if (!selectedAlbum || !availableAlbums.some((album) => album.name === selectedAlbum)) {
      setSelectedAlbum(availableAlbums[0]?.name ?? '');
    }
  }, [availableAlbums, selectedAlbum]);

  useEffect(() => {
    if (!manualDest || !customFolders.includes(manualDest)) {
      setManualDest(customFolders[0] ?? '');
    }
  }, [customFolders, manualDest]);

  const visiblePlaylists = useMemo(() => {
    const keyword = preferredCreator.trim();
    if (!keyword) return availablePlaylists;
    const matched: RemotePlaylist[] = [];
    const rest: RemotePlaylist[] = [];
    availablePlaylists.forEach((playlist) => {
      (fuzzyScore(keyword, playlist.creator) !== null ? matched : rest).push(playlist);
    });
    return onlyMine ? matched : [...matched, ...rest];
  }, [availablePlaylists, preferredCreator, onlyMine]);

  const filteredTracks = tracks.filter((t) => {
    if (activeFilter === 'issues') return t.status === 'NEEDS_FIX';
    if (activeFilter === 'ok') return t.status === 'COMPLIANT';
    if (activeFilter === 'not_downloaded') return t.status === 'NOT_DOWNLOADED';
    return true;
  });

  const okCount = tracks.filter((t) => t.status === 'COMPLIANT').length;
  const needsFixCount = tracks.filter((t) => t.status === 'NEEDS_FIX').length;
  const notDownloadedCount = tracks.filter((t) => t.status === 'NOT_DOWNLOADED').length;
  const isAllChecked = tracks.length > 0 && checkedIds.size === tracks.length;

  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      const formatted = newFolderName.trim().startsWith('Playlists/') || newFolderName.trim().startsWith('Albums/')
        ? newFolderName.trim()
        : `Playlists/${newFolderName.trim()}`;
      onAddCustomFolder(formatted);
      setManualDest(formatted);
      setNewFolderName('');
      setIsCreatingFolder(false);
    }
  };

  return (
    <section id="col-01" className="col-span-12 md:col-span-6 xl:col-span-5 swiss-border-r flex flex-col min-h-0 h-full">
      {/* Section Header */}
      <div className="px-3.5 py-2.5 swiss-border-b flex items-center justify-between bg-[var(--sidebar)] shrink-0">
        <div className="flex items-baseline gap-3 min-w-0">
          <h2 className="text-xs font-bold tracking-wider shrink-0">曲目</h2>
          <span className="swiss-mono text-[10px] text-[var(--muted-foreground)] truncate">
            {tracks[0]?.collectionName ?? '未选择来源'} · {tracks.length} 首
          </span>
        </div>
      </div>

      {!hideSource && (
        <>
      {/* Mode 1 & 2 Tab Switcher */}
      <div className="p-2.5 swiss-border-b bg-[var(--background)] shrink-0 space-y-2">
        <div className="grid grid-cols-2 gap-1.5 swiss-mono text-xs">
          <button
            onClick={() => onClassifyModeChange('db')}
            className={`py-1.5 px-2 border font-bold cursor-pointer text-left flex items-center justify-between transition-colors ${
              classifyMode === 'db'
                ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)] shadow-inner'
                : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)] hover:bg-[var(--sidebar)]'
            }`}
          >
            <span>A. 网易云本地数据库导入</span>
            <span className="text-xs px-1 bg-[#FF3300] text-white">AUTO</span>
          </button>
          <button
            onClick={() => onClassifyModeChange('manual')}
            className={`py-1.5 px-2 border font-bold cursor-pointer text-left flex items-center justify-between transition-colors ${
              classifyMode === 'manual'
                ? 'bg-[var(--active-bg)] text-[var(--active-fg)] border-[var(--active-border)] shadow-inner'
                : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-[var(--border)] hover:bg-[var(--sidebar)]'
            }`}
          >
            <span>B. 手动创建/编排分类</span>
            <span className="text-xs text-[var(--muted-foreground)]">MANUAL</span>
          </button>
        </div>

        {/* Mode A: NetEase DB View */}
        {classifyMode === 'db' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs swiss-mono">
              <div className="flex items-center gap-1.5">
                <span className="text-[var(--muted-foreground)]">作者筛选:</span>
                <input
                  type="text"
                  value={preferredCreator}
                  onChange={(e) => onPreferredCreatorChange(e.target.value)}
                  placeholder="作者昵称 (可选)"
                  className="bg-[var(--card)] border border-[var(--border)] px-1.5 py-0.5 text-xs font-bold w-28 focus:outline-none"
                />
                <label
                  className={`flex items-center gap-1 cursor-pointer ml-1 select-none transition-opacity ${
                    !preferredCreator.trim() ? 'opacity-40 cursor-not-allowed' : ''
                  }`}
                  title={!preferredCreator.trim() ? '请先输入作者昵称以启用 TA 的专属筛选' : undefined}
                >
                  <input
                    type="checkbox"
                    checked={onlyMine && !!preferredCreator.trim()}
                    disabled={!preferredCreator.trim()}
                    onChange={(e) => onOnlyMineToggle(e.target.checked)}
                    className="swiss-check"
                  />
                  <span className="font-semibold text-xs">仅看 TA 的歌单</span>
                </label>
              </div>

              <button
                onClick={onRefreshDb}
                disabled={isLoadingDb}
                className="text-xs swiss-mono px-2 py-0.5 border border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] font-bold cursor-pointer"
              >
                {isLoadingDb ? '扫描中...' : '↻ 重新探测'}
              </button>
            </div>

            <div className="grid grid-cols-12 gap-1.5 items-center">
              <div className="col-span-4 flex items-center border border-[var(--border)] bg-[var(--card)] text-xs swiss-mono font-bold">
                <button
                  onClick={() => setDbSourceType('album')}
                  className={`flex-1 py-1 text-center cursor-pointer transition-colors ${
                    dbSourceType === 'album'
                      ? 'bg-[var(--active-bg)] text-[var(--active-fg)] shadow-sm'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--sidebar)]'
                  }`}
                >
                  已下专辑
                </button>
                <button
                  onClick={() => setDbSourceType('playlist')}
                  className={`flex-1 py-1 text-center cursor-pointer transition-colors ${
                    dbSourceType === 'playlist'
                      ? 'bg-[var(--active-bg)] text-[var(--active-fg)] shadow-sm'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--sidebar)]'
                  }`}
                >
                  歌单列表
                </button>
              </div>

              {dbSourceType === 'album' ? (
                <>
                  <select
                    aria-label="Select Downloaded Album"
                    value={selectedAlbum}
                    onChange={(e) => setSelectedAlbum(e.target.value)}
                    className="col-span-5 bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] px-2 py-1 text-xs font-semibold swiss-mono cursor-pointer focus:outline-none truncate"
                  >
                    {availableAlbums.map((a) => (
                      <option key={a.id} value={a.name} className="bg-[var(--card)] text-[var(--foreground)]">
                        {a.name} ({a.track_count}首 - {a.main_artist})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => selectedAlbum && onApplyDbAlbum(selectedAlbum)}
                    disabled={!selectedAlbum}
                    className="col-span-3 text-xs swiss-mono px-2 py-1 bg-[#FF3300] hover:bg-[#e02d00] disabled:opacity-40 text-white font-bold cursor-pointer truncate"
                  >
                    导入此专辑 →
                  </button>
                </>
              ) : (
                <>
                  <select
                    aria-label="Select Playlist"
                    value={selectedPlaylist || (availablePlaylists[0]?.id ?? '')}
                    onChange={(e) => setSelectedPlaylist(e.target.value)}
                    className="col-span-5 bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] px-2 py-1 text-xs font-semibold swiss-mono cursor-pointer focus:outline-none truncate"
                  >
                    {visiblePlaylists.map((p) => (
                      <option key={p.id} value={p.id} className="bg-[var(--card)] text-[var(--foreground)]">
                        {p.name} ({p.track_count}首 - {p.creator})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => onApplyDbPlaylist(selectedPlaylist || visiblePlaylists[0]?.id)}
                    className="col-span-3 text-xs swiss-mono px-2 py-1 bg-[#FF3300] hover:bg-[#e02d00] text-white font-bold cursor-pointer truncate"
                  >
                    导入此歌单 →
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* Mode B: Manual View */}
        {classifyMode === 'manual' && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[var(--muted-foreground)] swiss-mono">手动分类操作栏:</span>
              <div className="flex items-center gap-1">
                {isCreatingFolder ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      placeholder="歌单名称"
                      className="bg-[var(--card)] border border-[var(--border)] px-1.5 py-0.5 text-xs swiss-mono w-28 focus:outline-none"
                    />
                    <button
                      onClick={handleCreateFolder}
                      className="text-xs swiss-mono px-1.5 py-0.5 bg-[#FF3300] text-white font-bold cursor-pointer"
                    >
                      确定
                    </button>
                    <button
                      onClick={() => setIsCreatingFolder(false)}
                      className="text-xs swiss-mono px-1.5 py-0.5 border border-[var(--border)] font-bold cursor-pointer"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsCreatingFolder(true)}
                    className="text-xs swiss-mono px-2 py-0.5 border border-[var(--border)] bg-[var(--card)] font-bold cursor-pointer hover:border-[#FF3300]"
                  >
                    + 新建专辑/歌单
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-12 gap-1.5">
              <select
                aria-label="Select Target Destination Collection"
                value={manualDest}
                onChange={(e) => setManualDest(e.target.value)}
                className="col-span-8 bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] px-2 py-1 text-xs font-semibold swiss-mono cursor-pointer focus:outline-none"
              >
                {customFolders.map((f) => (
                  <option key={f} value={f} className="bg-[var(--card)] text-[var(--foreground)]">
                    目标: {f}
                  </option>
                ))}
              </select>
              <button
                onClick={() => onMoveToDest(manualDest)}
                className="col-span-4 text-xs swiss-mono px-2 py-1 border border-[var(--border)] bg-[var(--active-bg)] text-[var(--active-fg)] hover:bg-[#FF3300] hover:border-[#FF3300] hover:text-white font-bold cursor-pointer truncate transition-colors"
              >
                移入所选分类 →
              </button>
            </div>
          </div>
        )}
      </div>

        </>
      )}

      {/* Filter & Batch Selection Bar */}
      <div className="px-3.5 py-1.5 swiss-border-b flex items-center justify-between text-xs swiss-mono bg-[var(--sidebar)] shrink-0">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={isAllChecked}
              onChange={(e) => onToggleSelectAll(e.target.checked)}
              className="swiss-check"
            />
            <span className="font-bold">全选</span>
          </label>
          <span className="text-[var(--muted-foreground)]">|</span>
          <button
            onClick={() => onFilterChange('all')}
            className={`cursor-pointer ${
              activeFilter === 'all'
                ? 'font-bold underline decoration-[#FF3300] decoration-2 underline-offset-4'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            全部 {tracks.length}
          </button>
          <span className="text-[var(--muted-foreground)]">/</span>
          <button
            onClick={() => onFilterChange('ok')}
            className={`cursor-pointer ${
              activeFilter === 'ok'
                ? 'font-bold underline decoration-emerald-600 decoration-2 underline-offset-4 text-emerald-600'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            已合规 {okCount}
          </button>
          <span className="text-[var(--muted-foreground)]">/</span>
          <button
            onClick={() => onFilterChange('issues')}
            className={`cursor-pointer ${
              activeFilter === 'issues'
                ? 'font-bold underline decoration-[#FF3300] decoration-2 underline-offset-4 text-[#FF3300]'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            待规范 {needsFixCount}
          </button>
          {notDownloadedCount > 0 && (
            <>
              <span className="text-[var(--muted-foreground)]">/</span>
              <button
                onClick={() => onFilterChange('not_downloaded')}
                className={`cursor-pointer ${
                  activeFilter === 'not_downloaded'
                    ? 'font-bold underline decoration-zinc-500 decoration-2 underline-offset-4 text-zinc-500'
                    : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                }`}
              >
                未下载 {notDownloadedCount}
              </button>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onMoveUp}
            className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--card)] font-bold cursor-pointer"
            title="上移曲目序号"
          >
            ↑
          </button>
          <button
            onClick={onMoveDown}
            className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--card)] font-bold cursor-pointer"
            title="下移曲目序号"
          >
            ↓
          </button>
        </div>
      </div>

      {hideSource && checkedIds.size > 0 && (
        <div className="px-3.5 py-1.5 swiss-border-b flex items-center gap-2 text-[11px] swiss-mono bg-[var(--card)] shrink-0">
          <span className="font-bold">已选 {checkedIds.size} 首</span>
          <select
            value={manualDest}
            onChange={(event) => setManualDest(event.target.value)}
            className="bg-[var(--card)] border border-[var(--border)] px-1.5 py-0.5 text-[10px] max-w-[180px]"
            aria-label="选择目标分类"
          >
            {customFolders.map((folder) => (
              <option key={folder} value={folder}>
                {folder}
              </option>
            ))}
          </select>
          <button
            onClick={() => {
              onMoveToDest(manualDest);
              onToggleSelectAll(false);
            }}
            className="px-2 py-0.5 bg-[var(--active-bg)] text-[var(--active-fg)] font-bold cursor-pointer"
          >
            移入
          </button>
          <button
            onClick={() => onToggleSelectAll(false)}
            className="px-1.5 py-0.5 border border-[var(--border)] cursor-pointer"
          >
            清除
          </button>
        </div>
      )}

      {/* Track Queue Table */}
      <div tabIndex={0} role="region" aria-labelledby="queue-table-caption" className="table-wrapper panel-scroll">
        <table className="text-left text-xs">
          <caption id="queue-table-caption" className="sr-only">
            Audio queue with manual and automated classification
          </caption>
          <thead className="bg-[var(--sidebar)] text-[var(--muted-foreground)] swiss-mono uppercase">
            <tr>
              <th className="py-2 px-2 swiss-border-b font-semibold w-8">#</th>
              <th className="py-2 px-2 swiss-border-b font-semibold">曲目</th>
              <th className="py-2 px-2 swiss-border-b font-semibold col-folder">分类</th>
              <th className="py-2 px-2 swiss-border-b font-semibold col-secondary">帧</th>
              <th className="py-2 px-2 swiss-border-b font-semibold col-secondary">封面</th>
              <th className="py-2 px-3 swiss-border-b font-semibold text-right">状态</th>
            </tr>
          </thead>
          <tbody className="swiss-mono divide-y divide-[var(--border)]">
            {filteredTracks.map((t) => {
              const isSelected = t.id === selectedId;
              const isChecked = checkedIds.has(t.id);

              return (
                <tr
                  key={t.id}
                  onClick={() => onSelectTrack(t.id)}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? 'bg-[var(--background)] font-bold' : 'hover:bg-[var(--background)]/60'
                  }`}
                >
                  <td className="py-2 px-2 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => onToggleCheck(t.id, e.target.checked)}
                      className="swiss-check"
                    />
                  </td>
                  <th scope="row" className="py-2 px-2 font-semibold text-left whitespace-nowrap">
                    <span
                      className={`inline-block w-1.5 h-1.5 mr-1 ${
                        isSelected ? 'bg-[#FF3300]' : 'bg-transparent'
                      }`}
                    />
                    <span className={t.status === 'NOT_DOWNLOADED' ? 'text-[var(--muted-foreground)] font-normal' : ''}>
                      {t.seq} {t.title}
                    </span>
                    {t.status === 'NOT_DOWNLOADED' && (
                      <span className="ml-1 text-[10px] px-1 border border-[var(--border)] text-[var(--muted-foreground)] font-normal">
                        云端
                      </span>
                    )}
                  </th>
                  <td className="py-2 px-2 truncate max-w-[150px] col-folder">
                    <span className="text-[10px] text-[var(--muted-foreground)]" title={t.targetFolder}>
                      {t.targetFolder.replace(/^Albums\//, '').replace(/^Playlists\//, '')}
                    </span>
                  </td>
                  <td className="py-2 px-2 col-secondary">
                    {t.status === 'NOT_DOWNLOADED' ? (
                      <span className="text-[var(--muted-foreground)]">--</span>
                    ) : t.blockSize === null ? (
                      <span
                        className="text-[var(--muted-foreground)]"
                        title={t.encrypted ? '加密 .ncm：构建时解密后再复核真实帧大小' : '无法读取帧大小'}
                      >
                        {t.encrypted ? '待解密' : '—'}
                      </span>
                    ) : t.blockSize > 4096 ? (
                      <span className="text-[#FF3300] font-bold">{t.blockSize}!</span>
                    ) : (
                      <span className="text-emerald-600">{t.blockSize}</span>
                    )}
                  </td>
                  <td className="py-2 px-2 col-secondary">
                    {t.status === 'NOT_DOWNLOADED' ? (
                      <span className="text-[var(--muted-foreground)]">--</span>
                    ) : t.coverCompliant ? (
                      <span className="text-emerald-600">500p</span>
                    ) : t.coverRes === '无封面' ? (
                      <span
                        className="text-[#FF3300] font-bold"
                        title={t.encrypted ? '加密 .ncm：构建时解密后补封面' : '无内嵌封面'}
                      >
                        缺失
                      </span>
                    ) : (
                      <span
                        className="text-[#FF3300] font-bold"
                        title={t.coverReasons.join(' / ') || undefined}
                      >
                        {t.coverRes === '—' ? '—' : `${t.coverRes.split('×')[0]}p`}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right whitespace-nowrap">
                    {t.status === 'COMPLIANT' ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600">
                        <i className="inline-block w-1.5 h-1.5 bg-emerald-600 not-italic" />合规
                      </span>
                    ) : t.status === 'NEEDS_FIX' ? (
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] font-semibold ${
                          t.encrypted ? 'text-[var(--muted-foreground)]' : 'text-[#FF3300]'
                        }`}
                      >
                        <i
                          className={`inline-block w-1.5 h-1.5 not-italic ${
                            t.encrypted ? 'bg-[var(--muted-foreground)]' : 'bg-[#FF3300]'
                          }`}
                        />
                        {t.encrypted ? '待解密' : '待规范'}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
                        <i className="inline-block w-1.5 h-1.5 bg-[var(--muted-foreground)] not-italic" />
                        未下载
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Column Footer */}
      {!hideSource && (
      <div className="px-3.5 py-2.5 swiss-border-t bg-[var(--sidebar)] flex items-center justify-between text-xs swiss-mono shrink-0">
        <span className="truncate">
          NAMING: <strong className="font-semibold">{'{01..N}'} {'{Artist}'} - {'{Title}'}.flac / .mp3</strong>
        </span>
        <span
          className={`px-2 py-0.5 text-white font-bold shrink-0 ${
            needsFixCount === 0 && okCount > 0
              ? 'bg-emerald-600'
              : notDownloadedCount === tracks.length
              ? 'bg-zinc-600'
              : 'bg-[#FF3300]'
          }`}
        >
          {okCount > 0 ? `${okCount}/${tracks.length} 合规` : `${needsFixCount} 待规范`}
        </span>
      </div>
      )}
    </section>
  );
};
