import React from 'react';

interface TelemetryFooterProps {
  logMessage: string;
  okCount: number;
  totalCount: number;
}

export const TelemetryFooter: React.FC<TelemetryFooterProps> = ({
  logMessage,
  okCount,
  totalCount,
}) => {
  const pct = totalCount > 0 ? Math.round((okCount / totalCount) * 100) : 0;
  const isAllOk = totalCount > 0 && okCount === totalCount;

  return (
    <footer className="grid grid-cols-12 swiss-border-t bg-[var(--sidebar)] text-xs swiss-mono shrink-0">
      <div className="col-span-12 md:col-span-8 py-2 px-4 swiss-border-r flex items-center gap-3 overflow-hidden">
        <span className="px-1.5 py-0.5 bg-[var(--badge-bg)] text-[var(--badge-fg)] border border-[var(--border)] font-bold shrink-0">
          TELEMETRY
        </span>
        <span className="truncate text-[var(--muted-foreground)]">
          {logMessage}
        </span>
      </div>
      <div className="col-span-12 md:col-span-4 py-2 px-4 flex items-center justify-between gap-4">
        <div className="w-full bg-[var(--background)] h-2 border border-[var(--border)] overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              isAllOk ? 'bg-emerald-600' : 'bg-[#FF3300]'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="font-bold shrink-0">
          {okCount}/{totalCount} OK
        </span>
      </div>
    </footer>
  );
};
