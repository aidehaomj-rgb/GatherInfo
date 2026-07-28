import { FileText, Trash2, Eye, Download } from "lucide-react";
import type { Report } from "../types";
import { StatusBadge } from "./shared/StatusBadge";
import { formatBeijingDateTime } from "../utils/date";

interface ReportCardProps {
  report: Report;
  onView: (r: Report) => void;
  onDelete: (id: string) => void;
  onExport: (id: string) => void;
  onDownload: (id: string, fmt: string) => void;
  exportingId: string | null;
}

export function ReportCard({
  report: r,
  onView,
  onDelete,
  onExport,
  onDownload,
  exportingId,
}: ReportCardProps) {
  const statusVariant =
    r.status === "completed"
      ? "completed"
      : r.status === "failed"
        ? "failed"
        : "running";

  return (
    <article className="report-item">
      <div className="report-item-header">
        <div className="report-item-title">
          <FileText size={16} />
          <span>{r.title}</span>
        </div>
        <StatusBadge status={statusVariant as any} />
      </div>
      <div className="report-item-meta">
        <span>
          {r.topic_name && <>主题: {r.topic_name}</>}
          {!r.topic_name && r.topic_id && <>主题: {r.topic_id}</>}
        </span>
        <span>生成时基于 {r.item_count} 条信息</span>
        {r.generated_at && (
          <span>{formatBeijingDateTime(r.generated_at)}</span>
        )}
        {r.tokens_used > 0 && (
          <span className="text-muted">{r.tokens_used} tokens</span>
        )}
      </div>
      <div className="report-item-footer">
        <button
          type="button"
          className="btn btn-sm btn-primary"
          onClick={() => onView(r)}
          disabled={r.status !== "completed"}
        >
          <Eye size={12} /> 查看报告
        </button>
        {r.status === "completed" &&
        r.output_files &&
        Object.keys(r.output_files).length > 0
          ? Object.keys(r.output_files).map((fmt) => (
              <a
                key={fmt}
                className="btn btn-sm btn-ghost"
                href={onDownload as any}
                onClick={(e) => {
                  e.preventDefault();
                  onDownload(r.id, fmt);
                }}
              >
                <Download size={12} /> {fmt.toUpperCase()}
              </a>
            ))
          : r.status === "completed" && (
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => onExport(r.id)}
                disabled={exportingId === r.id}
              >
                <Download size={12} />{" "}
                {exportingId === r.id ? "导出中…" : "导出文件"}
              </button>
            )}
        <button
          type="button"
          className="btn btn-sm btn-danger"
          onClick={() => onDelete(r.id)}
        >
          <Trash2 size={12} /> 删除
        </button>
      </div>
    </article>
  );
}
