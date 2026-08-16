import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { ArrowRight, BookOpenText, CalendarDays, FileText, Globe2, Newspaper } from "lucide-react";
import { collectTopic, fetchDashboard, fetchFeaturedItems, fetchItem, fetchItems, fetchReports, fetchSources, fetchTopics, resolveFeaturedImages } from "../api";
import { useToast } from "./ToastProvider";
import type { CollectedItem, DashboardData, Report, Source, Topic } from "../types";
import { getDisplayTitle } from "../utils/title";
import { ItemDetailModal } from "./ItemDetailModal";
import { ReportViewerModal } from "./ReportViewerModal";
import { HomeHero } from "./HomeHero";
import { CollectTopicsDialog, RecentReportsDialog } from "./HomeActionDialogs";
import { formatBeijingDate, parseDateValue } from "../utils/date";

const HOME_ITEMS_PER_PAGE = 5;
const HOME_ITEM_LIMIT = 30;

export function IntelligenceHomePage() {
  const [items, setItems] = useState<CollectedItem[]>([]);
  const [featuredPool, setFeaturedPool] = useState<CollectedItem[]>([]);
  const [itemTotal, setItemTotal] = useState(0);
  const [itemPage, setItemPage] = useState(1);
  const [itemsLoading, setItemsLoading] = useState(true);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [readingItem, setReadingItem] = useState<CollectedItem | null>(null);
  const [viewingReport, setViewingReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { success } = useToast();
  const [collectDialogOpen, setCollectDialogOpen] = useState(false);
  const [viewReportsOpen, setViewReportsOpen] = useState(false);
  const [collectionJustFinished, setCollectionJustFinished] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchDashboard()
      .then((dash) => {
        if (!active) return;
        setDashboard(dash);
        setError(null);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    // Large source/report inventories load independently so one slow endpoint
    // cannot hold the entire home page behind a spinner.
    void fetchFeaturedItems().then((data) => { if (active) setFeaturedPool(data); }).catch(() => {});
    void fetchReports(undefined, 7).then((data) => { if (active) setReports(data.reports); }).catch(() => {});
    void fetchSources().then((data) => { if (active) setSources(data); }).catch(() => {});
    void fetchTopics().then((data) => { if (active) setTopics(data); }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setItemsLoading(true);
    fetchItems({ page: itemPage, page_size: HOME_ITEMS_PER_PAGE })
      .then((itemList) => {
        if (!active) return;
        setItems(itemList.items);
        setItemTotal(Math.min(itemList.total, HOME_ITEM_LIMIT));
        setItemsError(null);
      })
      .catch((err) => {
        if (active) setItemsError(err instanceof Error ? err.message : "采集信息加载失败");
      })
      .finally(() => {
        if (active) setItemsLoading(false);
      });
    return () => { active = false; };
  }, [itemPage]);

  useEffect(() => {
    let active = true;
    const refreshAfterBackgroundCollection = async () => {
      const [itemList, featuredList, dash] = await Promise.all([
        fetchItems({ page: 1, page_size: HOME_ITEMS_PER_PAGE }),
        fetchFeaturedItems(),
        fetchDashboard(),
      ]);
      if (!active) return;
      setItemPage(1);
      setItems(itemList.items);
      setItemTotal(Math.min(itemList.total, HOME_ITEM_LIMIT));
      setFeaturedPool(featuredList);
      setDashboard(dash);
    };
    const handleUpdated = () => { void refreshAfterBackgroundCollection(); };
    window.addEventListener("collection-data-updated", handleUpdated);
    return () => {
      active = false;
      window.removeEventListener("collection-data-updated", handleUpdated);
    };
  }, []);

  // 为重点信息解析真实配图：缺图时从源头页面抓图/网络兜底，每条只尝试一次
  const imageResolveRequested = useRef(new Set<string>());
  useEffect(() => {
    const missing = featuredPool.filter(
      (i) => !i.featured_image_url && !imageResolveRequested.current.has(i.id),
    );
    if (missing.length === 0) return;
    const ids = missing.map((i) => i.id);
    ids.forEach((id) => imageResolveRequested.current.add(id));
    resolveFeaturedImages(ids)
      .then(({ images }) => {
        setFeaturedPool((prev) =>
          prev.map((i) => (images[i.id] ? { ...i, featured_image_url: images[i.id] } : i)),
        );
      })
      .catch(() => {});
  }, [featuredPool]);

  const sourceMap = useMemo(() => new Map(sources.map((s) => [s.id, s])), [sources]);
  const topicMap = useMemo(() => new Map(topics.map((t) => [t.id, t])), [topics]);
  const itemTotalPages = Math.max(1, Math.ceil(itemTotal / HOME_ITEMS_PER_PAGE));
  const safeItemPage = Math.min(itemPage, itemTotalPages);
  const featuredItems = useMemo(() => featuredPool.slice(0, 3), [featuredPool]);
  const featuredCards = useMemo(() => assignFeatureImages(featuredItems), [featuredItems]);
  const featuredGroups = useMemo(() => chunkItems(featuredCards, 3), [featuredCards]);
  const featuredSlideCount = Math.max(1, Math.ceil(featuredCards.length / 3));
  const featuredPage = Math.min(featuredSlideCount - 1, Math.floor(0 / 3));
  const completedReports = reports
    .filter((r) => r.status === "completed")
    .sort((a, b) => new Date(b.generated_at || b.created_at || 0).getTime() - new Date(a.generated_at || a.created_at || 0).getTime())
    .slice(0, 4);

  const RECENT_DAYS = 7;
  const recentReports = useMemo(() => {
    const cutoff = Date.now() - RECENT_DAYS * 24 * 60 * 60 * 1000;
    return reports
      .filter((r) => r.status === "completed" && (r.generated_at ? new Date(r.generated_at).getTime() > cutoff : new Date(r.created_at || 0).getTime() > cutoff))
      .sort((a, b) => new Date(b.generated_at || b.created_at || 0).getTime() - new Date(a.generated_at || a.created_at || 0).getTime())
      .slice(0, 4);
  }, [reports]);

  const handleCollect = useCallback(() => setCollectDialogOpen(true), []);
  const handleReports = useCallback(() => setViewReportsOpen(true), []);
  const openItemDetail = useCallback((item: CollectedItem) => {
    setReadingItem(item);
    void fetchItem(item.id)
      .then((fullItem) => setReadingItem((current) => current?.id === item.id ? fullItem : current))
      .catch(() => {
        // Keep the list payload visible if the detail request is unavailable.
      });
  }, []);

  const runCollection = useCallback(async (topicIds: string[]) => {
    if (!topicIds.length) return;
    try {
      let totalNew = 0;
      for (const topicId of topicIds) {
        const results = await collectTopic(topicId);
        totalNew += results.reduce((sum, r) => sum + r.items_new, 0);
      }
      const [itemList, featuredList, reportList, topicList, dash] = await Promise.all([
        fetchItems({ page: 1, page_size: HOME_ITEMS_PER_PAGE }),
        fetchFeaturedItems(),
        fetchReports(),
        fetchTopics(),
        fetchDashboard(),
      ]);
      setItems(itemList.items);
      setFeaturedPool(featuredList);
      setItemPage(1);
      setItemTotal(Math.min(itemList.total, HOME_ITEM_LIMIT));
      setReports(reportList.reports);
      setTopics(topicList);
      setDashboard(dash);
      setCollectionJustFinished(true);
      setCollectDialogOpen(false);
      success(`采集完成：新增 ${totalNew} 条情报`);
    } catch (err) {
      success(`采集失败：${err instanceof Error ? err.message : "未知错误"}`);
    }
  }, [success]);

  if (loading) return <div className="loading">加载今日情报概览...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!dashboard) return null;

  return (
    <div className="home-page">
      {/* Hero 区域 — 紧凑版 */}
      <HomeHero data={dashboard} onCollect={handleCollect} onReports={handleReports} reportsEnabled={recentReports.length > 0 || collectionJustFinished} />

      {/* Featured 重点情报 — 横版卡片 */}
      {featuredCards.length > 0 && (
        <section className="featured-section">
          <div className="featured-section-header">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Globe2 size={18} />
              <strong>重点情报</strong>
            </div>
            <span className="text-muted">高价值采集内容优先展示</span>
          </div>
          <div className="featured-cards-row">
            {featuredCards.slice(0, 3).map(({ item, imageUrl }, index) => {
              const source = sourceMap.get(item.source_id);
              const title = getDisplayTitle(item.title_zh || item.title);
              const summary = item.summary_zh || item.summary || item.content_zh || item.content || "";
              const date = item.published_at || item.collected_at;
              return (
                <article key={item.id} className="featured-card" onClick={() => openItemDetail(item)}>
                  <div className="featured-card-image" style={{ backgroundImage: `url(${imageUrl})` }} />
                  <div className="featured-card-body">
                    <span className="featured-card-date">
                      <CalendarDays size={13} />
                      {date ? formatBeijingDate(date, { month: "short", day: "numeric" }) : "未知日期"}
                    </span>
                    <strong className="featured-card-title">{clip(title, 60)}</strong>
                    <p className="featured-card-summary">{clip(summary, 160)}</p>
                    <div className="featured-card-meta">
                      <span>{source?.name || item.source_id}</span>
                      <span className="featured-card-read">
                        阅读全文 <ArrowRight size={13} />
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* 左右分栏 */}
      <section className="home-grid">
        <main className="home-news">
          <div className="section-title-row">
            <div>
              <h3><Newspaper size={18} /> 最新采集信息</h3>
              <p className="text-muted">保留最近 30 条采集结果，每页展示 5 条，优先显示中文译文和摘要。</p>
            </div>
          </div>

          {itemsError && <div className="error-banner">{itemsError}</div>}
          <div className={`news-feed${itemsLoading ? " news-feed--loading" : ""}`}>
            {items.map((item, index) => {
              const source = sourceMap.get(item.source_id);
              const title = getDisplayTitle(item.title_zh || item.title);
              const summary = item.summary_zh || item.summary || item.content_zh || item.content || "";
              const collectedDate = item.collected_at;
              const relativeTime = collectedDate ? getRelativeTime(parseDateValue(collectedDate)) : "未知";
              return (
                <article key={item.id} className={`news-entry${index === 0 ? " news-entry--lead" : ""}`}>
                  <div className="news-timeline">
                    <div className="news-timeline-line" />
                    <div className="news-timeline-dot" />
                  </div>
                  <div className="news-entry-main">
                    <div className="news-entry-meta">
                      <span className="news-source-icon">{source?.name?.charAt(0) || "?"}</span>
                      <span>{source?.name || item.source_id}</span>
                      {item.category && <span className="news-badge">{item.category}</span>}
                      {(item.title_zh || item.summary_zh || item.content_zh) ? (
                        <span className="news-badge news-badge--lang">中文译文</span>
                      ) : item.language ? (
                        <span className="news-badge news-badge--lang">{item.language}</span>
                      ) : null}
                      <span className="news-relative-time">入库 {relativeTime}</span>
                    </div>
                    <button type="button" className="news-title-button" onClick={() => openItemDetail(item)}>
                      {title}
                    </button>
                    {summary && <p>{clip(summary, index === 0 ? 240 : 150)}</p>}
                  </div>
                  <button type="button" className="news-read-button" onClick={() => openItemDetail(item)}>
                    <BookOpenText size={14} /> 全文
                  </button>
                </article>
              );
            })}
            {itemsLoading && <div className="empty-inline">正在更新采集信息...</div>}
            {!itemsLoading && items.length === 0 && <div className="empty-inline">暂无采集信息</div>}
          </div>
          {itemTotal > HOME_ITEMS_PER_PAGE && (
            <div className="report-pager">
              <button type="button" className="pager-button" disabled={safeItemPage <= 1} onClick={() => setItemPage(Math.max(1, safeItemPage - 1))}>
                上一页
              </button>
              <span>{safeItemPage} / {itemTotalPages}</span>
              <button type="button" className="pager-button" disabled={safeItemPage >= itemTotalPages} onClick={() => setItemPage(Math.min(itemTotalPages, safeItemPage + 1))}>
                下一页
              </button>
            </div>
          )}
        </main>

        <aside className="home-side">
          <section className="home-panel">
            <h3><FileText size={17} /> 分析报告摘要</h3>
            <div className="report-summary-list">
              {completedReports.map((report) => (
                <button key={report.id} type="button" className="report-summary-card" onClick={() => setViewingReport(report)}>
                  <span className="report-topic">{topicMap.get(report.topic_id)?.name || report.topic_name || report.topic_id}</span>
                  <strong>{report.title}</strong>
                  <p>{extractFinding(report.summary || report.content || "暂无关键发现")}</p>
                  <span className="read-more">阅读全文 <ArrowRight size={13} /></span>
                </button>
              ))}
              {completedReports.length === 0 && <div className="empty-inline">暂无已完成报告</div>}
            </div>
          </section>

          <section className="home-panel">
            <h3><Globe2 size={17} /> 活跃主题</h3>
            <div className="topic-snapshot-list">
              {topics.filter((t) => t.is_active !== false).slice(0, 6).map((topic) => (
                <div key={topic.id} className="topic-snapshot">
                  <strong>{topic.name}</strong>
                  <span>{topic.current_item_count.toLocaleString()} 条</span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>

      {readingItem && (
        <ItemDetailModal item={readingItem} sources={sources} onClose={() => setReadingItem(null)} />
      )}
      {viewingReport && (
        <ReportViewerModal report={viewingReport} onClose={() => setViewingReport(null)} />
      )}
      <CollectTopicsDialog
        open={collectDialogOpen}
        topics={topics}
        onClose={() => setCollectDialogOpen(false)}
        onStart={runCollection}
      />
      <RecentReportsDialog
        open={viewReportsOpen}
        reports={recentReports}
        onClose={() => setViewReportsOpen(false)}
        onView={(report) => setViewingReport(report)}
      />
    </div>
  );
}

function clip(text: string, max: number) {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length > max ? `${compact.slice(0, max)}...` : compact;
}

function chunkItems<T>(items: T[], size: number) {
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function getRelativeTime(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;
  return formatBeijingDate(date, { month: "short", day: "numeric" });
}

function extractFinding(text: string) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*#\d.\s]+/, "").trim())
    .filter(Boolean)
    .filter((line) => !/^(```|摘要|报告|关键发现)$/i.test(line));
  const picked = lines.find((line) => /发现|风险|影响|措施|政策|贸易|关税|TBT|SPS|壁垒/.test(line)) || lines[0] || text;
  return clip(picked, 170);
}

const FEATURE_IMAGE_POOL = [
  "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1589923188900-85dae523342b?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1581093588401-fbb62a02f120?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1494412651409-8963ce7935a7?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1566576721346-d4a3b4eaeb55?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1462899006636-339e08d1844e?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1523741543316-beb7fc7023d8?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1581093458791-9d15482442f6?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1532635042-a6f6ad4745f9?auto=format&fit=crop&w=900&q=82",
  "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=900&q=82",
];

function assignFeatureImages(items: CollectedItem[]) {
  const used = new Set<string>();
  return items.map((item, index) => {
    // 优先使用从源头解析下载的真实配图；缺图时退回按主题关键词的图池兜底
    const candidates = item.featured_image_url
      ? [item.featured_image_url]
      : pickFeatureImageCandidates(item);
    const imageUrl = candidates.find((url) => !used.has(url))
      || FEATURE_IMAGE_POOL.find((url) => !used.has(url))
      || FEATURE_IMAGE_POOL[index % FEATURE_IMAGE_POOL.length];
    used.add(imageUrl);
    return { item, imageUrl };
  });
}

function pickFeatureImageCandidates(item: CollectedItem) {
  const text = `${item.title} ${item.title_zh || ""} ${item.summary || ""} ${item.summary_zh || ""} ${item.content || ""}`.toLowerCase();
  if (/metal|steel|aluminum|mining|mine|ore|矿|钢|铝|金属|机械/.test(text)) {
    return [
      "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=82",
      "https://images.unsplash.com/photo-1462899006636-339e08d1844e?auto=format&fit=crop&w=900&q=82",
    ];
  }
  if (/food|agri|farm|sps|sanitary|phytosanitary|食品|农|卫生|检疫/.test(text)) {
    return [
      "https://images.unsplash.com/photo-1589923188900-85dae523342b?auto=format&fit=crop&w=900&q=82",
      "https://images.unsplash.com/photo-1523741543316-beb7fc7023d8?auto=format&fit=crop&w=900&q=82",
    ];
  }
  if (/standard|technical|tbt|regulation|lab|certif|标准|技术|合格评定|认证/.test(text)) {
    return [
      "https://images.unsplash.com/photo-1581093588401-fbb62a02f120?auto=format&fit=crop&w=900&q=82",
      "https://images.unsplash.com/photo-1581093458791-9d15482442f6?auto=format&fit=crop&w=900&q=82",
    ];
  }
  if (/customs|port|container|shipping|import|export|海关|港口|进出口|集装箱|物流/.test(text)) {
    return [
      "https://images.unsplash.com/photo-1494412651409-8963ce7935a7?auto=format&fit=crop&w=900&q=82",
      "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=900&q=82",
    ];
  }
  if (/tariff|trade|policy|section|关税|贸易|政策|公告/.test(text)) {
    return [
      "https://images.unsplash.com/photo-1566576721346-d4a3b4eaeb55?auto=format&fit=crop&w=900&q=82",
      "https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=900&q=82",
    ];
  }
  return FEATURE_IMAGE_POOL;
}
