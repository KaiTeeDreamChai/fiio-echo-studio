import React from 'react';

interface DesktopHeaderProps {
  onThemeToggle: () => void;
  onReset: () => void;
}

export const DesktopHeader: React.FC<DesktopHeaderProps> = ({ onThemeToggle, onReset }) => (
  <header className="h-14 shrink-0 border-b border-[var(--border)] bg-[var(--sidebar)] flex items-center gap-2.5 px-6">
    <span className="inline-block w-2.5 h-2.5 bg-[#FF3300]" />
    <div className="min-w-0">
      <div className="text-[11px] font-bold tracking-[0.14em] uppercase truncate">
        FiiO Echo Studio
      </div>
      <div className="text-[9px] text-[var(--muted-foreground)] swiss-mono">
        SNOWSKY 乐库工作台 · v1.2.0
      </div>
    </div>
    <div className="ml-auto flex items-center gap-1.5">
      <button
        onClick={onReset}
        title="重置当前队列"
        aria-label="重置当前队列"
        className="w-8 h-8 grid place-items-center border border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] cursor-pointer text-xs"
      >
        ↻
      </button>
      <button
        onClick={onThemeToggle}
        title="切换深色/浅色"
        aria-label="切换深色或浅色主题"
        className="w-8 h-8 grid place-items-center border border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] cursor-pointer text-xs"
      >
        ◐
      </button>
    </div>
  </header>
);
