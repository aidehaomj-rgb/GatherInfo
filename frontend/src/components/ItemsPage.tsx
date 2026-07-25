import { useEffect, useState, useCallback, useRef } from "react";
import { ExternalLink, BookOpenText, Languages } from "lucide-react";
import {
  fetchItems, fetchTags, fetchSources, fetchTopics,
  fetchStatsBySource, fetchBatches, fetchItemIds, batchDeleteItems, translateItems,
} from "../api";
import type { CollectedItem, ItemList, Tag, Source, Topic } from "../types";
import { cleanItemTitle, getDisplayTitle } from "../utils/title";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { ItemFilterBar } from "./ItemFilterBar";
import { ItemDetailModal } from "./ItemDetailModal";
import { formatBeijingDateTime } from "../utils/date";

const PAGE_SIZE = 40;

export function ItemsPage() {
  const [data, setData] = useState<ItemList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [filterTag, setFilterTag] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterTopic, setFilterTopic] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [readingItem, setReadingItem] = useState<CollectedItem | null>(null);

  const [tags, setTags] = useState<Tag[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({});
  const [batchOptions, setBatchOptions] = useState<{ run_id: string; label: string }[]>([]);
  const [filterRun, setFilterRun] = useState("");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [selectAllMode, setSelectAllMode] = useState<"page" | "all">("page");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteCount, setDeleteCount] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const requestedTranslationIds = useRef(new Set<string>());

  useEffect(() => {
    fetchTags(undefined, 200).then(setTags).catch(() => {});
    fetchSources().then(setSources).catch(() => {});
    fetchTopics().then(setTopics).catch(() => {});
    fetchStatsBySource().then((rows) => {
      const m: Record<string, number> = {};
      for (const r of rows) m[r.source_id] = r.count;
      setSourceCounts(m);
    }).catch(() => {});
    fetchBatches(filterTopic || undefined, 30).then((batches) => {
      const options: { run_id: string; label: string }[] = [];
      for (const b of batches) {
        for (const r of b.runs || []) {
          if (r.id) options.push({
            run_id: r.id,
            label: b.batch_label || `${b.topic_name || "采集"}_${b.started_at?.slice(0, 16) || ""}`,
          });
        }
      }
      setBatchOptions(options);
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchItems({
        page, page_size: PAGE_SIZE,
        ...(query ? { q: query } : {}),
        ...(filterTag ? { tag: filterTag } : {}),
        ...(filterSource ? { source_id: filterSource } : {}),
        ...(filterTopic ? { topic_id: filterTopic } : {}),
        ...(filterRun ? { run_id: filterRun } : {}),
        ...(filterCat ? { category: filterCat } : {}),
      });
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, [page, query, filterTag, filterSource, filterTopic, filterCat, filterRun]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!data) return;
    const itemIds = data.items
      .filter(needsChineseTranslation)
      .filter((item) => !requestedTranslationIds.current.has(item.id))
      .map((item) => item.id);
    if (!itemIds.length) return;

    itemIds.forEach((id) => requestedTranslationIds.current.add(id));
    void translateItems(itemIds).then(load).catch(() => undefined);
  }, [data, load]);

  useEffect(() => {
    const handler = (e: Event) => {
      const evt = e as CustomEvent;
      if (evt.detail) setReadingItem(evt.detail);
    };
    window.addEventListener("open-reading", handler);
    return () => window.removeEventListener("open-reading", handler);
  }, []);

  useEffect(() => {
    if (readingItem) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [readingItem]);

  const handleBatchDelete = async () => {
    if (selectedItems.size === 0) return;
    const count = selectAllMode === "all" ? (data?.total ?? selectedItems.size) : selectedItems.size;
    setDeleteCount(count);
    setShowDeleteConfirm(true);
  };

  const executeDelete = async () => {
    const count = deleteCount;
    setDeleting(true);
    try {
      const ids = selectAllMode === "page"
        ? Array.from(selectedItems)
        : (await fetchItemIds({
            q: query || undefined,
            topic_id: filterTopic || undefined,
            source_id: filterSource || undefined,
            tag: filterTag || undefined,
            category: filterCat || undefined,
            run_id: filterRun || undefined,
          })).ids;
      const r = await batchDeleteItems(ids);
      setSelectedItems(new Set());
      setSelectAllMode("page");
      await load();
      setShowDeleteConfirm(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setDeleting(false);
  };

  return (
    <>
      <div className="page">
      <div className="page-header">
        <div>
          <h2>采集条目</h2>
          <p className="text-muted">
            {data ? `共 ${data.total.toLocaleString()} 条 · 第 ${data.page} 页` : "加载中..."}
          </p>
        </div>
      </div>

      <ItemFilterBar
        query={query}
        onQueryChange={(v) => { setQuery(v); setPage(1); }}
        filterTopic={filterTopic}
        onFilterTopicChange={(v) => { setFilterTopic(v); setPage(1); }}
        filterSource={filterSource}
        onFilterSourceChange={(v) => { setFilterSource(v); setPage(1); }}
        filterRun={filterRun}
        onFilterRunChange={(v) => { setFilterRun(v); setPage(1); }}
        filterTag={filterTag}
        onFilterTagChange={(v) => { setFilterTag(v); setPage(1); }}
        topics={topics}
        sources={sources}
        sourceCounts={sourceCounts}
        batchOptions={batchOptions}
        tags={tags}
      />

      {/* Selection toolbar */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, padding: "8px 14px", background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius)" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: "0.82rem" }}>
          <input type="checkbox" style={{ accentColor: "var(--accent)", cursor: "pointer" }}
            checked={Boolean(data && selectedItems.size > 0 && (selectAllMode === "all" || (selectAllMode === "page" && selectedItems.size >= data.items.length)))}
            onChange={async (e) => {
              if (e.target.checked && data) {
                setSelectedItems(new Set(data.items.map((item) => item.id)));
                setSelectAllMode("page");
              } else {
                setSelectedItems(new Set());
                setSelectAllMode("page");
              }
            }}
          />
          <strong>全选</strong>
        </label>
        <span className="text-muted small">已选 {selectedItems.size} / {data?.total || 0} 条</span>

        {selectedItems.size > 0 && (
          <>
            {data && selectAllMode === "page" && data.total > data.items.length && (
              <button type="button" className="btn btn-sm btn-ghost" style={{ color: "var(--accent)", fontSize: "0.78rem" }} onClick={async () => {
                const result = await fetchItemIds({
                  q: query || undefined,
                  topic_id: filterTopic || undefined,
                  source_id: filterSource || undefined,
                  tag: filterTag || undefined,
                  category: filterCat || undefined,
                  run_id: filterRun || undefined,
                });
                setSelectedItems(new Set(result.ids));
                setSelectAllMode("all");
              }}>
                全选全部 {data?.total || 0} 条匹配条目
              </button>
            )}
            {selectAllMode === "all" && (
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setSelectedItems(new Set()); setSelectAllMode("page"); }}>
                取消全选
              </button>
            )}
            <button type="button" className="btn btn-sm btn-danger" onClick={handleBatchDelete}>
              批量删除
            </button>
          </>
        )}
      </div>

      {loading ? (
        <div className="loading">加载条目...</div>
      ) : error ? (
        <div className="error-banner">{error}</div>
      ) : !data ? null : (
        <>
          <div className="item-list">
            {(() => {
              const groups = new Map<string, CollectedItem[]>();
              for (const item of data.items) {
                const key = item.run_id || item.source_id || "unknown";
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key)!.push(item);
              }
              const runLabelMap = new Map(batchOptions.map((b) => [b.run_id, b.label]));
              const entries = Array.from(groups.entries());
              return entries.map(([runId, items]) => (
                <div key={runId} style={{ marginBottom: 12 }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "6px 12px", marginBottom: 6,
                    background: "var(--surface-elevated)", borderRadius: "var(--radius)",
                    fontSize: "0.78rem", color: "var(--ink-muted)",
                    borderLeft: "3px solid var(--accent)",
                  }}>
                    <span style={{ fontWeight: 600, color: "var(--ink)" }}>
                      {runLabelMap.get(runId) || "批次: " + runId.slice(0, 16)}
                    </span>
                    <span>{items.length} 条</span>
                    {items[0].collected_at && (
                      <span>{formatBeijingDateTime(items[0].collected_at, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    )}
                  </div>
                  {items.map((item) => (
                    <div className="item-list-row" key={item.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                      <input type="checkbox" style={{ marginTop: 14, accentColor: "var(--accent)", cursor: "pointer" }}
                        checked={selectedItems.has(item.id)}
                        onChange={() => {
                          setSelectedItems((prev) => {
                            const next = new Set(prev);
                            if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                            return next;
                          });
                        }}
                      />
                      <div style={{ flex: 1 }}>
                        <ItemCard key={item.id} item={item} />
                      </div>
                    </div>
                  ))}
                </div>
              ));
            })()}
          </div>

          <div className="pagination">
            <button type="button" className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              上一页
            </button>
            <label className="pagination-select">
              <span className="sr-only">选择页码</span>
              <select value={page} onChange={(event) => setPage(Number(event.target.value))}>
                {Array.from({ length: Math.max(1, Math.ceil(data.total / PAGE_SIZE)) }, (_, index) => index + 1).map((pageNumber) => (
                  <option key={pageNumber} value={pageNumber}>第 {pageNumber} 页</option>
                ))}
              </select>
            </label>
            <span className="text-muted">/ {Math.max(1, Math.ceil(data.total / PAGE_SIZE))}</span>
            <button type="button" className="btn btn-sm btn-ghost" disabled={page >= Math.max(1, Math.ceil(data.total / PAGE_SIZE))} onClick={() => setPage(page + 1)}>
              下一页
            </button>
          </div>
        </>
      )}

      {readingItem && (
        <ItemDetailModal
          item={readingItem}
          sources={sources}
          onClose={() => setReadingItem(null)}
        />
      )}
    </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="批量删除条目"
        message={`确定删除 ${deleteCount} 条采集条目？此操作不可撤销。`}
        variant="danger"
        confirmLabel="确认删除"
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={executeDelete}
        loading={deleting}
      />
    </>
  );
}

// ── ItemCard ──────────────────────────────────────────────────────────

function needsChineseTranslation(item: CollectedItem): boolean {
  if (item.title_zh || item.summary_zh || item.content_zh) return false;
  if (/^zh(?:-|$)|^cn$/i.test(item.language ?? "")) return false;
  return !/[\u4e00-\u9fff]/.test(`${item.title} ${item.summary ?? ""} ${item.content ?? ""}`);
}

function ItemCard({ item }: { item: CollectedItem }) {
  const [expanded, setExpanded] = useState(false);
  const hasTranslation = Boolean(item.title_zh || item.summary_zh || item.content_zh);
  const awaitingTranslation = needsChineseTranslation(item);
  const displayTitle = awaitingTranslation ? "正在生成中文译文" : getDisplayTitle(item.title_zh || item.title);
  const originalTitle = cleanItemTitle(item.title);
  const displaySummary = item.summary_zh || item.summary;
  return (
    <article className="item-card">
      <div className="item-card-header">
        <h4 className="item-title" onClick={() => setExpanded(!expanded)}>
          {displayTitle}
        </h4>
        <div className="item-card-meta">
          {item.url && (
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="btn-icon" title="打开原文">
              <ExternalLink size={12} />
            </a>
          )}
          {hasTranslation && <span className="chip chip--green"><Languages size={12} /> 译文</span>}
          {item.enforcement_review && <span className="chip chip--green">AI审核</span>}
          <span className="chip">{item.language ?? "?"}</span>
          {item.category && <span className="chip chip--blue">{item.category}</span>}
          {item.tags?.map((t) => (
            <span key={t.id} className="chip chip--pink" title={`${t.namespace}:${t.value}`}>{t.value}</span>
          ))}
        </div>
      </div>
      {expanded && (
        <div className="item-card-body" id={`item-content-${item.id}`}>
          {hasTranslation ? (
            <>
              {(item.summary_zh || item.content_zh) && (
                <div className="item-translation-preview">
                  <strong>中文译文</strong>
                  <p className="text-muted">{item.summary_zh || item.content_zh}</p>
                </div>
              )}
              {(originalTitle || item.summary || item.content) && (
                <div className="item-original-preview">
                  <strong>源文件内容</strong>
                  {originalTitle && originalTitle !== displayTitle && (
                    <p className="item-original-line">原文标题：{originalTitle}</p>
                  )}
                  {(item.summary || item.content) && (
                    <p className="text-muted">{item.summary || item.content}</p>
                  )}
                </div>
              )}
            </>
          ) : awaitingTranslation ? (
            <p className="text-muted">正在使用已配置模型生成中文译文。</p>
          ) : (
            displaySummary && <p className="text-muted">{displaySummary}</p>
          )}
          {!displaySummary && item.url && <p className="text-muted">URL: {item.url}</p>}
          <div className="item-card-footer" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="text-muted small">
              {item.collected_at && `采集: ${formatBeijingDateTime(item.collected_at)}`}
              {item.published_at && ` · 发布: ${formatBeijingDateTime(item.published_at)}`}
              {` · 来源: ${item.source_id}`}
              {` · 质量: ${item.quality_score.toFixed(2)}`}
            </span>
          </div>
          <button type="button" className="btn btn-sm btn-secondary" style={{ marginTop: 8, width: "100%" }}
            onClick={(e) => {
              e.stopPropagation();
              window.dispatchEvent(new CustomEvent("open-reading", { detail: item }));
            }}>
            <BookOpenText size={14} /> 阅读全文
          </button>
        </div>
      )}
    </article>
  );
}
