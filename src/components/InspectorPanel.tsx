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

  const reframeState = isCloudOnly
    ? '未下载'
    : track.encrypted
      ? '待解密'
      : isMp3
        ? '不适用'
        : blockUnknown
          ? '未知'
          : track.blockSize !== null && track.blockSize > 4096
            ? '需重封装'
            : '合规';

  const reframeColor = isCloudOnly || track.encrypted || isMp3
    ? 'text-[var(--muted-foreground)]'
    : blockUnknown || (track.blockSize !== null && track.blockSize > 4096)
      ? 'text-[#FF3300]'
      : 'text-emerald-600';

  const coverState = isCloudOnly
    ? '未下载'
    : track.encrypted
      ? '待解密'
      : track.coverCompliant
        ? '合规'
        : track.coverRes === '无封面'
          ? '无封面'
          : '需转换';

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
          ? (track.coverLocalPath ? '本地 meta（构建时写入）' : '需要联网补全')
          : '内嵌图片块';

  const lrcStateLabel =
    track.lrcState === 'CLEAN'
      ? '已清洗'
      : track.lrcState === 'JSON_DIRTY'
        ? '含 JSON 脏词'
        : '三位毫秒';

  const footerStatus = isCompliant
    ? '合规'
    : isCloudOnly
      ? '未下载'
      : track.encrypted
        ? '待解密'
        : '待规范化';

  const folderLabel = track.targetFolder.replace(/^(Albums|Playlists)\//, '');

  return (
    <section
      id="col-02"
      className="col-span-12 md:col-span-6 xl:col-span-4 swiss-border-r flex flex-col min-h-0 h-full"
    >
      <div className="px-4 py-2.5 swiss-border-b flex items-baseline justify-between bg-[var(--sidebar)] shrink-0">
        <h2 className="text-xs font-bold tracking-wider">参数</h2>
        <span className="swiss-mono text-[10px] text-[var(--muted-foreground)]">曲目 #{track.seq}</span>
      </div>

      <div className="panel-scroll divide-y divide-[var(--border)]">
        {isCloudOnly && (
          <div className="px-4 py-2.5 bg-amber-500/10 text-[10px] leading-relaxed text-amber-600 dark:text-amber-400">
            该曲目仅存在于云端。请先在网易云客户端下载音频，再回到这里构建。
          </div>
        )}

        {/* 曲目概览 */}
        <div className="p-4 flex gap-3 items-start">
          <div className="w-[88px] h-[88px] shrink-0 border border-[var(--border)] bg-[var(--sidebar)] relative overflow-hidden">
            <div className="absolute left-3.5 top-5 w-9 h-9 rounded-full bg-[#FF3300] opacity-90" />
            <div className="absolute left-8 top-5 w-8 h-8 border-2 border-[var(--foreground)]" />
            <div className="absolute inset-x-0 bottom-0 py-0.5 text-center swiss-mono text-[8px] bg-[var(--card)] border-t border-[var(--border)]">
              {track.coverRes === '无封面' ? '无封面' : track.coverRes}
            </div>
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <h3 className="text-[15px] font-bold leading-snug truncate">{track.title}</h3>
            <div className="text-[11px] text-[var(--muted-foreground)] truncate">{track.artist}</div>
            <div className="text-[10px] text-[var(--muted-foreground)] truncate">{track.album}</div>
            <div className="pt-1.5 flex flex-wrap gap-1.5 swiss-mono text-[9px]">
              <span className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)]">
                {isMp3 ? 'MP3' : 'FLAC'}
              </span>
              <span className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)]">
                {(track.sizeBytes / 1024 / 1024).toFixed(1)} MB
              </span>
              <span
                className="px-1.5 py-0.5 border border-[var(--border)] bg-[var(--background)] max-w-[120px] truncate"
                title={track.targetFolder}
              >
                {folderLabel}
              </span>
            </div>
          </div>
        </div>

        {/* 音频流 */}
        <div className="px-4 py-3">
          <div className="flex items-baseline justify-between mb-2">
            <h4 className="text-[11px] font-bold tracking-wider">音频流</h4>
            <span className={`swiss-mono text-[10px] font-semibold ${reframeColor}`}>{reframeState}</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">位深 / 采样率</div>
              <div className="swiss-mono text-[11px] font-semibold mt-1">{track.pcm}</div>
            </div>
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">当前帧</div>
              <div
                className={`swiss-mono text-[11px] font-semibold mt-1 ${
                  !isMp3 && (blockUnknown || (track.blockSize !== null && track.blockSize > 4096))
                    ? 'text-[#FF3300]'
                    : ''
                }`}
              >
                {isMp3 ? '不适用' : blockUnknown ? (track.encrypted ? '待解密' : '—') : track.blockSize}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">目标帧</div>
              <div className="swiss-mono text-[11px] font-semibold mt-1">{isMp3 ? '不适用' : '4096'}</div>
            </div>
          </div>
        </div>

        {/* 封面 */}
        <div className="px-4 py-3">
          <div className="flex items-baseline justify-between mb-2">
            <h4 className="text-[11px] font-bold tracking-wider">封面</h4>
            <span
              className={`swiss-mono text-[10px] font-semibold ${
                track.coverCompliant ? 'text-emerald-600' : 'text-[#FF3300]'
              }`}
            >
              {coverState}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">分辨率</div>
              <div className="swiss-mono text-[11px] font-semibold mt-1">
                {isCloudOnly || track.coverRes === '—' ? '—' : track.coverRes}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">色度</div>
              <div
                className={`swiss-mono text-[11px] font-semibold mt-1 ${
                  track.coverCompliant ? '' : 'text-[#FF3300]'
                }`}
              >
                {track.coverYuv}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-[var(--muted-foreground)]">编码</div>
              <div className="swiss-mono text-[11px] font-semibold mt-1">{coverEncoding}</div>
            </div>
          </div>
          <div className="mt-2 text-[9px] text-[var(--muted-foreground)] flex items-center justify-between gap-2">
            <span className="truncate">
              来源 <strong className="font-semibold text-[var(--foreground)]">{coverSourceText}</strong>
            </span>
            {!isCloudOnly && !track.encrypted && !track.coverCompliant && (
              <span className="text-[#FF3300] truncate" title={track.coverReasons.join(' / ')}>
                {track.coverReasons.slice(0, 2).join(' / ') || 'NO_COVER'}
              </span>
            )}
          </div>
        </div>

        {/* 歌词 */}
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <h4 className="text-[11px] font-bold tracking-wider">歌词</h4>
              <span
                className={`swiss-mono text-[9px] ${
                  track.lrcState === 'CLEAN' ? 'text-emerald-600' : 'text-[#FF3300]'
                }`}
              >
                {lrcStateLabel}
              </span>
            </div>
            <div className="flex items-center swiss-mono text-[9px]">
              <button
                onClick={() => setLrcMode('raw')}
                className={`px-1.5 py-0.5 border border-[var(--border)] cursor-pointer ${
                  lrcMode === 'raw'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] font-bold'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)]'
                }`}
              >
                原文
              </button>
              <button
                onClick={() => setLrcMode('clean')}
                className={`px-1.5 py-0.5 border border-[var(--border)] -ml-px cursor-pointer ${
                  lrcMode === 'clean'
                    ? 'bg-[var(--active-bg)] text-[var(--active-fg)] font-bold'
                    : 'bg-[var(--card)] text-[var(--muted-foreground)]'
                }`}
              >
                清洗后
              </button>
            </div>
          </div>
          <pre className="swiss-mono text-[10px] p-2 bg-[var(--background)] border border-[var(--border)] leading-relaxed min-h-[78px] whitespace-pre-wrap break-words">
            {lrcMode === 'raw' ? track.rawLrc : track.cleanLrc}
          </pre>
        </div>
      </div>

      <div className="px-4 py-2.5 swiss-border-t bg-[var(--sidebar)] flex items-center justify-between shrink-0">
        <span
          className={`swiss-mono text-[10px] truncate mr-2 ${
            isCompliant
              ? 'text-emerald-600'
              : isCloudOnly
                ? 'text-[var(--muted-foreground)]'
                : 'text-[#FF3300]'
          }`}
        >
          {footerStatus}
        </span>
        <button
          onClick={() => onNormalizeTrack(track.id)}
          disabled={isCompliant || isCloudOnly || isBuilding}
          className={`swiss-mono text-[10px] font-bold px-3 py-1.5 border transition-colors shrink-0 ${
            isCompliant || isCloudOnly || isBuilding
              ? 'border-[var(--border)] text-[var(--muted-foreground)] bg-[var(--card)] cursor-not-allowed'
              : 'border-[#FF3300] text-[#FF3300] bg-[var(--card)] hover:bg-[#FF3300] hover:text-white cursor-pointer'
          }`}
        >
          {isNormalizing ? '执行中…' : isCompliant ? '已合规' : isCloudOnly ? '未下载' : '规范化此曲 →'}
        </button>
      </div>
    </section>
  );
};
