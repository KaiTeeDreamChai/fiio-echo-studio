import React from 'react';
import type { TrackItem } from '../types/library';

interface LocalLibraryPanelProps {
  tracks: TrackItem[];
  isBuilding: boolean;
  buildProgress?: { done: number; total: number };
  canCancel?: boolean;
  onCancelBuild?: () => void;
  onBuildLibrary: () => void;
  onFatSort: () => void;
  onDotClean: () => void;
}

export const LocalLibraryPanel: React.FC<LocalLibraryPanelProps> = ({
  tracks,
  isBuilding,
  buildProgress,
  canCancel = false,
  onCancelBuild,
  onBuildLibrary,
  onFatSort,
  onDotClean,
}) => {
  // Aggregate Metrics & Folder Tree
  const folders: Record<string, TrackItem[]> = {};
  let totalBytes = 0;
  let albumCount = 0;
  let plCount = 0;

  tracks.forEach((t) => {
    totalBytes += t.sizeBytes;
    if (!folders[t.targetFolder]) {
      folders[t.targetFolder] = [];
      if (t.collectionType === 'album') albumCount++;
      else plCount++;
    }
    folders[t.targetFolder].push(t);
  });

  const downloadedCount = tracks.filter((t) => t.isDownloaded).length;
  const okCount = tracks.filter((t) => t.status === 'COMPLIANT').length;
  const allCompliant = downloadedCount > 0 && okCount === downloadedCount;

  return (
    <section id="col-03" className="col-span-12 md:col-span-6 xl:col-span-3 flex flex-col min-h-0 h-full">
      {/* Section Header */}
      <div className="px-3.5 py-2.5 swiss-border-b flex items-center justify-between bg-[var(--sidebar)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="swiss-mono text-xs font-bold px-1.5 py-0.5 bg-[var(--badge-bg)] text-[var(--badge-fg)] border border-[var(--border)]">
            03
          </span>
          <h2 className="text-xs font-bold uppercase tracking-wider">LOCAL LIBRARY</h2>
        </div>
        <span
          className={`swiss-mono text-xs font-bold ${
            allCompliant ? 'text-emerald-600' : 'text-amber-600'
          }`}
        >
          {allCompliant ? 'READY TO EXPORT' : 'STAGING'}
        </span>
      </div>

      {/* Panel Scrollable Content */}
      <div className="panel-scroll divide-y divide-[var(--border)]">
        {/* 1. Metrics Grid */}
        <div className="p-3.5">
          <div className="text-xs font-bold uppercase tracking-wider mb-2">LIBRARY METRICS</div>
          <div className="grid grid-cols-2 gap-2 swiss-mono text-xs">
            <div className="p-2 border border-[var(--border)] bg-[var(--background)]">
              <div className="text-[var(--muted-foreground)]">COLLECTIONS</div>
              <div className="text-sm font-bold mt-0.5">
                {albumCount} ALBUM / {plCount} PL
              </div>
            </div>
            <div className="p-2 border border-[var(--border)] bg-[var(--background)]">
              <div className="text-[var(--muted-foreground)]">TOTAL AUDIO SIZE</div>
              <div className="text-sm font-bold mt-0.5">
                {(totalBytes / 1024 / 1024).toFixed(1)} MB
              </div>
            </div>
            <div className="p-2 border border-[var(--border)] bg-[var(--background)]">
              <div className="text-[var(--muted-foreground)]">DOWNLOADED AUDIO</div>
              <div className="text-sm font-bold mt-0.5 text-emerald-600">
                {downloadedCount} / {tracks.length} ON DISK
              </div>
            </div>
            <div className="p-2 border border-[var(--border)] bg-[var(--background)]">
              <div className="text-[var(--muted-foreground)]">META MANIFEST</div>
              <div className="text-sm font-bold mt-0.5">echo_library.json</div>
            </div>
          </div>
        </div>

        {/* 2. Directory Structure Tree Preview */}
        <div className="p-3.5">
          <div className="flex items-center justify-between text-xs swiss-mono mb-2">
            <span className="font-bold">DIRECTORY STRUCTURE PREVIEW</span>
            <span className="text-[var(--muted-foreground)] text-xs">AUTOMATIC TREE</span>
          </div>
          <div className="bg-[var(--background)] border border-[var(--border)] p-2.5 swiss-mono text-xs space-y-1">
            <div className="font-bold text-[var(--foreground)] flex items-center gap-1.5 pb-1 border-b border-[var(--border)]">
              <span>📁</span> <span>FiiO_Echo_Library/</span>
              <span className="text-[var(--muted-foreground)] font-normal text-xs ml-auto">ROOT</span>
            </div>
            <div className="pl-2 pt-1 text-[var(--muted-foreground)] space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span>📄 <strong className="text-[#FF3300]">echo_library.json</strong></span>
                <span className="text-xs px-1 border border-[var(--border)] bg-[var(--card)]">CONFIG</span>
              </div>
              {Object.keys(folders).map((folderPath) => {
                const trks = folders[folderPath];
                return (
                  <div key={folderPath}>
                    <div className="font-semibold text-[var(--foreground)] flex items-center justify-between text-xs">
                      <span>📁 {folderPath}/</span>
                      <span className="text-emerald-600 font-bold text-xs">{trks.length} tracks</span>
                    </div>
                    <div className="pl-4 text-[var(--muted-foreground)] text-xs space-y-0.5 mt-0.5">
                      {trks.slice(0, 2).map((tk) => (
                        <div key={tk.id} className="truncate">
                          ├── 🎵 {tk.seq} {tk.artist} - {tk.title}
                          {tk.container === 'mp3' ? '.mp3' : '.flac'}
                        </div>
                      ))}
                      {trks.length > 2 && (
                        <div className="text-[var(--muted-foreground)] italic">
                          └── ... and {trks.length - 2} more (.flac/.mp3 + .lrc)
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 3. Optional TF Card Utilities */}
        <div className="p-3.5 bg-[var(--sidebar)]/40">
          <div className="text-xs font-bold uppercase tracking-wider mb-1">OPTIONAL: TF CARD UTILITY</div>
          <p className="text-xs text-[var(--muted-foreground)] mb-2 leading-relaxed">
            用户将乐库手动拷入播放器 TF 卡后，可在此一键修复 FAT32 物理目录槽位与清理 Mac 隐藏文件：
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={onFatSort}
              className="text-xs swiss-mono p-2 border border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] font-bold cursor-pointer text-left"
            >
              <div>⚡ FAT32 物理排序</div>
              <div className="text-[var(--muted-foreground)] font-normal text-xs mt-0.5">重排 TF 根目录</div>
            </button>
            <button
              onClick={onDotClean}
              className="text-xs swiss-mono p-2 border border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] font-bold cursor-pointer text-left"
            >
              <div>🧹 清除 macOS 幽灵</div>
              <div className="text-[var(--muted-foreground)] font-normal text-xs mt-0.5">dot_clean ._* 净化</div>
            </button>
          </div>
        </div>
      </div>

      {/* Master Build Action Buttons */}
      <div className="p-3 swiss-border-t bg-[var(--sidebar)] shrink-0 flex flex-col gap-2">
        {isBuilding && buildProgress && buildProgress.total > 0 && (
          <div className="flex items-center gap-2">
            <div className="h-1 flex-1 bg-[var(--border)] overflow-hidden">
              <div
                className="h-full bg-[#FF3300] transition-all duration-300"
                style={{
                  width: `${Math.min(100, Math.round((buildProgress.done / buildProgress.total) * 100))}%`,
                }}
              />
            </div>
            <span className="swiss-mono text-xs text-[var(--muted-foreground)] shrink-0">
              {buildProgress.done}/{buildProgress.total}
            </span>
            <button
              onClick={onCancelBuild}
              disabled={!canCancel}
              className="swiss-mono text-xs px-2 py-0.5 border border-[var(--border)] bg-[var(--card)] font-bold cursor-pointer hover:border-[#FF3300] disabled:opacity-40"
            >
              取消
            </button>
          </div>
        )}
        <div className="flex items-center gap-2">
        <button
          onClick={onBuildLibrary}
          disabled={isBuilding}
          className={`px-5 py-2.5 font-bold swiss-mono text-xs tracking-wider uppercase shrink-0 transition-colors ${
            isBuilding
              ? 'bg-[#FF3300]/60 text-white cursor-wait animate-pulse'
              : 'bg-[#FF3300] hover:bg-[#e02d00] active:bg-[#c92800] text-white cursor-pointer'
          }`}
          title="执行构建本地乐库"
        >
          {isBuilding ? '执行中...' : '执行'}
        </button>

        <button
          onClick={onBuildLibrary}
          disabled={isBuilding}
          className={`flex-1 py-2.5 px-3 font-bold swiss-mono text-xs tracking-wider uppercase flex items-center justify-between border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--background)] text-[var(--foreground)] transition-colors truncate ${
            isBuilding ? 'opacity-60 cursor-wait' : 'cursor-pointer hover:border-[#FF3300]'
          }`}
          title="构建本地乐库 (FiiO Echo 本地化目录与清单)"
        >
          <span className="truncate">
            {isBuilding
              ? `BUILDING ${buildProgress?.done ?? 0}/${buildProgress?.total ?? 0}...`
              : allCompliant
                ? '✓ REBUILD LOCAL LIBRARY'
                : 'BUILD LOCAL LIBRARY'}
          </span>
          <span className="shrink-0 ml-1 font-bold">→</span>
        </button>
        </div>
      </div>
    </section>
  );
};
