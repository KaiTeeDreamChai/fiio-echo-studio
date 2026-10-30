import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { RemoteAlbum, RemotePlaylist } from '../services/api';
import { fuzzyScore, fuzzyScoreAny, highlightRange } from '../lib/fuzzy';

type SourceMode = 'album' | 'playlist';

interface SourceSidebarProps {
  albums: RemoteAlbum[];
  playlists: RemotePlaylist[];
  isLoading: boolean;
  onRefresh: () => void;
  onApplyAlbum: (name: string) => void;
  onApplyPlaylist: (id: string) => void;
  onCreateFolder: (folder: string) => void;
  sourceInfo?: {
    dbPath: string | null;
    downloadDir: string;
    matched: number;
    sample: number;
  } | null;
}

interface MatchItem {
  key: string;
  name: string;
  meta: string;
  score: number;
  createTime?: number;
  albumName?: string;
  playlistId?: string;
}

const formatDate = (timestamp?: number): string => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
};

const Highlight: React.FC<{ text: string; query: string }> = ({ text, query }) => {
  const range = highlightRange(text, query);
  if (!range) return <>{text}</>;
  return (
    <>
      {text.slice(0, range[0])}
      <mark className="bg-transparent font-bold text-[#FF3300]">
        {text.slice(range[0], range[1])}
      </mark>
      {text.slice(range[1])}
    </>
  );
};

