import { ExternalLink, X } from "lucide-react";
import { BookmarkButton } from "./BookmarkButton";
import type { CollectedItem, Source } from "../types";
import { cleanItemTitle, getDisplayTitle } from "../utils/title";
import { cleanContent, extractSummary } from "../utils/contentCleaner";
import { formatBeijingDateTime } from "../utils/date";

interface ItemDetailModalProps {
  item: CollectedItem;
  sources: Source[];
  onClose: () => void;
}

export function ItemDetailModal({ item, sources, onClose }: ItemDetailModalProps) {
  const sourceName =
    sources.find((s) => s.id === item.source_id)?.name || item.source_id;
  const hasTranslation = Boolean(item.title_zh || item.summary_zh || item.content_zh);
  const awaitingTranslation = needsChineseTranslation(item, hasTranslation);
  const displayTitle = awaitingTranslation ? "正在生成中文译文" : getDisplayTitle(item.title_zh || item.title);
  const originalTitle = cleanItemTitle(item.title);
  const review = item.enforcement_review;
  const reviewFields = review ? [
    ["涉华等级", review.china_relevance_label],
    ["国家/地区", review.jurisdiction],
    ["执法机关", review.authority],
    ["案件类型", review.case_type],
    ["涉案对象", review.subject],
    ["执法行为", review.enforcement_action],
    ["关联依据", review.mainland_nexus_evidence],
    ["原始来源", review.source_name || review.source_domain],
  ].filter((entry) => entry[1] != null && String(entry[1]).trim()) : [];

  // 清洗内容：过滤导航菜单噪音
  // Translations are curated text. Preserve the stored value when the generic
  // page cleaner is too aggressive with a short translated paragraph.
  const translatedSummary = cleanContent(item.summary_zh) || item.summary_zh?.trim() || "";
  const translatedContent = cleanContent(item.content_zh) || item.content_zh?.trim() || "";
  const originalSummary = cleanContent(item.summary) || "";
  const originalContent = cleanContent(item.content) || "";

  // 如果摘要为空或仍然是导航内容，从正文中提取
  const displaySummary = awaitingTranslation ? "" : hasTranslation
    ? (translatedSummary && !isNavOnly(translatedSummary) ? translatedSummary : extractSummary(translatedContent, 300))
    : (originalSummary && !isNavOnly(originalSummary) ? originalSummary : extractSummary(originalContent, 300));

  const displayContent = awaitingTranslation ? "" : hasTranslation ? translatedContent : originalContent;

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
              {item.enforcement_review && <span className="chip chip--green">AI审核</span>}
              {hasTranslation && <span className="chip chip--green">中文译文</span>}
              {item.category && <span className="chip chip--blue">{item.category}</span>}
              {item.published_at && (
                <span className="text-muted small">发布: {formatBeijingDateTime(item.published_at)}</span>
              )}
              {item.tags?.map((t) => (
                <span key={t.id} className="chip chip--pink" title={`${t.namespace}:${t.value}`}>
                  {t.value}
                </span>
              ))}
            </div>
          </div>
          {item.enforcement_review && (
            <div className="text-muted small" style={{ marginTop: 6 }}>
              审核状态: {String(item.enforcement_review.decision || "已审核")}
              {item.enforcement_review.confidence != null && ` | 置信度: ${String(item.enforcement_review.confidence)}`}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <BookmarkButton itemId={item.id} size={18} />
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="reading-modal-body">
          {reviewFields.length > 0 && (
            <section className="reading-summary" aria-label="执法案件要素">
              <strong>执法案件要素</strong>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "10px 18px",
                marginTop: 10,
              }}>
                {reviewFields.map(([label, value]) => (
                  <div key={String(label)} style={{ minWidth: 0 }}>
                    <span className="text-muted small">{String(label)}</span>
                    <div style={{ marginTop: 2, overflowWrap: "anywhere" }}>{String(value)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}
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
              {hasTranslation && <strong>中文译文</strong>}
              <div style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem", lineHeight: 1.8 }}>
                {displayContent}
              </div>
            </div>
          ) : (
            <p className="text-muted" style={{ fontStyle: "italic", padding: 20, textAlign: "center" }}>
              {awaitingTranslation ? "正在使用已配置模型生成中文译文。" : "暂无详细内容，当前仅显示摘要信息。"}
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

function needsChineseTranslation(item: CollectedItem, hasTranslation: boolean): boolean {
  if (hasTranslation || /^zh(?:-|$)|^cn$/i.test(item.language ?? "")) return false;
  return !/[\u4e00-\u9fff]/.test(`${item.title} ${item.summary ?? ""} ${item.content ?? ""}`);
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
