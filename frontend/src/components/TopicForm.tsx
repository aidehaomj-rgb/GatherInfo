import { useState } from "react";
import type { Topic, ModelConfig, Source } from "../types";
import {
  DESCRIPTION_PROMPT_TEMPLATES,
  KEYWORD_WEIGHT_TEMPLATES,
} from "../templates";
import { formatKeywordInput, parseKeywordInput } from "../utils/keywords";
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
  const [keywords, setKeywords] = useState(formatKeywordInput(topic?.keywords ?? []));
  const [keywordTags, setKeywordTags] = useState(
    ((topic as any)?.keyword_tags ?? [])
      .map((kt: any) => `${kt.keyword}:${kt.weight}`)
      .join("\n"),
  );
  const [descriptionPrompt, setDescriptionPrompt] = useState(
    (topic as any)?.description_prompt ?? "",
  );
  const [aiResearchModelId, setAiResearchModelId] = useState(
    topic?.ai_research_model_id ?? topic?.collection_model_ids?.[0] ?? models.find((model) => model.is_default)?.id ?? "",
  );
  const [collectWindowDays, setCollectWindowDays] = useState<number>(
    (topic as any)?.collect_window_days ?? 7,
  );
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>(
    topic?.source_ids ?? [],
  );
  const [selectedCollectionModelIds, setSelectedCollectionModelIds] = useState<string[]>(
    topic?.collection_model_ids ?? [],
  );
  const [targetUrls, setTargetUrls] = useState(
    (topic?.target_urls ?? []).join("\n"),
  );
  const [cron, setCron] = useState(topic?.schedule_cron ?? "");
  const [autoReport, setAutoReport] = useState(topic?.auto_report ?? false);
  const [autoReportModelId, setAutoReportModelId] = useState(
    topic?.auto_report_model_id ?? models.find((m) => m.is_default)?.id ?? "",
  );
  const [autoReportType, setAutoReportType] = useState<"analytical" | "archive">(
    topic?.auto_report_type ?? "analytical",
  );
  const [weeklyDigestEnabled, setWeeklyDigestEnabled] = useState(
    topic?.weekly_digest_enabled ?? false,
  );
  const [weeklyDigestModelId, setWeeklyDigestModelId] = useState(
    topic?.weekly_digest_model_id ?? models.find((m) => m.is_default)?.id ?? "",
  );
  const [weeklyDigestTargetItems, setWeeklyDigestTargetItems] = useState(
    topic?.weekly_digest_target_items ?? 80,
  );
  const [weeklyDigestPartSize, setWeeklyDigestPartSize] = useState(
    topic?.weekly_digest_part_size ?? 40,
  );
  const [weeklyDigestMinItems, setWeeklyDigestMinItems] = useState(
    topic?.weekly_digest_min_items ?? 60,
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
        keywords: parseKeywordInput(keywords),
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
        ai_research_model_id: aiResearchModelId || null,
        source_ids: selectedSourceIds.length ? selectedSourceIds : null,
        collection_model_ids: selectedCollectionModelIds.length ? selectedCollectionModelIds : null,
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
        auto_report_type: autoReportType,
        weekly_digest_enabled: weeklyDigestEnabled,
        weekly_digest_model_id: weeklyDigestEnabled ? weeklyDigestModelId || null : null,
        weekly_digest_target_items: weeklyDigestTargetItems,
        weekly_digest_part_size: weeklyDigestPartSize,
        weekly_digest_min_items: weeklyDigestMinItems,
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
  const kwList = parseKeywordInput(keywords);
  const recs = recommendTemplates(kwList);
  const recLabels = new Set(recs.map((r) => r.label));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal modal--config"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header-with-actions">
          <h3>{topic ? "编辑主题" : "新建主题"}</h3>
          <span className="text-muted small">
            输入关键词、选择信息源并配置高级选项，创建精准的采集监控主题
          </span>
        </div>

        <div className="form-grid">
          <label>
            <span className="field-label-row">主题名称 <span className="required-mark" aria-hidden="true">*</span></span>
            <input
              required
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
            <span className="field-label-row">关键词 <span className="required-mark" aria-hidden="true">*</span></span>
            <input
              required
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder={'例如：关税；走私、出口管制 或 "trade war", "export control"'}
            />
            <span className="text-muted small">支持中英文逗号、分号、顿号和空格；英文多词短语请使用引号保留。</span>
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
                        const existing = parseKeywordInput(keywords);
                        const recKws = parseKeywordInput(r.value);
                        const merged = [
                          ...new Set([
                            ...existing,
                            ...recKws.filter(
                              (k) => !existing.includes(k),
                            ),
                          ]),
                        ];
                        setKeywords(formatKeywordInput(merged));
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
            models={models}
            selectedModelIds={selectedCollectionModelIds}
            onModelChange={setSelectedCollectionModelIds}
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
          <label>
            每周双卷情报合集
            <select
              value={weeklyDigestEnabled ? "1" : "0"}
              onChange={(event) => setWeeklyDigestEnabled(event.target.value === "1")}
            >
              <option value="0">关闭</option>
              <option value="1">每周一 06:30 自动编排上周合集</option>
            </select>
          </label>
          {weeklyDigestEnabled && (
            <label>
              周刊处理模型
              <select
                value={weeklyDigestModelId}
                onChange={(event) => setWeeklyDigestModelId(event.target.value)}
              >
                <option value="">使用默认模型</option>
                {models.filter((model) => model.is_active).map((model) => (
                  <option key={model.id} value={model.id}>{model.name}</option>
                ))}
              </select>
            </label>
          )}
          {weeklyDigestEnabled && (
            <label>
              每周目标条数
              <input
                type="number"
                min={60}
                max={80}
                value={weeklyDigestTargetItems}
                onChange={(event) => setWeeklyDigestTargetItems(
                  Math.max(60, Math.min(80, Number(event.target.value) || 80)),
                )}
              />
            </label>
          )}
          {weeklyDigestEnabled && (
            <label>
              每卷最多条数
              <input
                type="number"
                min={30}
                max={40}
                value={weeklyDigestPartSize}
                onChange={(event) => setWeeklyDigestPartSize(
                  Math.max(30, Math.min(40, Number(event.target.value) || 40)),
                )}
              />
            </label>
          )}
          {weeklyDigestEnabled && (
            <label>
              自动发布最低条数
              <input
                type="number"
                min={60}
                max={weeklyDigestTargetItems}
                value={weeklyDigestMinItems}
                onChange={(event) => setWeeklyDigestMinItems(
                  Math.max(60, Math.min(weeklyDigestTargetItems, Number(event.target.value) || 60)),
                )}
              />
              <span className="text-muted small">不足 60 条不自动发布，避免低质量凑数。</span>
            </label>
          )}
          {autoReport && (
            <label>
              自动报告类型
              <select
                value={autoReportType}
                onChange={(e) => setAutoReportType(e.target.value as "analytical" | "archive")}
              >
                <option value="analytical">总结推理分析型</option>
                <option value="archive">逐条信息归档型</option>
              </select>
            </label>
          )}
          <label className="span-2">
            AI 采集提示词{" "}
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
              主题关联“AI 提示采集”信息源时，手动与定时采集都会使用这份提示词生成检索式。
            </span>
          </label>
          <label>
            AI 采集模型
            <select value={aiResearchModelId} onChange={(event) => setAiResearchModelId(event.target.value)}>
              <option value="">使用主题采集模型或默认模型</option>
              {models.filter((model) => model.is_active && model.is_configured).map((model) => (
                <option key={model.id} value={model.id}>{model.name} · {model.model_name}</option>
              ))}
            </select>
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
