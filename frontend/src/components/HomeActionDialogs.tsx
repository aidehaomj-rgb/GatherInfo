 import { useEffect, useState } from "react";
 import { X, Zap, FileText, Loader2, CalendarDays } from "lucide-react";
 import type { Topic, Report } from "../types";
 import { formatBeijingDateTime } from "../utils/date";

 type CollectTopicsDialogProps = {
   open: boolean;
   topics: Topic[];
   onClose: () => void;
   onStart: (topicIds: string[]) => Promise<void>;
 };

 export function CollectTopicsDialog({ open, topics, onClose, onStart }: CollectTopicsDialogProps) {
   const [selected, setSelected] = useState<string[]>([]);
   const [loading, setLoading] = useState(false);

   useEffect(() => {
     if (!open) setSelected([]);
   }, [open]);

   if (!open) return null;

   const toggle = (id: string) => {
     setSelected((prev) =>
       prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
     );
   };
   const allSelected = topics.length > 0 && topics.every((t) => selected.includes(t.id));
   const toggleAll = () => setSelected(allSelected ? [] : topics.map((t) => t.id));

   const handleStart = async () => {
     if (selected.length === 0) return;
     setLoading(true);
     try {
       await onStart(selected);
     } finally {
       setLoading(false);
     }
   };

   return (
     <div className="modal-overlay" onClick={onClose}>
       <div className="modal" style={{ width: 520 }} onClick={(e) => e.stopPropagation()}>
         <div className="modal-header-with-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
           <h3><Zap size={16} /> 选择采集主题</h3>
           <button type="button" className="btn-icon" onClick={onClose} aria-label="关闭">
             <X size={16} />
           </button>
         </div>
         <p className="text-muted" style={{ fontSize: "0.82rem", marginBottom: 12 }}>
           手动启动一次采集，完成后可在右侧查看最近一周的采集报告。
         </p>
         <div
           className="form-group"
           style={{
             maxHeight: 320,
             overflowY: "auto",
             border: "1px solid var(--line)",
             borderRadius: "var(--radius)",
             padding: "8px 12px",
           }}
         >
           {topics.length > 0 && (
             <label
               className="checkbox-label"
               style={{
                 display: "flex",
                 alignItems: "center",
                 gap: 8,
                 padding: "6px 0",
                 borderBottom: "1px solid var(--line-light)",
                 marginBottom: 4,
                 cursor: "pointer",
               }}
             >
               <input type="checkbox" checked={allSelected} onChange={toggleAll} />
               <strong>{allSelected ? "取消全选" : "全选所有主题"}</strong>
             </label>
           )}
           {topics.map((t) => (
             <label
               key={t.id}
               className="checkbox-label"
               style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "6px 0", cursor: "pointer" }}
             >
               <input type="checkbox" checked={selected.includes(t.id)} onChange={() => toggle(t.id)} />
               <div style={{ flex: 1 }}>
                 <div style={{ fontWeight: 500 }}>{t.name}</div>
                 <div className="text-muted small" style={{ fontSize: "0.75rem" }}>
                   {t.keywords.slice(0, 5).join(", ")} · 累计 {t.total_items_collected} 条
                 </div>
               </div>
             </label>
           ))}
           {topics.length === 0 && <div className="text-muted small">暂无主题</div>}
         </div>
         <div className="modal-actions">
           <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
             取消
           </button>
           <button
             type="button"
             className="btn btn-primary"
             onClick={handleStart}
             disabled={loading || selected.length === 0}
           >
             {loading ? (
               <><Loader2 size={14} className="spin" /> 采集中...</>
             ) : (
               <>开始采集 {selected.length > 0 && `(${selected.length})`}</>
             )}
           </button>
         </div>
       </div>
     </div>
   );
 }

 type RecentReportsDialogProps = {
   open: boolean;
   reports: Report[];
   onClose: () => void;
   onView: (report: Report) => void;
 };

 export function RecentReportsDialog({ open, reports, onClose, onView }: RecentReportsDialogProps) {
   if (!open) return null;
   return (
     <div className="modal-overlay" onClick={onClose}>
       <div className="modal" style={{ width: 640 }} onClick={(e) => e.stopPropagation()}>
         <div className="modal-header-with-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
           <h3><FileText size={16} /> 最近一周报告</h3>
           <button type="button" className="btn-icon" onClick={onClose} aria-label="关闭">
             <X size={16} />
           </button>
         </div>
         {reports.length === 0 ? (
           <div className="empty" style={{ padding: 24 }}>暂无最近一周的采集报告</div>
         ) : (
           <div className="report-summary-list" style={{ maxHeight: 420, overflowY: "auto" }}>
             {reports.map((r) => (
               <button
                 key={r.id}
                 type="button"
                 className="report-summary-card"
                 onClick={() => {
                   onView(r);
                   onClose();
                 }}
               >
                 <span className="report-topic">{r.topic_name || r.topic_id}</span>
                 <strong>{r.title}</strong>
                 <p>{r.summary || r.content?.slice(0, 160) || "暂无摘要"}</p>
                 <span className="text-muted small">
                   <CalendarDays size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                   {r.generated_at ? formatBeijingDateTime(r.generated_at) : "未知时间"}
                 </span>
               </button>
             ))}
           </div>
         )}
         <div className="modal-actions">
           <button type="button" className="btn btn-ghost" onClick={onClose}>关闭</button>
         </div>
       </div>
     </div>
   );
 }
