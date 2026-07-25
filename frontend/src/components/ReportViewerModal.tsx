import { Download } from "lucide-react";
import type { Report } from "../types";
import { RenderMarkdown } from "./shared/RenderMarkdown";
import { formatBeijingDateTime } from "../utils/date";

interface Props {
  report: Report;
  onClose: () => void;
}

export function ReportViewerModal({ report, onClose }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 800, maxWidth: "95vw" }}>
        <div className="modal-header-with-actions">
          <h3>{report.title}</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => {
              const blob = new Blob([report.content || ""], { type: "text/markdown" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url; a.download = `${report.title}.md`; a.click();
              URL.revokeObjectURL(url);
            }}>
              <Download size={12} /> 下载
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>关闭</button>
          </div>
        </div>
        <div className="report-meta" style={{ fontSize: "0.8rem", color: "var(--ink-muted)", marginBottom: 16, padding: "8px 0", borderBottom: "1px solid var(--line-light)" }}>
          基于 {report.item_count} 条采集信息
          {report.generated_at && <> · {formatBeijingDateTime(report.generated_at)}</>}
          {report.tokens_used > 0 && <> · 使用 {report.tokens_used} tokens</>}
        </div>
        <div className="report-content" style={{ fontSize: "0.85rem", lineHeight: 1.7, maxHeight: "60vh", overflowY: "auto" }}>
          {report.content ? (
            <RenderMarkdown content={report.content} />
          ) : (
            <p className="text-muted">（暂无内容）</p>
          )}
        </div>
      </div>
    </div>
  );
}
