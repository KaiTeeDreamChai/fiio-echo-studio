/**
 * 轻量模糊匹配：中文按子串，英文按子串/子序列。
 * 仅用于本地列表（专辑/歌单/作者），数据量在千级以内，无需索引。
 */

export function normalizeText(input: string): string {
  return (input || '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[\s\-_·・.,，。:：;；!！?"'“”‘’()（）[\]【】<>《》/\\|+&]/g, '');
}

/**
 * 返回匹配分数（越在越前/越连续分越高），不匹配返回 null。
 */
export function fuzzyScore(query: string, text: string): number | null {
  const needle = normalizeText(query);
  if (!needle) return 0;

  const haystack = normalizeText(text);
  if (!haystack) return null;

  if (haystack === needle) return 1000;
  if (haystack.startsWith(needle)) {
    return 900 - Math.min(haystack.length - needle.length, 50) * 0.5;
  }

  const index = haystack.indexOf(needle);
  if (index >= 0) {
    return 800 - index * 2 - Math.min(haystack.length - needle.length, 50) * 0.5;
  }

  // 子序列：允许 "weeknd" 命中 "the weeknd"、"hurrytom" 命中 "hurry up tomorrow"
  let cursor = 0;
  let gaps = 0;
  let last = -1;
  for (const char of needle) {
    const found = haystack.indexOf(char, cursor);
    if (found === -1) return null;
    if (last >= 0) gaps += found - last - 1;
    last = found;
    cursor = found + 1;
  }
  return 400 - Math.min(gaps, 100) - Math.min(haystack.length - needle.length, 100) * 0.2;
}

/** 在多个字段里取最高分（用于“名称 + 作者/歌手”的联合匹配）。 */
export function fuzzyScoreAny(
  query: string,
  entries: Array<{ text: string; weight?: number }>,
): number | null {
  let best: number | null = null;
  for (const entry of entries) {
    const score = fuzzyScore(query, entry.text);
    if (score === null) continue;
    const weighted = score * (entry.weight ?? 1);
    if (best === null || weighted > best) best = weighted;
  }
  return best;
}

/** 找到原文中的连续匹配区间，用于高亮；子序列匹配不返回区间。 */
export function highlightRange(text: string, query: string): [number, number] | null {
  const needle = (query || '').trim();
  if (!needle || !text) return null;
  const index = text.toLowerCase().indexOf(needle.toLowerCase());
  if (index < 0) return null;
  return [index, index + needle.length];
}
