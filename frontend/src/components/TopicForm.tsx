import { useState } from "react";
import type { Topic, ModelConfig, Source } from "../types";
import {
  DESCRIPTION_PROMPT_TEMPLATES,
  KEYWORD_WEIGHT_TEMPLATES,
} from "../templates";
import { SourceSelector } from "./SourceSelector";

/** Score templates against current keywords; return top-3 recommendations (for ★ marking). */
function recommendTemplates(keywords: string[]): { label: string; value: string; score: number }[] {
  if (!keywords.length) return [];
  const allTemplates = [...DESCRIPTION_PROMPT_TEMPLATES, ...KEYWORD_WEIGHT_TEMPLATES];
  return allTemplates
    .map((t) => {
      const label = t.label.toLowerCase();
      const value = t.value.toLowerCase();
      let score = 0;
      for (const kw of keywords) {
        const k = kw.toLowerCase();
        if (label.includes(k)) score += 3;
        if (value.includes(k)) score += 2;
      }
      const valueWords = value.split(/[\s,\u3001]+/);
      for (const w of valueWords) {
        for (const kw of keywords) {
          if (w.includes(kw.toLowerCase()) || kw.toLowerCase().includes(w)) score += 1;
        }
      }
      return { ...t, score };
    })
    .filter((t) => t.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
}

type TopicFormProps = {
  topic: Topic | null;
  sources: Source[];
  models: ModelConfig[];
  categories: { id: string; name: string }[];
  onSave: (data: Partial<Topic>) => Promise<void>;
  onClose: () => void;
};

export function TopicForm({
  topic,
  sources,
  models,
  categories,
  onSave,
  onClose,
}: TopicFormProps) {
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(topic?.name ?? "");
  const [desc, setDesc] = useState(topic?.description ?? "");
  const [categoryId, setCategoryId] = useState(topic?.category_id ?? "");
  const [keywords, setKeywords] = useState((topic?.keywords ?? []).join(", "));
  const [keywordTags, setKeywordTags] = useState(
    ((topic as any)?.keyword_tags ?? [])
      .map((kt: any) => `${kt.keyword}:${kt.weight}`)
      .join("\n"),
  );
  const [descriptionPrompt, setDescriptionPrompt] = useState(
    (topic as any)?.description_prompt ?? "",
  );
  const [collectWindowDays, setCollectWindowDays] = useState<number>(
    (topic as any)?.collect_window_days ?? 7,
  );
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>(
    topic?.source_ids ?? [],
  );
  const [targetUrls, setTargetUrls] = useState(
    (topic?.target_urls ?? []).join("\n"),
  );
  const [cron, setCron] = useState(topic?.schedule_cron ?? "");
  const [autoReport, setAutoReport] = useState(topic?.auto_report ?? false);
  const [autoReportModelId, setAutoReportModelId] = useState(
    topic?.auto_report_model_id ?? models.find((m) => m.is_default)?.id ?? "",
  );
  const [autoTags, setAutoTags] = useState(
    (topic?.auto_tag_rules ?? [])
      .map((r) => `${r.keyword}:${r.tag}`)
      .join(", "),
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        name,
        category_id: categoryId || null,
        description: desc || null,
        keywords: keywords
          .split(/[,，]/)
          .map((s) => s.trim())
          .filter(Boolean),
        keyword_tags: keywordTags
          ? keywordTags
              .split(/\r?\n/)
              .map((s: string) => {
                const [kw, w] = s.split(/[:：]/);
                return {
                  keyword: kw?.trim() || "",
                  weight: parseFloat(w?.trim() || "1") || 1,
                };
              })
              .filter((r: { keyword: string; weight: number }) => r.keyword)
          : null,
        description_prompt: descriptionPrompt || null,
        source_ids: selectedSourceIds.length ? selectedSourceIds : null,
        collect_window_days: Number.isFinite(collectWindowDays)
          ? collectWindowDays
          : 7,
        target_urls: targetUrls
          ? targetUrls
              .split(/\r?\n/)
              .map((s) => s.trim())
              .filter(Boolean)
          : null,
        schedule_cron: cron || null,
        is_scheduled: !!cron,
        auto_report: autoReport,
        auto_report_model_id: autoReport ? autoReportModelId || null : null,
        auto_tag_rules: autoTags
          ? autoTags
              .split(/[,，]/)
              .map((s) => {
                const [kw, tag] = s.trim().split(/[:：]/);
                return { keyword: kw?.trim() ?? "", tag: tag?.trim() ?? "" };
              })
              .filter((r: { keyword: string; tag: string }) => r.keyword && r.tag)
          : null,
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失败");
    }
    setSaving(false);
  };

  const activeSources = sources.filter(
    (source) => source.is_active && (source.is_configured || selectedSourceIds.includes(source.id)),
  );
  const kwList = keywords.split(/[,\u3001\s]+/).filter(Boolean);
  const recs = recommendTemplates(kwList);
  const recLabels = new Set(recs.map((r) => r.label));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 640 }}
      >
        <div className="modal-header-with-actions">
          <h3>{topic ? "编辑主题" : "新建主题"}</h3>
          <span className="text-muted small">
            输入关键词、选择信息源并配置高级选项，创建精准的采集监控主题
          </span>
        </div>

        <div className="form-grid">
          <label>
            主题名称 <span className="text-red">*</span>{" "}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：中美贸易政策监控"
              autoFocus
            />
          </label>
          <label>
            分类{" "}
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">-- 无 --</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="span-2">
            关键词 (逗号分隔) <span className="text-red">*</span>{" "}
            <input
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="例如：tariffs, trade war, semiconductor sanctions, export control"
            />
            {recs.length > 0 && (
              <div style={{ fontSize: "0.75rem", marginTop: 4 }}>
                <span className="text-muted">推荐模板：</span>
                {recs.map((r, i) => (
                  <span key={i}>
                    <button
                      type="button"
                      className="chip-link"
                      onClick={(e) => {
                        e.preventDefault();
                        const existing = keywords
                          .split(/[,，\s]+/)
                          .filter(Boolean);
                        const recKws = r.value
                          .split(/[,\s]+/)
                          .filter(Boolean);
                        const merged = [
                          ...new Set([
                            ...existing,
                            ...recKws.filter(
                              (k) => !existing.includes(k),
                            ),
                          ]),
                        ];
                        setKeywords(merged.join(", "));
                      }}
                      title={`匹配度: ${r.score} — 点击添加关键词`}
                    >
                      ★ {r.label}
                    </button>
                    {i < recs.length - 1 && " "}
                  </span>
                ))}
              </div>
            )}
          </label>
          <div className="span-2 topic-source-field">
            <span className="topic-source-label">关联信息源</span>
            <SourceSelector
              sources={activeSources}
              selected={selectedSourceIds}
              onChange={setSelectedSourceIds}
            />
          </div>
          <label>
            Cron 表达式
            <input
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="例如：0 8 * * * (每天8点)"
            />
            <span className="text-muted small">
              留空则不使用定时；配置后需保存才能生效
            </span>
          </label>
          <label>
            采集窗口 (天)
            <input
              type="number"
              value={collectWindowDays}
              onChange={(e) =>
                setCollectWindowDays(
                  Math.max(1, parseInt(e.target.value) || 7),
                )
              }
              min={1}
            />
          </label>
          <label className="span-2">
            描述{" "}
            <textarea
              rows={2}
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="简短描述这个采集主题的用途"
            />
          </label>
          <label className="span-2">
            关键词权重 (一行一个: keyword:权重0-10){" "}
            <textarea
              rows={3}
              value={keywordTags}
              onChange={(e) => setKeywordTags(e.target.value)}
              placeholder={
                "tariffs:10\nUS-China trade:8\nexport control:7"
              }
            />
          </label>
          <label>
            自动报告{" "}
            <select
              value={autoReport ? "1" : "0"}
              onChange={(e) => {
                const v = e.target.value === "1";
                setAutoReport(v);
                if (v && !autoReportModelId) {
                  const def = models.find((m) => m.is_default);
                  if (def) setAutoReportModelId(def.id);
                }
              }}
            >
              <option value="0">关闭</option>
              <option value="1">启用</option>
            </select>
          </label>
          {autoReport && (
            <label>
              报告模型{" "}
              <select
                value={autoReportModelId}
                onChange={(e) => setAutoReportModelId(e.target.value)}
              >
                <option value="">-- 默认 --</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.is_default ? " (默认)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="span-2">
            AI 描述提示词{" "}
            <select
              style={{ marginBottom: 4 }}
              value=""
              onChange={(e) => {
                const tpl = DESCRIPTION_PROMPT_TEMPLATES.find(
                  (t) => t.label === e.target.value,
                );
                if (tpl) setDescriptionPrompt(tpl.value);
              }}
            >
              <option value="">-- 选择模板 --</option>
              {DESCRIPTION_PROMPT_TEMPLATES.map((t) => (
                <option key={t.label} value={t.label}>
                  {recLabels.has(t.label) ? "★ " + t.label : t.label}
                </option>
              ))}
            </select>
            <textarea
              rows={3}
              value={descriptionPrompt}
              onChange={(e) => setDescriptionPrompt(e.target.value)}
              placeholder="例如：监控全球主要经济体的贸易政策变化、关税调整、贸易协定进展，重点关注影响中国出口的措施"
            />
            <span className="text-muted small">
              用自然语言描述这个主题的关注重点和需求，AI
              报告生成时会参考此描述
            </span>
          </label>
          <label className="span-2">
            目标URL (每行一个){" "}
            <textarea
              rows={2}
              value={targetUrls}
              onChange={(e) => setTargetUrls(e.target.value)}
              placeholder={"https://example.com/page\nhttps://example.com/other"}
            />
          </label>
          <label className="span-2">
            自动标签 (keyword:tag, 逗号分隔){" "}
            <input
              value={autoTags}
              onChange={(e) => setAutoTags(e.target.value)}
              placeholder="关税:event:tariff, 电池:product:battery"
            />
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || !name}
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
