import React, { useState } from 'react';
import type { TrackItem } from '../types/library';

interface InspectorPanelProps {
  track: TrackItem;
  isBuilding?: boolean;
  isNormalizing?: boolean;
  onNormalizeTrack: (id: number) => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  track,
  isBuilding = false,
  isNormalizing = false,
  onNormalizeTrack,
}) => {
  const [lrcMode, setLrcMode] = useState<'clean' | 'raw'>('clean');

  const isCompliant = track.status === 'COMPLIANT';
  const isCloudOnly = track.status === 'NOT_DOWNLOADED';
  const isMp3 = track.container === 'mp3';
  const blockUnknown = track.blockSize === null;

  const reframeBadge = isCloudOnly
    ? 'CLOUD ONLY'
    : track.encrypted
      ? 'DECRYPT + MEASURE'
      : isMp3
        ? 'N/A (MP3 容器)'
        : blockUnknown
          ? 'UNKNOWN'
          : track.blockSize !== null && track.blockSize > 4096
            ? 'REFRAME REQUIRED'
            : 'COMPLIANT (≤4096)';

  const reframeClass = isCloudOnly
    ? 'bg-[var(--muted)] text-[var(--muted-foreground)]'
    : isMp3
      ? 'bg-[var(--badge-bg)] text-[var(--badge-fg)]'
      : blockUnknown || (track.blockSize !== null && track.blockSize > 4096)
        ? 'bg-[#FF3300] text-white'
        : 'bg-emerald-600 text-white';

  const coverBadge = isCloudOnly
    ? 'CLOUD ONLY'
    : track.encrypted
      ? 'DECRYPT + NORMALIZE'
      : track.coverCompliant
        ? 'COMPLIANT JPEG'
        : track.coverRes === '无封面'
          ? 'NO COVER'
          : 'CONVERT 4:2:0';

  const coverEncoding =
    track.coverRes === '无封面' || track.coverRes === '—'
      ? '—'
      : track.coverYuv === '—'
        ? '未知'
        : 'Baseline JPG';

  const coverSourceLabels: Record<string, string> = {
    embedded: '内嵌图片块',
    local_meta: '本地 meta 缓存',
    downloaded: '网络补全',
  };
  const coverSourceText = isCloudOnly
    ? '—'
    : track.coverSource
      ? (coverSourceLabels[track.coverSource] ?? track.coverSource)
      : track.encrypted
        ? '构建时确定'
        : track.coverRes === '无封面'
          ? (track.coverLocalPath ? '本地 meta 缓存（构建时写入）' : '需要联网补全')
          : '内嵌图片块';

  const statusText = isCompliant
    ? 'STATUS: 100% HARDWARE COMPLIANT'
    : isCloudOnly
      ? 'STATUS: CLOUD ONLY (NOT DOWNLOADED)'
      : track.encrypted
        ? 'STATUS: ENCRYPTED — 构建时解密并复核'
        : 'STATUS: PENDING NORMALIZATION';

  return (
    <section
      id="col-02"
      className="col-span-12 md:col-span-6 xl:col-span-4 swiss-border-r flex flex-col min-h-0 h-full"
    >
      {/* Section Header */}
      <div className="px-3.5 py-2.5 swiss-border-b flex items-center justify-between bg-[var(--sidebar)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="swiss-mono text-xs font-bold px-1.5 py-0.5 bg-[var(--badge-bg)] text-[var(--badge-fg)] border border-[var(--border)]">
            02
          </span>
          <h2 className="text-xs font-bold uppercase tracking-wider">SPECIFICATION MATRIX</h2>
        </div>
        <span className="swiss-mono text-xs font-bold text-[#FF3300]">TRACK #{track.seq}</span>
      </div>

      {/* Inspector Body */}
      <div className="panel-scroll divide-y divide-[var(--border)]">
        {isCloudOnly && (
          <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 text-xs swiss-mono text-amber-600 dark:text-amber-400 flex items-start gap-2">
            <span className="shrink-0 font-bold">⚠️ [未下载音频]</span>
            <span>
              该曲目目前仅存在于网易云歌单中，本地未下载音频文件。请先在网易云客户端中下载该曲目，刷新后即可标准化并写入播放器乐库。
            </span>
          </div>
        )}

        {/* Track Summary & Cover Art Preview */}
        <div className="p-3.5 grid grid-cols-12 gap-3.5 items-center">
          <div className="col-span-4 aspect-square max-w-[110px] border border-[var(--border)] bg-[var(--sidebar)] relative flex flex-col justify-between p-1.5 overflow-hidden">
            <div className="flex justify-between items-start z-10">
              <span className="swiss-mono text-xs font-bold px-1 bg-[var(--card)] border border-[var(--border)]">
                TYPE {track.coverType ?? '—'}
              </span>
            </div>
            <div className="my-auto flex items-center justify-center">
              <div className="w-9 h-9 rounded-full bg-[#FF3300] opacity-90" />
              <div className="w-9 h-9 border-2 border-[var(--foreground)] -ml-3" />
            </div>
            <div className="z-10 bg-[var(--card)] px-1 py-0.5 border border-[var(--border)] text-center">
              <div className="swiss-mono text-xs font-bold truncate">{track.coverRes}</div>
            </div>
          </div>

          <div className="col-span-8 space-y-1 min-w-0">
            <div className="swiss-mono text-xs text-[var(--muted-foreground)] truncate">
              SOURCE: {track.artist} - {track.title}
              {track.srcExt}
            </div>
            <h3 className="text-sm font-bold tracking-tight leading-snug truncate">
              {track.seq} {track.artist} - {track.title}
              {isMp3 ? '.mp3' : '.flac'}
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] truncate">
              Target: {track.targetFolder}/{track.seq} {track.artist} - {track.title}
              {isMp3 ? '.mp3' : '.flac'}
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

        {/* 1. Audio Stream & Frame Buffer */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">
              A. 音频流与帧大小 (STREAMINFO)
            </span>
            <span className={`swiss-mono text-xs px-1.5 py-0.5 font-bold ${reframeClass}`}>
              {reframeBadge}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 swiss-mono text-xs bg-[var(--background)] p-2 border border-[var(--border)]">
            <div>
              <div className="text-[var(--muted-foreground)]">PCM SPEC</div>
              <div className="font-bold mt-0.5">{track.pcm}</div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">CURRENT BLOCK</div>
              <div
                className={`font-bold mt-0.5 ${
                  !isMp3 && (blockUnknown || (track.blockSize !== null && track.blockSize > 4096))
                    ? 'text-[#FF3300]'
                    : 'text-emerald-600'
                }`}
              >
                {isMp3
                  ? '不适用'
                  : blockUnknown
                    ? track.encrypted
                      ? '待解密'
                      : '—'
                    : track.blockSize}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">TARGET BLOCK</div>
              <div className="font-bold text-emerald-600 mt-0.5">
                {isMp3 ? '不适用' : '4096 (SAFE)'}
              </div>
            </div>
          </div>
        </div>

        {/* 2. Album Cover Art Spec */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">
              B. 专辑封面格式规范 (PICTURE BLOCK)
            </span>
            <span
              className={`swiss-mono text-xs px-1.5 py-0.5 font-bold ${
                track.coverCompliant
                  ? 'bg-emerald-600 text-white'
                  : isCloudOnly
                    ? 'bg-[var(--muted)] text-[var(--muted-foreground)]'
                    : 'bg-[#FF3300] text-white'
              }`}
            >
              {coverBadge}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 swiss-mono text-xs bg-[var(--background)] p-2 border border-[var(--border)]">
            <div>
              <div className="text-[var(--muted-foreground)]">RESOLUTION</div>
              <div className="font-bold mt-0.5">
                {isCloudOnly || track.coverRes === '—' ? '—' : track.coverRes}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">CHROMA SUB</div>
              <div
                className={`font-bold mt-0.5 ${
                  track.coverCompliant ? 'text-emerald-600' : 'text-[#FF3300]'
                }`}
              >
                {track.coverYuv}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted-foreground)]">ENCODING</div>
              <div className="font-bold mt-0.5">{coverEncoding}</div>
            </div>
          </div>
          <div className="mt-1.5 flex items-center justify-between gap-2 text-xs swiss-mono">
            <span className="text-[var(--muted-foreground)] truncate">
              封面来源: <strong className="font-bold text-[var(--foreground)]">{coverSourceText}</strong>
            </span>
            {!isCloudOnly && !track.encrypted && !track.coverCompliant && (
              <span className="text-[#FF3300] truncate" title={track.coverReasons.join(' / ')}>
                {track.coverReasons.slice(0, 2).join(' / ') || 'NO_COVER'}
              </span>
            )}
          </div>
        </div>

        {/* 3. Companion LRC Sanitizer */}
        <div className="p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold uppercase tracking-wider">
              C. 伴随歌词清洗 (.LRC SANITIZER)
            </span>
            <div className="flex items-center gap-1 swiss-mono text-xs">
              <span
                className={`px-1 border border-[var(--border)] ${
                  track.lrcState === 'CLEAN' ? 'text-emerald-600' : 'text-[#FF3300]'
                }`}
              >
                {track.lrcState}
              </span>
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
          {statusText}
        </span>
        <button
          onClick={() => onNormalizeTrack(track.id)}
          disabled={isCompliant || isCloudOnly || isBuilding}
          className={`swiss-mono text-xs font-bold px-3 py-1 border transition-colors shrink-0 ${
            isCompliant || isCloudOnly || isBuilding
              ? 'border-[var(--border)] text-[var(--muted-foreground)] bg-[var(--card)] cursor-not-allowed'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[#FF3300] hover:text-[#FF3300] cursor-pointer'
          }`}
        >
          {isNormalizing
            ? '执行中...'
            : isCompliant
              ? '✓ COMPLIANT'
              : isCloudOnly
                ? 'NOT DOWNLOADED'
                : 'NORMALIZE TRACK →'}
        </button>
      </div>
    </section>
  );
};
