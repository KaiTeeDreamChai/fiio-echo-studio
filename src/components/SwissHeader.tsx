import React from 'react';
import type { LayoutTier } from '../types/library';

interface SwissHeaderProps {
  layoutTier: LayoutTier;
  windowWidth: number;
  windowHeight: number;
  libraryRoot: string;
  isBrowsing?: boolean;
  onLibraryRootChange: (path: string) => void;
  onBrowseFolder: () => void;
  onThemeToggle: () => void;
  onReset: () => void;
}

export const SwissHeader: React.FC<SwissHeaderProps> = ({
  layoutTier,
  windowWidth,
  windowHeight,
  libraryRoot,
  isBrowsing = false,
  onLibraryRootChange,
  onBrowseFolder,
  onThemeToggle,
  onReset,
}) => {
  const tierLabel = {
    TIER_1_DESKTOP: '3-COL WORKBENCH',
    TIER_2_SPLIT: 'SPLIT VIEW (2-COL)',
    TIER_3_MOBILE: 'MOBILE VIEW (1-COL)',
  }[layoutTier];

  const tierBadgeClass = {
    TIER_1_DESKTOP: 'swiss-mono text-xs px-2 py-0.5 border border-[var(--border)] bg-[var(--card)] font-bold',
    TIER_2_SPLIT: 'swiss-mono text-xs px-2 py-0.5 bg-[#FF3300] text-white font-bold',
    TIER_3_MOBILE: 'swiss-mono text-xs px-2 py-0.5 bg-emerald-600 text-white font-bold',
  }[layoutTier];

  return (
    <header className="grid grid-cols-12 swiss-border-b bg-[var(--sidebar)] shrink-0">
      {/* Brand Title */}
      <div className="col-span-12 md:col-span-5 xl:col-span-4 px-4 py-2.5 swiss-border-r flex items-center justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 bg-[#FF3300] shrink-0" />
            <h1 className="font-bold tracking-tight text-sm uppercase truncate">SNOWSKY / FIIO ECHO STUDIO</h1>
          </div>
          <p className="text-xs text-[var(--muted-foreground)] swiss-mono truncate">
            LOCAL LIBRARY NORMALIZER // v0.3 WORKBENCH
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <span className={tierBadgeClass}>{tierLabel}</span>
        </div>
      </div>

      {/* Center Spec Display */}
      <div className="hidden xl:flex xl:col-span-5 px-4 py-2.5 swiss-border-r items-center justify-between">
        <div className="grid grid-cols-3 gap-4 w-full swiss-mono">
          <div>
            <div className="text-xs text-[var(--muted-foreground)]">TARGET PROFILE</div>
            <div className="text-xs font-bold mt-0.5">
              FIIO ECHO <span className="font-normal text-[var(--muted-foreground)]">(FLAC ≤4096)</span>
            </div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted-foreground)]">COVER SPEC</div>
            <div className="text-xs font-bold mt-0.5">
              500×500 <span className="font-normal text-[var(--muted-foreground)]">YUV420P</span>
            </div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted-foreground)]">OUTPUT STRUCTURE</div>
            <div className="text-xs font-bold mt-0.5">ALBUMS / PLAYLISTS</div>
          </div>
        </div>
      </div>

      {/* Local Library Root Path Setting */}
      <div className="col-span-12 md:col-span-7 xl:col-span-3 px-4 py-2 flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-[var(--muted-foreground)] swiss-mono flex items-center gap-1">
            <span>LOCAL LIBRARY ROOT:</span>
            {windowWidth > 0 && (
              <span className="text-[var(--foreground)] font-bold ml-auto hidden sm:inline">
                {windowWidth} × {windowHeight}px
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 mt-0.5">
            <input
              type="text"
              value={libraryRoot}
              onChange={(e) => onLibraryRootChange(e.target.value)}
              className="bg-[var(--background)] border border-[var(--border)] px-1.5 py-0.5 text-xs swiss-mono w-full truncate focus:outline-none"
            />
            <button
              onClick={onBrowseFolder}
              disabled={isBrowsing}
              className={`text-xs swiss-mono px-2 py-0.5 border border-[var(--border)] font-bold transition-colors shrink-0 ${
                isBrowsing
                  ? 'bg-[#FF3300] text-white opacity-90 cursor-wait animate-pulse'
                  : 'bg-[var(--card)] hover:border-[#FF3300] hover:text-[#FF3300] cursor-pointer'
              }`}
              title="打开系统文件夹选择窗口"
            >
              {isBrowsing ? 'OPENING...' : 'BROWSE'}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0 ml-1">
          <button
            onClick={onThemeToggle}
            className="text-xs swiss-mono px-1.5 py-1 border border-[var(--border)] hover:bg-[var(--background)] transition-colors cursor-pointer"
            title="切换深色/浅色模式"
          >
            ◐
          </button>
          <button
            onClick={onReset}
            className="text-xs swiss-mono px-1.5 py-1 border border-[var(--border)] hover:bg-[var(--background)] transition-colors cursor-pointer"
            title="重置测试状态"
          >
            ↻
          </button>
        </div>
      </div>
    </header>
  );
};
