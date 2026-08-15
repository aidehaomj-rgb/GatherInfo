import { Search, Filter, X } from "lucide-react";
import type { Tag, Topic, Source } from "../types";

interface ItemFilterBarProps {
  query: string;
  onQueryChange: (v: string) => void;
  filterTopic: string;
  onFilterTopicChange: (v: string) => void;
  filterSource: string;
  onFilterSourceChange: (v: string) => void;
  filterBatch: string;
  onFilterBatchChange: (v: string) => void;
  filterTag: string;
  onFilterTagChange: (v: string) => void;
  topics: Topic[];
  sources: Source[];
  sourceCounts: Record<string, number>;
  batchOptions: { batch_id: string; label: string }[];
  tags: Tag[];
}

export function ItemFilterBar({
  query,
  onQueryChange,
  filterTopic,
  onFilterTopicChange,
  filterSource,
  onFilterSourceChange,
  filterBatch,
  onFilterBatchChange,
  filterTag,
  onFilterTagChange,
  topics,
  sources,
  sourceCounts,
  batchOptions,
  tags,
}: ItemFilterBarProps) {
  const hasFilters =
    query || filterTag || filterSource || filterTopic || filterBatch;

  const clearFilters = () => {
    onQueryChange("");
    onFilterTagChange("");
    onFilterSourceChange("");
    onFilterTopicChange("");
    onFilterBatchChange("");
  };

  return (
    <div className="search-bar">
      <div className="search-input-wrapper">
        <Search size={14} className="search-icon" />
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="搜索标题或内容..."
          className="search-input"
        />
        {query && (
          <button
            type="button"
            className="btn-icon"
            onClick={() => onQueryChange("")}
          >
            <X size={14} />
          </button>
        )}
      </div>

      <select value={filterTopic} onChange={(e) => onFilterTopicChange(e.target.value)}>
        <option value="">全部主题</option>
        {topics.map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>

      <select value={filterSource} onChange={(e) => onFilterSourceChange(e.target.value)}>
        <option value="">全部信息源</option>
        {sources.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({sourceCounts[s.id] || 0})
          </option>
        ))}
      </select>

      <select value={filterBatch} onChange={(e) => onFilterBatchChange(e.target.value)}>
        <option value="">全部批次</option>
        {batchOptions.map((b) => (
          <option key={b.batch_id} value={b.batch_id}>{b.label}</option>
        ))}
      </select>

      <select value={filterTag} onChange={(e) => onFilterTagChange(e.target.value)}>
        <option value="">全部标签</option>
        {tags.slice(0, 50).map((t) => (
          <option key={t.id} value={t.id}>
            {t.id} ({t.item_count})
          </option>
        ))}
      </select>

      {hasFilters && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={clearFilters}>
          <Filter size={12} /> 清除过滤
        </button>
      )}
    </div>
  );
}
