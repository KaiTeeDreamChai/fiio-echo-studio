import React, { useState } from 'react';
import type { TrackItem } from '../types/library';

interface InspectorPanelProps {
  track: TrackItem;
  onNormalizeTrack: (id: number) => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  track,
  onNormalizeTrack,
}) => {
  const [lrcMode, setLrcMode] = useState<'clean' | 'raw'>('clean');

  const isCompliant = track.status === 'COMPLIANT';
  const needsAudioReframe = track.blockSize > 4096 || track.srcExt === '.ncm';
  const needsCoverNorm = track.coverRes !== '500×500' || track.coverYuv !== '4:2:0' || track.coverType !== 3;

  return (
    <section id="col-02" className="col-span-12 md:col-span-6 xl:col-span-4 swiss-border-r flex flex-col min-h-0 h-full">
      {/* Section Header */}
      <div className="px-3.5 py-2.5 swiss-border-b flex items-center justify-between bg-[var(--sidebar)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="swiss-mono text-xs font-bold px-1.5 py-0.5 bg-[var(--badge-bg)] text-[var(--badge-fg)] border border-[var(--border)]">
            02
          </span>
          <h2 className="text-xs font-bold uppercase tracking-wider">SPECIFICATION MATRIX</h2>
        </div>
        <span className="swiss-mono text-xs font-bold text-[#FF3300]">
          TRACK #{track.seq}
        </span>
      </div>

      {/* Inspector Body */}
      <div className="panel-scroll divide-y divide-[var(--border)]">
        {track.status === 'NOT_DOWNLOADED' && (
          <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 text-xs swiss-mono text-amber-600 dark:text-amber-400 flex items-start gap-2">
            <span className="shrink-0 font-bold">⚠️ [未下载音频]</span>
            <span>该曲目目前仅存在于网易云歌单中，本地未下载音频文件。请先在网易云客户端中下载该曲目，刷新后即可标准化并写入播放器乐库。</span>
          </div>
        )}

        {/* Track Summary & Cover Art Preview */}
        <div className="p-3.5 grid grid-cols-12 gap-3.5 items-center">
          <div className="col-span-4 aspect-square max-w-[110px] border border-[var(--border)] bg-[var(--sidebar)] relative flex flex-col justify-between p-1.5 overflow-hidden">
            <div className="flex justify-between items-start z-10">
              <span className="swiss-mono text-xs font-bold px-1 bg-[var(--card)] border border-[var(--border)]">
                TYPE {track.coverType}
              </span>
            </div>
            <div className="my-auto flex items-center justify-center">
              <div className="w-9 h-9 rounded-full bg-[#FF3300] opacity-90" />
              <div className="w-9 h-9 border-2 border-[var(--foreground)] -ml-3" />
            </div>
            <div className="z-10 bg-[var(--card)] px-1 py-0.5 border border-[var(--border)] text-center">
              <div className="swiss-mono text-xs font-bold truncate">
                {track.coverRes}
              </div>
            </div>
          </div>

          <div className="col-span-8 space-y-1 min-w-0">
            <div className="swiss-mono text-xs text-[var(--muted-foreground)] truncate">
              SOURCE: {track.artist} - {track.title}{track.srcExt}
            </div>
            <h3 className="text-sm font-bold tracking-tight leading-snug truncate">
              {track.seq} {track.artist} - {track.title}.flac
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] truncate">
              Target: {track.targetFolder}/{track.seq} {track.artist} - {track.title}.flac
            </p>
            <div className="pt-1 flex flex-wrap gap-1.5 swiss-mono text-xs">
              <span className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)]">
                {track.pcm}
              </span>
              <span className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)]">
                UTF-8 CRLF
              </span>
              <span className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)]">
                {(track.sizeBytes / 1024 / 1024).toFixed(1)} MB
              </span>
            </div>
          </div>
        </div>

        {/* 1. FLAC Stream & Frame Buffer */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">A. 音频流与帧大小 (FLAC STREAMINFO)</span>
            <span
              className={`swiss-mono text-xs px-1.5 py-0.5 font-bold ${
                needsAudioReframe ? 'bg-[#FF3300] text-white' : 'bg-emerald-600 text-white'
              }`}
            >
              {needsAudioReframe ? (track.srcExt === '.ncm' ? 'DECRYPT + REFRAME' : 'REFRAME REQUIRED') : 'COMPLIANT (≤4096)'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 swiss-mono text-xs bg-[var(--background)] p-2 border border-[var(--border)]">
            <div>
              <div className="text-[var(--muted-foreground)]">PCM SPEC</div>
              <div className="font-bold mt-0.5">{track.pcm}</div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">CURRENT BLOCK</div>
              <div className={`font-bold mt-0.5 ${needsAudioReframe ? 'text-[#FF3300]' : 'text-emerald-600'}`}>
                {track.blockSize} {needsAudioReframe ? '(ERR)' : '(OK)'}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">TARGET BLOCK</div>
              <div className="font-bold text-emerald-600 mt-0.5">4096 (SAFE)</div>
            </div>
          </div>
        </div>

        {/* 2. Album Cover Art Spec */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">B. 专辑封面格式规范 (PICTURE BLOCK)</span>
            <span
              className={`swiss-mono text-xs px-1.5 py-0.5 font-bold ${
                needsCoverNorm ? 'bg-[#FF3300] text-white' : 'bg-emerald-600 text-white'
              }`}
            >
              {needsCoverNorm ? 'CONVERT 4:2:0' : 'COMPLIANT JPEG'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 swiss-mono text-xs bg-[var(--background)] p-2 border border-[var(--border)]">
            <div>
              <div className="text-[var(--muted-foreground)]">RESOLUTION</div>
              <div className="font-bold mt-0.5">
                {needsCoverNorm ? `${track.coverRes.split('×')[0]} → 500px` : '500×500 (OK)'}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">CHROMA SUB</div>
              <div className={`font-bold mt-0.5 ${needsCoverNorm ? 'text-[#FF3300]' : 'text-emerald-600'}`}>
                {track.coverYuv} {needsCoverNorm ? '→ 4:2:0' : '(OK)'}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">ENCODING</div>
              <div className="font-bold mt-0.5">Baseline JPG</div>
            </div>
          </div>
        </div>

        {/* 3. Companion LRC Sanitizer */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">C. 伴随歌词清洗 (.LRC SANITIZER)</span>
            <div className="flex items-center gap-1 swiss-mono text-xs">
              <button
                onClick={() => setLrcMode('raw')}
                className={`px-1.5 py-0.5 border border-[var(--border)] cursor-pointer transition-colors ${
                  lrcMode === 'raw'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] font-bold shadow-sm'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                }`}
              >
                RAW
              </button>
              <button
                onClick={() => setLrcMode('clean')}
                className={`px-1.5 py-0.5 border border-[var(--border)] cursor-pointer transition-colors ${
                  lrcMode === 'clean'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] font-bold shadow-sm'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                }`}
              >
                CLEANED
              </button>
            </div>
          </div>
          <pre className="swiss-mono text-xs p-2 bg-[var(--background)] border border-[var(--border)] overflow-x-auto leading-relaxed min-h-[76px]">
            {lrcMode === 'raw' ? track.rawLrc : track.cleanLrc}
          </pre>
        </div>
      </div>

      {/* Column Footer Action */}
      <div className="px-3.5 py-2.5 swiss-border-t bg-[var(--sidebar)] flex items-center justify-between shrink-0">
        <span className="swiss-mono text-xs text-[var(--muted-foreground)] truncate mr-2">
          {isCompliant
            ? 'STATUS: 100% HARDWARE COMPLIANT'
            : track.status === 'NOT_DOWNLOADED'
            ? 'STATUS: CLOUD ONLY (NOT DOWNLOADED)'
            : 'STATUS: PENDING NORMALIZATION'}
        </span>
        <button
          onClick={() => onNormalizeTrack(track.id)}
          disabled={isCompliant || track.status === 'NOT_DOWNLOADED'}
          className={`swiss-mono text-xs font-bold px-3 py-1 border transition-colors shrink-0 ${
            isCompliant
              ? 'border-[var(--border)] text-[var(--muted-foreground)] cursor-not-allowed'
              : track.status === 'NOT_DOWNLOADED'
              ? 'border-[var(--border)] text-[var(--muted-foreground)] bg-[var(--card)] cursor-not-allowed'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] hover:text-[#FF3300] cursor-pointer'
          }`}
        >
          {isCompliant ? '✓ COMPLIANT' : track.status === 'NOT_DOWNLOADED' ? 'NOT DOWNLOADED' : 'NORMALIZE TRACK →'}
        </button>
      </div>
    </section>
  );
};
