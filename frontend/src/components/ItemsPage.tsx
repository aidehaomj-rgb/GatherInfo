import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { ExternalLink, BookOpenText, Languages, ShieldCheck, Send, ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import {
  fetchItems, fetchTags, fetchSources, fetchTopics,
  fetchStatsBySource, fetchBatches, fetchItemIds, batchDeleteItems, reviewItemQuality,
  translateItems, pushItemsToHaiSee,
} from "../api";
import type { BatchOut, CollectedItem, HaiSeePushResponse, ItemList, Tag, Source, Topic } from "../types";
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
  const [batches, setBatches] = useState<BatchOut[]>([]);
  const [filterBatch, setFilterBatch] = useState("");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [selectAllMode, setSelectAllMode] = useState<"page" | "all">("page");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteCount, setDeleteCount] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const [showQualityConfirm, setShowQualityConfirm] = useState(false);
  const [reviewingQuality, setReviewingQuality] = useState(false);
  const [qualityNotice, setQualityNotice] = useState<string | null>(null);
  const [haiseeResult, setHaiSeeResult] = useState<HaiSeePushResponse | null>(null);
  const [haiseeError, setHaiSeeError] = useState<string | null>(null);
  const [pushingHaiSee, setPushingHaiSee] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const requestedTranslationIds = useRef(new Set<string>());
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(new Set());
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchTags(undefined, 200).then(setTags).catch(() => {});
    fetchSources().then(setSources).catch(() => {});
    fetchTopics().then(setTopics).catch(() => {});
    fetchStatsBySource().then((rows) => {
      const m: Record<string, number> = {};
      for (const r of rows) m[r.source_id] = r.count;
      setSourceCounts(m);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchBatches(filterTopic || undefined, 50).then(setBatches).catch(() => setBatches([]));
  }, [filterTopic]);

  const batchOptions = useMemo(() => batches.map((batch) => ({
    batch_id: batch.batch_id,
    label: batch.batch_label || `${batch.topic_name || "采集"}_${batch.started_at?.slice(0, 16) || ""}`,
  })), [batches]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchItems({
        page, page_size: PAGE_SIZE,
        ...(query ? { q: query } : {}),
        ...(filterTag ? { tag: filterTag } : {}),
        ...(filterSource ? { source_id: filterSource } : {}),
        ...(filterTopic ? { topic_id: filterTopic } : {}),
        ...(filterBatch ? { batch_id: filterBatch } : {}),
        ...(filterCat ? { category: filterCat } : {}),
      });
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, [page, query, filterTag, filterSource, filterTopic, filterCat, filterBatch]);

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
            batch_id: filterBatch || undefined,
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

  const executeQualityReview = async () => {
    const itemIds = selectedItems.size > 0
      ? Array.from(selectedItems)
      : (data?.items.map((item) => item.id) ?? []);
    if (!itemIds.length) return;
    setReviewingQuality(true);
    try {
      const result = await reviewItemQuality(itemIds, itemIds.length);
      setSelectedItems(new Set());
      setSelectAllMode("page");
      setQualityNotice(`AI 已审核 ${result.reviewed} 条，整理 ${result.curated} 条，删除 ${result.deleted} 条低价值信息。`);
      await load();
      setShowQualityConfirm(false);
    } catch (e) {
      setQualityNotice(e instanceof Error ? e.message : "AI 质量审核失败");
    }
    setReviewingQuality(false);
  };

  const handleHaiSeePush = async () => {
    const itemIds = Array.from(selectedItems);
    if (!itemIds.length) return;
    if (itemIds.length > 50) {
      setHaiSeeError("HaiSee 单次最多接收 50 条信息，请缩小选择范围后重试。");
      return;
    }
    setPushingHaiSee(true);
    setHaiSeeError(null);
    setHaiSeeResult(null);
    try {
      setHaiSeeResult(await pushItemsToHaiSee(itemIds));
    } catch (e) {
      setHaiSeeError(e instanceof Error ? e.message : "推送 HaiSee 失败");
    }
    setPushingHaiSee(false);
  };

  const itemTree = useMemo(() => {
    const runToBatch = new Map<string, BatchOut>();
    for (const batch of batches) {
      for (const run of batch.runs) runToBatch.set(run.id, batch);
    }
    const sourceNames = new Map(sources.map((source) => [source.id, source.name]));
    const tree = new Map<string, { label: string; timestamp: string | null; sources: Map<string, CollectedItem[]> }>();
    for (const item of data?.items ?? []) {
      const batch = item.run_id ? runToBatch.get(item.run_id) : undefined;
      const batchId = batch?.batch_id || "unbatched";
      const label = batch?.batch_label || (item.run_id ? `采集运行 ${item.run_id.slice(0, 12)}` : "未归档采集条目");
      const current = tree.get(batchId) ?? { label, timestamp: batch?.started_at ?? item.collected_at, sources: new Map() };
      current.sources.set(item.source_id, [...(current.sources.get(item.source_id) ?? []), item]);
      tree.set(batchId, current);
    }
    return Array.from(tree.entries()).map(([batchId, batch]) => ({
      batchId,
      label: batch.label,
      timestamp: batch.timestamp,
      sources: Array.from(batch.sources.entries()).map(([sourceId, items]) => ({
        sourceId,
        sourceName: sourceNames.get(sourceId) || sourceId,
        items,
      })),
    }));
  }, [batches, data?.items, sources]);

  const toggleBatchExpanded = (key: string) => {
    setExpandedBatches((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const toggleSourceExpanded = (key: string) => {
    setExpandedSources((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const expandAllTree = () => {
    const batchIds = itemTree.map((batch) => batch.batchId);
    const sourceKeys = itemTree.flatMap((batch) => batch.sources.map((source) => `${batch.batchId}:${source.sourceId}`));
    setExpandedBatches(new Set(batchIds));
    setExpandedSources(new Set(sourceKeys));
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
        onFilterTopicChange={(v) => { setFilterTopic(v); setFilterBatch(""); setPage(1); }}
        filterSource={filterSource}
        onFilterSourceChange={(v) => { setFilterSource(v); setPage(1); }}
        filterBatch={filterBatch}
        onFilterBatchChange={(v) => { setFilterBatch(v); setPage(1); }}
        filterTag={filterTag}
        onFilterTagChange={(v) => { setFilterTag(v); setPage(1); }}
        topics={topics}
        sources={sources}
        sourceCounts={sourceCounts}
        batchOptions={batchOptions}
        tags={tags}
      />

      {qualityNotice && <div className="info-banner" style={{ marginBottom: 12 }}>{qualityNotice}</div>}
      {haiseeError && <div className="error-banner" style={{ marginBottom: 12 }}>{haiseeError}</div>}
      {haiseeResult && (
        <div className="info-banner haisee-handoff-notice" style={{ marginBottom: 12 }}>
          <span>
            已向 HaiSee 提交 {haiseeResult.task_ids.length} 个转译分析任务
            {haiseeResult.batch_id ? `，批次 ${haiseeResult.batch_id}` : ""}。
          </span>
          <a className="btn btn-sm btn-ghost" href={`${haiseeResult.web_url}/tasks`} target="_blank" rel="noreferrer">
            <ExternalLink size={13} /> 打开 HaiSee
          </a>
        </div>
      )}

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
        <button type="button" className="btn btn-sm btn-secondary" disabled={!data?.items.length} onClick={() => setShowQualityConfirm(true)}>
          <ShieldCheck size={14} /> AI 质量清理{selectedItems.size > 0 ? `（${selectedItems.size}）` : "本页"}
        </button>

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
                  batch_id: filterBatch || undefined,
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
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() => void handleHaiSeePush()}
              disabled={pushingHaiSee || selectedItems.size > 50}
              title={selectedItems.size > 50 ? "HaiSee 单次最多接收 50 条" : "送入下一环节开展转译分析"}
            >
              <Send size={14} />
              {pushingHaiSee ? "推送中..." : `推送至 HaiSee（${selectedItems.size}）`}
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
          <div className="item-tree-actions">
            <button type="button" className="btn btn-sm btn-ghost" onClick={expandAllTree}><ChevronsUpDown size={14} /> 全部展开</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setExpandedBatches(new Set()); setExpandedSources(new Set()); }}><ChevronsDownUp size={14} /> 收起到一级</button>
          </div>
          <div className="item-list">
            {itemTree.map((batch) => {
              const batchExpanded = expandedBatches.has(batch.batchId);
              const itemCount = batch.sources.reduce((sum, source) => sum + source.items.length, 0);
              return (
                <section key={batch.batchId} className="item-tree-batch">
                  <button type="button" className="item-tree-row item-tree-row--batch" onClick={() => toggleBatchExpanded(batch.batchId)} aria-expanded={batchExpanded}>
                    {batchExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <strong>{batch.label}</strong>
                    <span>{itemCount} 条</span>
                    {batch.timestamp && <span>{formatBeijingDateTime(batch.timestamp, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>}
                  </button>
                  {batchExpanded && batch.sources.map((source) => {
                    const sourceKey = `${batch.batchId}:${source.sourceId}`;
                    const sourceExpanded = expandedSources.has(sourceKey);
                    return (
                      <div key={sourceKey} className="item-tree-source">
                        <button type="button" className="item-tree-row item-tree-row--source" onClick={() => toggleSourceExpanded(sourceKey)} aria-expanded={sourceExpanded}>
                          {sourceExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                          <strong>{source.sourceName}</strong><span>{source.items.length} 条</span>
                        </button>
                        {sourceExpanded && source.items.map((item) => (
                          <div className="item-list-row item-tree-item" key={item.id}>
                            <input type="checkbox" checked={selectedItems.has(item.id)} onChange={() => {
                              setSelectedItems((prev) => {
                                const next = new Set(prev);
                                if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                                return next;
                              });
                            }} />
                            <div><ItemCard item={item} /></div>
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </section>
              );
            })}
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
      <ConfirmDialog
        open={showQualityConfirm}
        title="AI 质量清理"
        message={`将使用已配置的默认模型审核 ${selectedItems.size || data?.items.length || 0} 条信息。非独立文章、广告聚合页和不完整低价值内容会被直接删除；通过的信息会整理为中文情报简报。`}
        variant="danger"
        confirmLabel="审核并清理"
        onClose={() => setShowQualityConfirm(false)}
        onConfirm={executeQualityReview}
        loading={reviewingQuality}
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
          {item.quality_review && <span className="chip chip--green"><ShieldCheck size={12} /> AI整理</span>}
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
              {!item.quality_review && (originalTitle || item.summary || item.content) && (
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
