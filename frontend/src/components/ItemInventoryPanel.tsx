import { CalendarRange, Database, FolderTree, Layers3, RefreshCw } from "lucide-react";
import type { ItemInventory, InventoryRow } from "../types";
import { formatBeijingDateTime } from "../utils/date";

interface Props {
  inventory: ItemInventory | null;
  loading: boolean;
  onRefresh: () => void;
}

const GROUPS: { key: keyof Pick<ItemInventory, "topics" | "categories" | "batches" | "sources" | "statuses">; label: string; icon: typeof FolderTree }[] = [
  { key: "topics", label: "按主题", icon: FolderTree },
  { key: "categories", label: "按类别", icon: Layers3 },
  { key: "batches", label: "按批次", icon: CalendarRange },
  { key: "sources", label: "按信息源", icon: Database },
  { key: "statuses", label: "按状态", icon: Layers3 },
];

export function ItemInventoryPanel({ inventory, loading, onRefresh }: Props) {
  return (
    <section className="item-inventory-panel" aria-label="采集条目全面整理">
      <div className="item-inventory-header">
        <div>
          <h3><Layers3 size={17} /> 全面整理</h3>
          <p className="text-muted small">以下数量均来自当前已存储的采集条目，不包含已删除信息或历史累计计数。</p>
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={onRefresh} disabled={loading}>
          <RefreshCw size={13} className={loading ? "spin" : ""} /> 刷新统计
        </button>
      </div>

      {loading && !inventory ? (
        <div className="loading">正在整理当前条目...</div>
      ) : !inventory ? (
        <div className="empty-inline">暂无可整理的采集条目。</div>
      ) : (
        <>
          <div className="item-inventory-total">
            <Database size={20} />
            <div><strong>{inventory.total_items.toLocaleString()}</strong><span>当前存储条目</span></div>
            {inventory.generated_at && <time>统计于 {formatBeijingDateTime(inventory.generated_at)}</time>}
          </div>
          <div className="item-inventory-grid">
            {GROUPS.map(({ key, label, icon: Icon }) => (
              <InventoryGroup key={key} label={label} icon={Icon} rows={inventory[key]} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function InventoryGroup({ label, icon: Icon, rows }: { label: string; icon: typeof FolderTree; rows: InventoryRow[] }) {
  return (
    <div className="item-inventory-group">
      <h4><Icon size={14} /> {label}</h4>
      {rows.length === 0 ? <span className="text-muted small">暂无条目</span> : (
        <div className="item-inventory-rows">
          {rows.slice(0, 12).map((row) => (
            <div key={row.id} className="item-inventory-row">
              <span title={row.label}>{row.label}</span>
              <strong>{row.count.toLocaleString()}</strong>
            </div>
          ))}
          {rows.length > 12 && <span className="text-muted small">还有 {rows.length - 12} 项，请使用筛选条件查看。</span>}
        </div>
      )}
    </div>
  );
}
