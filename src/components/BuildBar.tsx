import React, { useEffect, useRef, useState } from 'react';
import type { TrackItem } from '../types/library';

interface BuildBarProps {
  tracks: TrackItem[];
  libraryRoot: string;
  isBuilding: boolean;
  progress: { done: number; total: number };
  canCancel: boolean;
  onBrowse: () => void;
  onBuild: () => void;
  onCancel: () => void;
  onFatSort: () => void;
  onDotClean: () => void;
}

export const BuildBar: React.FC<BuildBarProps> = ({
  tracks,
  libraryRoot,
  isBuilding,
  progress,
  canCancel,
  onBrowse,
  onBuild,
  onCancel,
  onFatSort,
  onDotClean,
}) => {
  const [toolsOpen, setToolsOpen] = useState(false);
  const toolsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocMouseDown = (event: MouseEvent) => {
      if (!toolsRef.current?.contains(event.target as Node)) setToolsOpen(false);
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, []);

  const total = tracks.length;
  const totalBytes = tracks.reduce((sum, track) => sum + (track.sizeBytes || 0), 0);
  const compliant = tracks.filter((track) => track.status === 'COMPLIANT').length;
  const percent =
    progress.total > 0 ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;

  return (
    <div className="h-16 shrink-0 border-t border-[var(--border)] bg-[var(--sidebar)] flex items-center gap-5 px-5">
      <div className="swiss-mono text-[11px] whitespace-nowrap">
        <b className="font-bold">{total}</b> 首
        <span className="mx-1.5 text-[var(--muted-foreground)]">·</span>
        <b className="font-bold">{(totalBytes / 1024 / 1024 / 1024).toFixed(2)}</b> GB
        <span className="mx-1.5 text-[var(--muted-foreground)]">·</span>
        <b className={`font-bold ${compliant > 0 ? 'text-emerald-600' : 'text-[var(--muted-foreground)]'}`}>
          {compliant}
        </b>{' '}
        已合规
      </div>

      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span className="swiss-mono text-[9px] text-[var(--muted-foreground)] shrink-0">输出</span>
        <button
          onClick={onBrowse}
          className="flex-1 min-w-0 text-left swiss-mono text-[10px] truncate border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 hover:border-[#FF3300] cursor-pointer"
          title="点击选择输出目录"
        >
          {libraryRoot}
        </button>
        <button
          onClick={onBrowse}
          className="shrink-0 text-[9px] swiss-mono underline underline-offset-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer"
        >
          更改
        </button>
      </div>

      {isBuilding && progress.total > 0 && (
        <div className="w-36 shrink-0">
          <div className="h-1 w-full bg-[var(--border)] overflow-hidden">
            <div className="h-full bg-[#FF3300] transition-all duration-300" style={{ width: `${percent}%` }} />
          </div>
          <div className="swiss-mono text-[9px] text-[var(--muted-foreground)] mt-1 text-right">
            {progress.done} / {progress.total}
          </div>
        </div>
      )}

      <div className="relative shrink-0" ref={toolsRef}>
        <button
          onClick={() => setToolsOpen((open) => !open)}
          className="swiss-mono text-[10px] border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 hover:border-[#FF3300] cursor-pointer"
        >
          TF 卡工具 ▾
        </button>
        {toolsOpen && (
          <div className="absolute right-0 bottom-full mb-1 w-48 border border-[var(--border)] bg-[var(--card)] shadow-lg z-30">
            <button
              onClick={() => {
                setToolsOpen(false);
                onFatSort();
              }}
              className="w-full text-left px-3 py-2 text-[10px] swiss-mono hover:bg-[var(--sidebar)] cursor-pointer border-b border-[var(--border)]/50"
            >
              FAT32 目录排序
            </button>
            <button
              onClick={() => {
                setToolsOpen(false);
                onDotClean();
              }}
              className="w-full text-left px-3 py-2 text-[10px] swiss-mono hover:bg-[var(--sidebar)] cursor-pointer"
            >
              清理 macOS 幽灵文件
            </button>
          </div>
        )}
      </div>

      {isBuilding && canCancel && (
        <button
          onClick={onCancel}
          className="shrink-0 swiss-mono text-[10px] border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 hover:border-[#FF3300] cursor-pointer"
        >
          取消
        </button>
      )}

      <button
        onClick={onBuild}
        disabled={isBuilding || total === 0}
        className="shrink-0 bg-[#FF3300] hover:bg-[#e02d00] disabled:opacity-40 disabled:cursor-not-allowed text-white swiss-mono text-[11px] font-bold px-4 py-2 transition-colors cursor-pointer"
      >
        {isBuilding ? '构建中…' : '开始构建'}
      </button>
    </div>
  );
};