export const SourceSidebar: React.FC<SourceSidebarProps> = ({
  albums,
  playlists,
  isLoading,
  onRefresh,
  onApplyAlbum,
  onApplyPlaylist,
  onCreateFolder,
  sourceInfo,
}) => {
  const [mode, setMode] = useState<SourceMode>('album');
  const [query, setQuery] = useState('');
  const [creatorQuery, setCreatorQuery] = useState('');
  const [creatorOpen, setCreatorOpen] = useState(false);
  const [relationTab, setRelationTab] = useState<'all' | 'created' | 'favorited'>('all');
  const [selectedAlbum, setSelectedAlbum] = useState('');
  const [selectedPlaylist, setSelectedPlaylist] = useState('');
  const [creating, setCreating] = useState(false);
  const [newFolder, setNewFolder] = useState('');
  const creatorBoxRef = useRef<HTMLDivElement>(null);
  const creatorFilter = creatorQuery.trim();

  // 作者/歌手候选（按当前来源类型聚合）
  const creators = useMemo(() => {
    const counter = new Map<string, number>();
    if (mode === 'album') {
      albums.forEach((album) => {
        const name = (album.main_artist || '').trim();
        if (name) counter.set(name, (counter.get(name) ?? 0) + 1);
      });
    } else {
      playlists.forEach((playlist) => {
        const name = (playlist.creator || '').trim();
        if (name) counter.set(name, (counter.get(name) ?? 0) + 1);
      });
    }
    return Array.from(counter.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh'));
  }, [mode, albums, playlists]);

  const relationCounts = useMemo(
    () => ({
      created: playlists.filter((playlist) => playlist.relation === 'created').length,
      favorited: playlists.filter((playlist) => playlist.relation === 'favorited').length,
    }),
    [playlists],
  );

  const creatorSuggestions = useMemo(() => {
    const keyword = creatorQuery.trim();
    const pool = creators;
    if (!keyword) return pool.slice(0, 8);
    return pool
      .map((entry) => ({ entry, score: fuzzyScore(keyword, entry.name) }))
      .filter((row) => row.score !== null)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 8)
      .map((row) => row.entry);
  }, [creators, creatorQuery]);

  const items = useMemo<MatchItem[]>(() => {
    const keyword = query.trim();

    if (mode === 'album') {
      return albums
        .map((album) => {
          const score = fuzzyScoreAny(keyword, [
            { text: album.name, weight: 1 },
            { text: album.main_artist, weight: 0.7 },
          ]);
          if (score === null) return null;
          if (creatorFilter && fuzzyScore(creatorFilter, album.main_artist) === null) return null;
          return {
            key: album.name,
            name: album.name,
            meta: `${album.track_count} 首 · ${album.main_artist || '未知艺术家'}`,
            score,
            albumName: album.name,
          } as MatchItem;
        })
        .filter((item): item is MatchItem => item !== null)
        .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, 'zh'));
    }

    return playlists
      .map((playlist) => {
        if (relationTab !== 'all' && playlist.relation !== relationTab) return null;
        const score = fuzzyScoreAny(keyword, [
          { text: playlist.name, weight: 1 },
          { text: playlist.creator, weight: 0.7 },
        ]);
        if (score === null) return null;
        if (creatorFilter && fuzzyScore(creatorFilter, playlist.creator) === null) return null;
        const created = formatDate(playlist.create_time);
        return {
          key: playlist.id,
          name: playlist.name,
          meta: `${playlist.track_count} 首 · ${playlist.creator || '网易云用户'}${created ? ` · ${created}` : ''}`,
          score,
          createTime: playlist.create_time ?? 0,
          playlistId: playlist.id,
        } as MatchItem;
      })
      .filter((item): item is MatchItem => item !== null)
      .sort(
        (a, b) =>
          b.score - a.score ||
          (b.createTime ?? 0) - (a.createTime ?? 0) ||
          a.name.localeCompare(b.name, 'zh'),
      );
  }, [mode, albums, playlists, query, creatorFilter, relationTab]);

  useEffect(() => {
    if (mode === 'album') {
      if (!items.some((item) => item.albumName === selectedAlbum)) {
        setSelectedAlbum(items[0]?.albumName ?? '');
      }
    } else if (!items.some((item) => item.playlistId === selectedPlaylist)) {
      setSelectedPlaylist(items[0]?.playlistId ?? '');
    }
  }, [items, mode, selectedAlbum, selectedPlaylist]);

  useEffect(() => {
    const onDocMouseDown = (event: MouseEvent) => {
      if (!creatorBoxRef.current?.contains(event.target as Node)) setCreatorOpen(false);
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, []);

  const total = mode === 'album' ? albums.length : playlists.length;
  const selectedKey = mode === 'album' ? selectedAlbum : selectedPlaylist;
  const canImport = Boolean(selectedKey);

  const switchMode = (next: SourceMode) => {
    if (next === mode) return;
    setMode(next);
    setQuery('');
    setCreatorQuery('');
    setRelationTab('all');
    setCreatorOpen(false);
  };

  const handleImport = () => {
    if (mode === 'album' && selectedAlbum) onApplyAlbum(selectedAlbum);
    if (mode === 'playlist' && selectedPlaylist) onApplyPlaylist(selectedPlaylist);
  };

  const handleCreateFolder = () => {
    const name = newFolder.trim();
    if (!name) return;
    const folder =
      name.startsWith('Albums/') || name.startsWith('Playlists/') ? name : `Playlists/${name}`;
    onCreateFolder(folder);
    setNewFolder('');
    setCreating(false);
  };

  return (
    <aside className="w-[272px] shrink-0 border-r border-[var(--border)] bg-[var(--sidebar)] flex flex-col min-h-0">
      <div className="px-3.5 py-2.5 border-b border-[var(--border)] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="swiss-mono text-xs font-bold px-1.5 py-0.5 bg-[var(--badge-bg)] text-[var(--badge-fg)]">
            来源
          </span>
          <span className="swiss-mono text-[10px] text-[var(--muted-foreground)]">
            {total} {mode === 'album' ? '张专辑' : '个歌单'}
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="swiss-mono text-[10px] underline underline-offset-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] disabled:opacity-40 cursor-pointer"
          title={
            sourceInfo?.dbPath
              ? `重新扫描本地数据库\n${sourceInfo.dbPath}\n下载目录: ${sourceInfo.downloadDir}`
              : '重新扫描本地网易云数据库'
          }
        >
          {isLoading ? '扫描中…' : '重新探测'}
        </button>
      </div>

      <div className="p-3 space-y-2 shrink-0">
        <div className="grid grid-cols-2 border border-[var(--border)] bg-[var(--card)] swiss-mono text-[11px] font-bold">
          <button
            onClick={() => switchMode('album')}
            className={`py-1.5 cursor-pointer transition-colors ${
              mode === 'album'
                ? 'bg-[var(--active-bg)] text-[var(--active-fg)]'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            已下专辑
          </button>
          <button
            onClick={() => switchMode('playlist')}
            className={`py-1.5 cursor-pointer transition-colors border-l border-[var(--border)] ${
              mode === 'playlist'
                ? 'bg-[var(--active-bg)] text-[var(--active-fg)]'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            歌单列表
          </button>
        </div>

        {mode === 'playlist' && (
          <div className="flex items-center gap-2 swiss-mono text-[9px] text-[var(--muted-foreground)]">
            {[
              ['all', '全部', playlists.length],
              ['created', '我创建', relationCounts.created],
              ['favorited', '我收藏', relationCounts.favorited],
            ].map(([key, label, count]) => (
              <button
                key={String(key)}
                onClick={() => setRelationTab(key as 'all' | 'created' | 'favorited')}
                className={`cursor-pointer transition-colors ${
                  relationTab === key
                    ? 'text-[var(--foreground)] font-bold underline decoration-[#FF3300] decoration-1 underline-offset-4'
                    : 'hover:text-[var(--foreground)]'
                }`}
              >
                {label} {count}
              </button>
            ))}
          </div>
        )}

        <div className="relative">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={mode === 'album' ? '搜索专辑 / 歌手' : '搜索歌单 / 作者'}
            aria-label="搜索专辑或歌单"
            className="w-full h-8 bg-[var(--card)] border border-[var(--border)] px-2 pr-7 text-xs focus:outline-none focus:border-[#FF3300]"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 grid place-items-center text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer"
              aria-label="清空搜索"
            >
              ×
            </button>
          )}
        </div>

        <div className="relative" ref={creatorBoxRef}>
          <input
            value={creatorQuery}
            onChange={(event) => {
              setCreatorQuery(event.target.value);
              setCreatorOpen(true);
            }}
            onFocus={() => setCreatorOpen(true)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && creatorSuggestions[0]) {
                event.preventDefault();
                setCreatorQuery(creatorSuggestions[0].name);
                setCreatorOpen(false);
              }
              if (event.key === 'Escape') setCreatorOpen(false);
            }}
            placeholder={mode === 'album' ? '按歌手筛选（模糊）' : '按创建人筛选（模糊）'}
            aria-label="按创建人或歌手筛选"
            className="w-full h-8 bg-[var(--card)] border border-[var(--border)] px-2 pr-7 text-xs focus:outline-none focus:border-[#FF3300]"
          />
          {creatorQuery && (
            <button
              onClick={() => {
                setCreatorQuery('');
                setCreatorOpen(false);
              }}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 grid place-items-center text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer"
              aria-label="清空作者筛选"
            >
              ×
            </button>
          )}
          {creatorOpen && creatorSuggestions.length > 0 && (
            <div className="absolute z-20 left-0 right-0 mt-1 border border-[var(--border)] bg-[var(--card)] shadow-lg max-h-56 overflow-y-auto">
              {creatorSuggestions.map((entry) => (
                <button
                  key={entry.name}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    setCreatorQuery(entry.name);
                    setCreatorOpen(false);
                  }}
                  className="w-full text-left px-2 py-1.5 text-[11px] flex items-center justify-between gap-2 hover:bg-[var(--sidebar)] cursor-pointer"
                >
                  <span className="truncate">
                    <Highlight text={entry.name} query={creatorQuery} />
                  </span>
                  <span className="swiss-mono text-[9px] text-[var(--muted-foreground)] shrink-0">
                    {entry.count}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

      </div>

      <div className="px-3.5 py-1 flex items-center justify-between border-y border-[var(--border)] swiss-mono text-[9px] text-[var(--muted-foreground)] shrink-0">
        <span>
          {query.trim()
            ? '匹配结果'
            : mode === 'playlist'
              ? relationTab === 'created'
                ? '我创建的歌单'
                : relationTab === 'favorited'
                  ? '我收藏的歌单'
                  : '按创建时间'
              : '全部'}
        </span>
        <span>
          {items.length} / {total}
        </span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {items.length === 0 ? (
          <div className="p-4 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
            没有匹配的{mode === 'album' ? '专辑' : '歌单'}。
            <button
              onClick={() => {
                setQuery('');
                setCreatorQuery('');
              }}
              className="ml-1 underline underline-offset-2 text-[var(--foreground)] cursor-pointer"
            >
              清除筛选
            </button>
          </div>
        ) : (
          items.map((item) => {
            const active = mode === 'album' ? item.albumName === selectedAlbum : item.playlistId === selectedPlaylist;
            return (
              <button
                key={item.key}
                onClick={() => {
                  if (mode === 'album') setSelectedAlbum(item.albumName ?? '');
                  else setSelectedPlaylist(item.playlistId ?? '');
                }}
                onDoubleClick={() => {
                  if (mode === 'album' && item.albumName) onApplyAlbum(item.albumName);
                  if (mode === 'playlist' && item.playlistId) onApplyPlaylist(item.playlistId);
                }}
                className={`w-full text-left px-3.5 py-2 border-b border-[var(--border)]/40 cursor-pointer transition-colors ${
                  active
                    ? 'bg-[var(--card)] shadow-[inset_2px_0_0_#FF3300]'
                    : 'hover:bg-[var(--card)]'
                }`}
              >
                <div className="text-[11px] font-semibold truncate">
                  <Highlight text={item.name} query={query} />
                </div>
                <div className="swiss-mono text-[9px] text-[var(--muted-foreground)] mt-0.5 truncate">
                  <Highlight text={item.meta} query={query} />
                </div>
              </button>
            );
          })
        )}
      </div>

      <div className="p-3 border-t border-[var(--border)] shrink-0 space-y-2">
        <button
          onClick={handleImport}
          disabled={!canImport}
          className="w-full py-2 bg-[#FF3300] text-white text-[11px] font-bold swiss-mono disabled:opacity-40 cursor-pointer hover:bg-[#e02d00] transition-colors"
        >
          {mode === 'album' ? '导入此专辑 →' : '导入此歌单 →'}
        </button>

        {sourceInfo && (
          <div
            className="text-[8px] swiss-mono text-[var(--muted-foreground)] truncate pt-1"
            title={`数据库: ${sourceInfo.dbPath ?? '未找到'}\n下载目录: ${sourceInfo.downloadDir}\n本地文件抽样匹配: ${sourceInfo.matched}/${sourceInfo.sample}`}
          >
            库 {sourceInfo.dbPath ? sourceInfo.dbPath.split('/').pop() : '未找到'} · 下载{' '}
            {sourceInfo.downloadDir.split('/').pop() || '未识别'}
          </div>
        )}

        {creating ? (
          <div className="flex items-center gap-1">
            <input
              value={newFolder}
              onChange={(event) => setNewFolder(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handleCreateFolder();
                if (event.key === 'Escape') setCreating(false);
              }}
              autoFocus
              placeholder="分类名称"
              className="flex-1 h-7 bg-[var(--card)] border border-[var(--border)] px-1.5 text-[10px] focus:outline-none"
            />
            <button
              onClick={handleCreateFolder}
              className="text-[10px] px-2 h-7 bg-[var(--active-bg)] text-[var(--active-fg)] font-bold cursor-pointer"
            >
              添加
            </button>
            <button
              onClick={() => setCreating(false)}
              className="text-[10px] px-1.5 h-7 border border-[var(--border)] cursor-pointer"
            >
              ×
            </button>
          </div>
        ) : (
          <button
            onClick={() => setCreating(true)}
            className="w-full text-center text-[10px] swiss-mono text-[var(--muted-foreground)] underline underline-offset-2 hover:text-[var(--foreground)] cursor-pointer"
          >
            ＋ 手动创建分类
          </button>
        )}
      </div>
    </aside>
  );
};
