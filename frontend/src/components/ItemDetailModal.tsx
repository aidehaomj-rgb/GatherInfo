import { ExternalLink, X } from "lucide-react";
import { BookmarkButton } from "./BookmarkButton";
import type { CollectedItem, Source } from "../types";
import { cleanItemTitle, getDisplayTitle } from "../utils/title";
import { cleanContent, extractSummary } from "../utils/contentCleaner";

interface ItemDetailModalProps {
  item: CollectedItem;
  sources: Source[];
  onClose: () => void;
}

export function ItemDetailModal({ item, sources, onClose }: ItemDetailModalProps) {
  const sourceName =
    sources.find((s) => s.id === item.source_id)?.name || item.source_id;
  const hasTranslation = Boolean(item.title_zh || item.summary_zh || item.content_zh);
  const displayTitle = getDisplayTitle(item.title_zh || item.title);
  const originalTitle = cleanItemTitle(item.title);

  // 清洗内容：过滤导航菜单噪音
  const translatedSummary = cleanContent(item.summary_zh) || "";
  const translatedContent = cleanContent(item.content_zh) || "";
  const originalSummary = cleanContent(item.summary) || "";
  const originalContent = cleanContent(item.content) || "";

  // 如果摘要为空或仍然是导航内容，从正文中提取
  const displaySummary = hasTranslation
    ? (translatedSummary && !isNavOnly(translatedSummary) ? translatedSummary : extractSummary(translatedContent, 300))
    : (originalSummary && !isNavOnly(originalSummary) ? originalSummary : extractSummary(originalContent, 300));

  const displayContent = hasTranslation ? translatedContent : originalContent;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal reading-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="reading-modal-header">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, lineHeight: 1.4 }}>
              {displayTitle}
            </h3>
            <div className="reading-modal-meta" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              {item.source_id && <span className="chip">来源: {sourceName}</span>}
              {item.language && <span className="chip">{item.language}</span>}
              {hasTranslation && <span className="chip chip--green">中文译文</span>}
              {item.category && <span className="chip chip--blue">{item.category}</span>}
              {item.published_at && (
                <span className="text-muted small">发布: {new Date(item.published_at).toLocaleString("zh")}</span>
              )}
              {item.tags?.map((t) => (
                <span key={t.id} className="chip chip--pink" title={`${t.namespace}:${t.value}`}>
                  {t.value}
                </span>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <BookmarkButton itemId={item.id} size={18} />
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="reading-modal-body">
          {/* 摘要 */}
          {displaySummary && (
            <div className="reading-summary">
              <strong>摘要</strong>
              <p>{displaySummary}</p>
            </div>
          )}

          {/* 正文 */}
          {displayContent ? (
            <div className="reading-content">
              <div style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem", lineHeight: 1.8 }}>
                {displayContent}
              </div>
            </div>
          ) : (
            <p className="text-muted" style={{ fontStyle: "italic", padding: 20, textAlign: "center" }}>
              暂无详细内容，当前仅显示摘要信息。
            </p>
          )}

          {/* 原文链接 */}
          {item.url && (
            <div className="reading-url">
              <strong>原文链接</strong>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.url} <ExternalLink size={12} />
              </a>
            </div>
          )}

          {/* 源文件内容（仅在翻译模式下显示） */}
          {hasTranslation && originalContent && (
            <section className="reading-section reading-original">
              <strong>源文件内容</strong>
              {originalTitle && originalTitle !== displayTitle && <h4>{originalTitle}</h4>}
              <div style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem", color: "var(--ink-muted)" }}>
                {originalContent}
              </div>
            </section>
          )}

          {/* Footer */}
          <div className="reading-modal-footer">
            <div className="text-muted small">
              质量评分: {item.quality_score.toFixed(2)} | 相关性: {item.relevance_score.toFixed(2)} | 状态: {item.status}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** 判断文本是否仅为导航内容 */
function isNavOnly(text: string): boolean {
  if (!text) return true;
  const words = text.match(/[\w\u4e00-\u9fff]+/g) || [];
  if (words.length === 0) return true;
  const navWords = new Set([
    "首页", "新闻中心", "媒体发布", "文件库", "新闻官员", "社交媒体",
    "多媒体", "法律声明", "新闻通讯", "公告", "出版物", "聚光灯",
    "home", "news", "press", "media", "library", "contact", "about",
    "sitemap", "privacy", "terms", "copyright", "subscribe",
  ]);
  const navHits = words.filter(w => navWords.has(w.toLowerCase())).length;
  return navHits / words.length > 0.40;
}
