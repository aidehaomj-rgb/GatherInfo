import React, { useState, useCallback, useMemo } from "react";
import { Download, FileSpreadsheet, FileJson, FileText, FileCode } from "lucide-react";
import type { CollectedItem } from "../types";

export type ExportFormat = "csv" | "xlsx" | "json" | "markdown";

interface ExportPanelProps {
  items: CollectedItem[];
  defaultFormat?: ExportFormat;
  filename?: string;
}

const FORMAT_META: Record<ExportFormat, { label: string; ext: string; mime: string; icon: React.ReactNode }> = {
  csv: { label: "CSV", ext: ".csv", mime: "text/csv;charset=utf-8;", icon: <FileSpreadsheet size={16} /> },
  xlsx: { label: "XLSX", ext: ".xlsx", mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon: <FileSpreadsheet size={16} /> },
  json: { label: "JSON", ext: ".json", mime: "application/json;charset=utf-8;", icon: <FileJson size={16} /> },
  markdown: { label: "Markdown", ext: ".md", mime: "text/markdown;charset=utf-8;", icon: <FileText size={16} /> },
};

function escapeCsvCell(cell: string): string {
  const needsQuote = /[",\n\r]/.test(cell);
  if (needsQuote) {
    return '"' + cell.replace(/"/g, '""') + '"';
  }
  return cell;
}

function toCsv(items: CollectedItem[]): string {
  const headers = ["ID", "Title", "Content", "URL", "Language", "Category", "Tags", "CollectedAt", "PublishedAt"];
  const rows = items.map((it) => [
    it.id,
    it.title || "",
    (it.content || "").replace(/\s+/g, " "),
    it.url || "",
    it.language || "",
    it.category || "",
    it.tags.map((t) => t.value).join("; "),
    it.collected_at || "",
    it.published_at || "",
  ]);
  return [headers, ...rows].map((r) => r.map(escapeCsvCell).join(",")).join("\n");
}

function toJson(items: CollectedItem[]): string {
  return JSON.stringify(items, null, 2);
}

function toMarkdown(items: CollectedItem[]): string {
  const lines: string[] = ["# 导出数据\n"];
  items.forEach((it, idx) => {
    lines.push(`## ${idx + 1}. ${it.title || "无标题"}`);
    if (it.url) lines.push(`- **链接**: ${it.url}`);
    if (it.language) lines.push(`- **语言**: ${it.language}`);
    if (it.category) lines.push(`- **分类**: ${it.category}`);
    if (it.tags.length) lines.push(`- **标签**: ${it.tags.map((t) => t.value).join(", ")}`);
    if (it.published_at) lines.push(`- **发布时间**: ${it.published_at}`);
    if (it.collected_at) lines.push(`- **采集时间**: ${it.collected_at}`);
    if (it.content) lines.push(`\n${it.content}\n`);
    lines.push("---\n");
  });
  return lines.join("\n");
}

function toXlsxBlob(items: CollectedItem[]): Blob {
  const headers = ["ID", "Title", "Content", "URL", "Language", "Category", "Tags", "CollectedAt", "PublishedAt"];
  const rows = items.map((it) => [
    it.id,
    it.title || "",
    (it.content || "").replace(/\s+/g, " "),
    it.url || "",
    it.language || "",
    it.category || "",
    it.tags.map((t) => t.value).join("; "),
    it.collected_at || "",
    it.published_at || "",
  ]);
  const html = `
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
<head><meta charset="UTF-8"><style>td{border:1px solid #ccc;padding:4px;}</style></head>
<body><table>
<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
<tbody>
${rows.map((r) => `<tr>${r.map((c) => `<td>${c.replace(/</g, "&lt;")}</td>`).join("")}</tr>`).join("\n")}
</tbody></table></body></html>`;
  return new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
}

export const ExportPanel: React.FC<ExportPanelProps> = ({
  items,
  defaultFormat = "csv",
  filename = "export",
}) => {
  const [format, setFormat] = useState<ExportFormat>(defaultFormat);
  const [busy, setBusy] = useState(false);

  const meta = FORMAT_META[format];

  const doExport = useCallback(() => {
    if (!items.length) return;
    setBusy(true);
    let blob: Blob;
    let ext = meta.ext;
    let mime = meta.mime;

    switch (format) {
      case "csv":
        blob = new Blob(["\uFEFF" + toCsv(items)], { type: mime });
        break;
      case "json":
        blob = new Blob([toJson(items)], { type: mime });
        break;
      case "markdown":
        blob = new Blob([toMarkdown(items)], { type: mime });
        break;
      case "xlsx":
        blob = toXlsxBlob(items);
        ext = ".xls";
        break;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setBusy(false);
  }, [items, format, meta, filename]);

  const formats = useMemo(() => Object.keys(FORMAT_META) as ExportFormat[], []);

  return (
    <div className="export-panel">
      <div className="export-panel-header">
        <FileCode size={16} />
        <span>导出数据</span>
        <span className="export-count">{items.length} 条</span>
      </div>
      <div className="export-formats">
        {formats.map((f) => {
          const m = FORMAT_META[f];
          const active = f === format;
          return (
            <button
              key={f}
              type="button"
              className={["export-format-btn", active ? "active" : ""].join(" ")}
              onClick={() => setFormat(f)}
              aria-pressed={active}
            >
              {m.icon}
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className="export-action-btn"
        onClick={doExport}
        disabled={busy || items.length === 0}
      >
        <Download size={16} />
        <span>{busy ? "导出中…" : `导出 ${meta.label}`}</span>
      </button>
    </div>
  );
};
