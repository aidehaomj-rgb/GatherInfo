import React, { useState, useEffect, useCallback, useRef } from "react";
import { PenLine, Eye, Save, Trash2 } from "lucide-react";
import { formatBeijingDateTime } from "../utils/date";

interface NoteEditorProps {
  itemId: string;
  className?: string;
}

const STORAGE_KEY = "traderadar_notes";

interface NoteRecord {
  content: string;
  updatedAt: string;
}

function readNotes(): Record<string, NoteRecord> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, NoteRecord>;
  } catch {
    return {};
  }
}

function writeNotes(notes: Record<string, NoteRecord>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
}

function simpleMarkdownToHtml(md: string): string {
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^###### (.*$)/gim, "<h6>$1</h6>")
    .replace(/^##### (.*$)/gim, "<h5>$1</h5>")
    .replace(/^#### (.*$)/gim, "<h4>$1</h4>")
    .replace(/^### (.*$)/gim, "<h3>$1</h3>")
    .replace(/^## (.*$)/gim, "<h2>$1</h2>")
    .replace(/^# (.*$)/gim, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/gim, "<em>$1</em>")
    .replace(/`(.*?)`/gim, "<code>$1</code>")
    .replace(/^\> (.*$)/gim, "<blockquote>$1</blockquote>")
    .replace(/^- (.*$)/gim, "<li>$1</li>")
    .replace(/^\d+\. (.*$)/gim, "<li>$1</li>")
    .replace(/\n/gim, "<br>");
  return html;
}

export const NoteEditor: React.FC<NoteEditorProps> = ({ itemId, className = "" }) => {
  const [content, setContent] = useState<string>("");
  const [preview, setPreview] = useState<boolean>(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const notes = readNotes();
    const rec = notes[itemId];
    if (rec) {
      setContent(rec.content);
      setSavedAt(rec.updatedAt);
    } else {
      setContent("");
      setSavedAt(null);
    }
  }, [itemId]);

  const save = useCallback(() => {
    const notes = readNotes();
    const updatedAt = new Date().toISOString();
    const next = { ...notes, [itemId]: { content, updatedAt } };
    writeNotes(next);
    setSavedAt(updatedAt);
  }, [itemId, content]);

  const clear = useCallback(() => {
    const notes = readNotes();
    const next = { ...notes };
    delete next[itemId];
    writeNotes(next);
    setContent("");
    setSavedAt(null);
  }, [itemId]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        save();
      }
    },
    [save]
  );

  return (
    <div className={["note-editor", className].join(" ")}>
      <div className="note-editor-toolbar">
        <div className="note-editor-title">
          <PenLine size={14} />
          <span>笔记</span>
        </div>
        <div className="note-editor-actions">
          <button
            type="button"
            className={["note-toggle-btn", preview ? "active" : ""].join(" ")}
            onClick={() => setPreview((p) => !p)}
            title={preview ? "编辑" : "预览"}
          >
            {preview ? <PenLine size={14} /> : <Eye size={14} />}
            <span>{preview ? "编辑" : "预览"}</span>
          </button>
          <button
            type="button"
            className="note-save-btn"
            onClick={save}
            title="保存 (Ctrl+Enter)"
          >
            <Save size={14} />
            <span>保存</span>
          </button>
          <button
            type="button"
            className="note-clear-btn"
            onClick={clear}
            title="清空"
            disabled={!content}
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {preview ? (
        <div
          className="note-preview"
          dangerouslySetInnerHTML={{ __html: simpleMarkdownToHtml(content || "*暂无内容*") }}
        />
      ) : (
        <textarea
          ref={textareaRef}
          className="note-textarea"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="在此添加批注… 支持简单 Markdown 语法\nCtrl+Enter 保存"
          rows={6}
        />
      )}

      {savedAt && (
        <div className="note-saved-hint">
          已保存 {formatBeijingDateTime(savedAt)}
        </div>
      )}
    </div>
  );
};
