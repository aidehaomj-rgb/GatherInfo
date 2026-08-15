/**
 * 内容清洗工具：过滤导航菜单、面包屑、重复内容
 * 提取真正的文章正文和摘要
 */

const NAV_KEYWORDS = new Set([
  "首页", "新闻中心", "国家媒体发布", "跳至正文内容", "统计数据和摘要",
  "问责制和透明度", "媒体发布", "文件库", "新闻官员", "社交媒体目录",
  "多媒体图书馆", "法律声明", "前线数字杂志", "新闻通讯", "公告",
  "出版物目录", "聚光灯", "contact us", "about us", "sitemap",
  "accessibility", "foia", "privacy policy", "terms of use",
  "skip to main content", "main menu", "site map", "breadcrumb",
  "top stories", "latest news", "press releases", "newsroom",
  "media contacts", "social media", "photo gallery", "video",
  "podcast", "subscribe", "newsletter", "rss feed", "archive",
  "search", "advanced search", "site search", "quick links",
  "related links", "popular pages", "trending topics",
  "follow us", "share this", "print this page", "email this",
  "download", "pdf download", "read more", "learn more",
  "back to top", "scroll to top", "go home", "home page",
  "previous", "next", "page", "of", "pagination",
  "last updated", "modified date", "published date",
  "disclaimer", "legal notice", "copyright", "all rights reserved",
  "trademark", "patent", "accessibility statement",
  "equal employment opportunity", "eeo", "no fear act",
  "budget and performance", "inspector general", "ig",
  "strategic plan", "organization chart", "leadership",
  "directory", "phone directory", "contact directory",
  "frequently asked questions", "faq", "help center",
  "feedback", "report a problem", "suggestion box",
]);

const BREADCRUMB_PATTERNS = [
  /^(?:首页|home|主页)\s*[>›/→\\|]\s*.+/i,
  /\b(?:您在这里|you are here|breadcrumb)\s*[:：]?\s*.+/i,
];

const REPEAT_THRESHOLD = 3;

/**
 * 清洗文本内容，过滤导航噪音
 */
export function cleanContent(text: string | null | undefined): string {
  if (!text) return "";

  let cleaned = text;

  // 1. 移除 HTML 标签
  cleaned = cleaned.replace(/<[^>]+>/g, " ");

  // 2. 规范化空白
  cleaned = cleaned.replace(/[\x00-\x1f\x7f]+/g, " ");
  cleaned = cleaned.replace(/\s+/g, " ");

  // 3. 按段落/句子拆分处理
  const segments = cleaned.split(/[.!?。！？]\s+|\n\s*\n|\n/);
  const filtered: string[] = [];
  const seenCounts = new Map<string, number>();

  for (let segment of segments) {
    segment = segment.trim();
    if (!segment || segment.length < 10) continue;

    // 3a. 过滤面包屑导航
    if (BREADCRUMB_PATTERNS.some(p => p.test(segment))) continue;

    // 3b. 导航菜单过滤：导航关键词占比过高
    const words = segment.match(/[\w\u4e00-\u9fff]+/g) || [];
    if (words.length > 0) {
      const navHits = words.filter(w =>
        NAV_KEYWORDS.has(w.toLowerCase())
      ).length;
      if (navHits / words.length > 0.30) continue;
    }

    // 3c. 纯链接列表过滤（每行都很短且含导航词）
    const lines = segment.split("\n").filter(l => l.trim());
    if (lines.length > 2 && lines.every(l => l.length <= 25)) {
      const navLineHits = lines.filter(l =>
        Array.from(NAV_KEYWORDS).some(kw => l.toLowerCase().includes(kw))
      ).length;
      if (navLineHits / lines.length > 0.40) continue;
    }

    // 3d. 重复内容检测
    const key = segment.toLowerCase().replace(/\s+/g, " ");
    const count = (seenCounts.get(key) || 0) + 1;
    seenCounts.set(key, count);
    if (count > REPEAT_THRESHOLD) continue;

    // 3e. 过滤纯数字/纯符号段落
    if (/^[\d\s\W]+$/.test(segment)) continue;

    filtered.push(segment);
  }

  // 4. 重新组合
  cleaned = filtered.join("\n\n");

  // 5. 最终清理
  cleaned = cleaned.replace(/\s{2,}/g, " ");
  cleaned = cleaned.replace(/^\s+|\s+$/g, "");

  return cleaned;
}

/**
 * 提取真正的摘要（从正文中提取前 N 个字符）
 */
export function extractSummary(text: string | null | undefined, limit: number = 220): string {
  if (!text) return "";

  const cleaned = cleanContent(text);
  if (!cleaned) return "";

  if (cleaned.length <= limit) return cleaned;

  // 尝试在句子边界截断
  const truncated = cleaned.slice(0, limit);
  const lastSentenceEnd = Math.max(
    truncated.lastIndexOf("。"),
    truncated.lastIndexOf(". "),
    truncated.lastIndexOf("! "),
    truncated.lastIndexOf("? ")
  );

  if (lastSentenceEnd > limit * 0.6) {
    return cleaned.slice(0, lastSentenceEnd + 1);
  }

  // 在单词边界截断
  const lastSpace = truncated.lastIndexOf(" ");
  if (lastSpace > limit * 0.7) {
    return cleaned.slice(0, lastSpace) + "...";
  }

  return truncated + "...";
}

/**
 * 判断内容是否为导航菜单/面包屑（而非正文）
 */
export function isNavContent(text: string): boolean {
  if (!text || text.length < 5) return false;

  const words = text.match(/[\w\u4e00-\u9fff]+/g) || [];
  if (words.length === 0) return false;

  const navHits = words.filter(w =>
    NAV_KEYWORDS.has(w.toLowerCase())
  ).length;

  return navHits / words.length > 0.35;
}
