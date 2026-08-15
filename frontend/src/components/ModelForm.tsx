import { useState } from "react";
import { listAvailableModelsFromConfig } from "../api";
import type { ListModelsResult, ModelConfig } from "../types";

type ModelFormProps = {
  model: ModelConfig | null;
  onSave: (data: Partial<ModelConfig>) => Promise<void>;
  onClose: () => void;
};

const PROVIDERS: { value: string; label: string; desc: string; group: string }[] = [
  // Local
  { value: "ollama", label: "Ollama（本地）", desc: "http://localhost:11434", group: "本地模型" },
  { value: "cc_switch", label: "CC Switch / OpenClaw", desc: "本机统一模型通道代理", group: "本地模型" },
  { value: "lmstudio", label: "LM Studio（本地）", desc: "http://localhost:1234", group: "本地模型" },
  // Cloud providers
  { value: "ollama_cloud", label: "Ollama Cloud", desc: "https://ollama.com", group: "云端模型 API" },
  // Chinese providers
  { value: "openai", label: "DeepSeek (深度求索)", desc: "api.deepseek.com", group: "国内大模型 API" },
  { value: "openai", label: "通义千问 (Qwen/阿里云)", desc: "dashscope.aliyuncs.com", group: "国内大模型 API" },
  { value: "openai", label: "智谱 GLM (智谱AI)", desc: "open.bigmodel.cn", group: "国内大模型 API" },
  { value: "openai", label: "月之暗面 (Moonshot)", desc: "api.moonshot.cn", group: "国内大模型 API" },
  { value: "openai", label: "文心一言 (百度)", desc: "aip.baidubce.com", group: "国内大模型 API" },
  // Standard
  { value: "openai", label: "OpenAI 兼容 API", desc: "标准 OpenAI 格式", group: "标准 API" },
  { value: "custom", label: "自定义 API", desc: "任意兼容格式", group: "标准 API" },
];

export function ModelForm({ model, onSave, onClose }: ModelFormProps) {
  const [saving, setSaving] = useState(false);
  const [id, setId] = useState(model?.id ?? "");
  const [name, setName] = useState(model?.name ?? "");
  const [provider, setProvider] = useState(model?.provider ?? "ollama");
  const [baseUrl, setBaseUrl] = useState(model?.base_url ?? "");
  const [apiKey, setApiKey] = useState(model?.api_key ?? "");
  const [modelName, setModelName] = useState(model?.model_name ?? "");
  const [temperature, setTemperature] = useState(String(model?.temperature ?? 0.7));
  const [maxTokens, setMaxTokens] = useState(String(model?.max_tokens ?? 4096));
  const [topP, setTopP] = useState(String(model?.top_p ?? 0.9));
  const [isActive, setIsActive] = useState(model?.is_active ?? true);
  const [isDefault, setIsDefault] = useState(model?.is_default ?? false);
  const [description, setDescription] = useState(model?.description ?? "");
  const [listing, setListing] = useState(false);
  const [listResult, setListResult] = useState<ListModelsResult | null>(null);

  const handleProviderChange = (p: string) => {
    setProvider(p);
    setListResult(null);
    if (!model) {
      if (p === "ollama") setBaseUrl("http://localhost:11434");
      if (p === "ollama_cloud") setBaseUrl("https://ollama.com");
      if (p === "cc_switch") { setBaseUrl("http://localhost:8080"); setModelName("openclaw-channel"); }
      if (p === "lmstudio") setBaseUrl("http://localhost:1234");
    }
  };

  // group providers
  const groups = [...new Set(PROVIDERS.map((p) => p.group))];
  const providerNeedsApiKey = provider !== "ollama" && provider !== "lmstudio" && provider !== "cc_switch";
  const modelPlaceholder = provider === "ollama" ? "llama3.1" : provider === "ollama_cloud" ? "gpt-oss:20b" : "gpt-4o-mini";
  const baseUrlPlaceholder = provider === "ollama" ? "http://localhost:11434" : provider === "ollama_cloud" ? "https://ollama.com" : "http://localhost:1234/v1";
  const apiKeyPlaceholder = provider === "ollama" ? "可留空" : provider === "ollama_cloud" ? "Ollama Cloud API Key" : "sk-...";
  const canFetchModels = Boolean(baseUrl) && (!providerNeedsApiKey || Boolean(apiKey));
  const isProviderSelected = (p: (typeof PROVIDERS)[number]) => {
    if (provider !== p.value) return false;
    if (p.value !== "openai") return true;
    return Boolean(baseUrl) ? baseUrl.includes(p.desc) : p.label.includes("OpenAI 兼容");
  };

  const handleFetchModels = async () => {
    setListing(true);
    try {
      const result = await listAvailableModelsFromConfig({
        provider,
        base_url: baseUrl || null,
        api_key: apiKey || null,
        model_name: modelName,
      });
      setListResult(result);
      if (result.success && result.models.length > 0 && !modelName) {
        setModelName(result.models[0]);
      }
    } catch (e) {
      setListResult({
        success: false,
        message: e instanceof Error ? e.message : "获取模型失败",
        models: [],
        provider_type: provider,
        current_model: modelName,
      });
    } finally {
      setListing(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(e) => e.stopPropagation()}>
        <h3>{model ? "编辑模型" : "添加 AI 模型"}</h3>

        <div className="form-grid" style={{ gap: 14 }}>
          <label><span className="field-label-row">名称 <span className="required-mark" aria-hidden="true">*</span></span>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="例如：本地 Llama3" autoFocus required />
            {!model && (
              <span className="text-muted small">建议用服务+型号命名，如 "Ollama-Qwen2.5"</span>
            )}
          </label>

          <label>ID (唯一标识，创建后不可改)
            <input value={id} onChange={(e) => setId(e.target.value.toLowerCase().replace(/\s/g, "_"))}
              placeholder="例如：ollama_qwen25" disabled={!!model} />
          </label>

          <label className="span-2">提供商
            {(() => {
              return groups.map((group) => (
                <div key={group} style={{ marginTop: group === groups[0] ? 4 : 8 }}>
                  <div className="text-muted small" style={{ marginBottom: 4 }}>{group}</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {PROVIDERS.filter((p) => p.group === group).map((p) => (
                      <button key={p.label}
                        type="button"
                        className={`provider-option ${isProviderSelected(p) ? "provider-option--active" : ""}`}
                        onClick={() => {
                          handleProviderChange(p.value);
                          // Quick-fill for known providers
                          if (p.label.includes("DeepSeek")) { setBaseUrl("https://api.deepseek.com/v1"); setModelName("deepseek-chat"); }
                          else if (p.label.includes("Ollama Cloud")) { setBaseUrl("https://ollama.com"); setModelName(""); if (!name) setName("Ollama Cloud"); if (!id) setId("ollama_cloud"); }
                          else if (p.label.includes("通义千问")) { setBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1"); setModelName("qwen-plus"); }
                          else if (p.label.includes("GLM")) { setBaseUrl("https://open.bigmodel.cn/api/paas/v4"); setModelName("glm-4-flash"); }
                          else if (p.label.includes("月之暗面")) { setBaseUrl("https://api.moonshot.cn/v1"); setModelName("moonshot-v1-8k"); }
                          else if (p.label.includes("文心一言")) { setBaseUrl("https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"); setModelName("ernie-4.0-8k"); }
                          else if (p.value === "cc_switch") { setBaseUrl("http://localhost:8080"); setModelName("openclaw-channel"); }
                          else if (p.value === "ollama") { setBaseUrl("http://localhost:11434"); setModelName("llama3.1"); }
                          else if (p.value === "lmstudio") { setBaseUrl("http://localhost:1234"); setModelName(""); }
                        }}
                      >
                        <strong>{p.label}</strong>
                        <span className="text-muted small">{p.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ));
            })()}
          </label>

          <label className="span-2">API 地址
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={baseUrlPlaceholder} />
          </label>

          <label>模型名称
            <input value={modelName} onChange={(e) => setModelName(e.target.value)}
              placeholder={modelPlaceholder} />
          </label>
          <label><span className="field-label-row">API Key {providerNeedsApiKey ? <span className="required-mark" aria-hidden="true">*</span> : null}</span>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={apiKeyPlaceholder} required={providerNeedsApiKey} />
          </label>

          <div className="span-2">
            <div className="toolbar-row" style={{ margin: 0, alignItems: "center" }}>
              <button type="button" className="btn btn-sm btn-secondary" onClick={handleFetchModels} disabled={listing || !canFetchModels}>
                {listing ? "获取中..." : "获取模型"}
              </button>
              {listResult && (
                <span className={`small ${listResult.success ? "text-muted" : "text-red"}`}>
                  {listResult.message}
                </span>
              )}
            </div>
            {listResult?.models.length ? (
              <div className="chip-row" style={{ marginTop: 8, marginBottom: 0 }}>
                {listResult.models.map((availableModel) => (
                  <button
                    key={availableModel}
                    type="button"
                    className={`chip ${modelName === availableModel ? "chip--blue" : ""}`}
                    onClick={() => setModelName(availableModel)}
                    title="选择此模型"
                  >
                    {availableModel}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <label>温度 (temperature)
            <div className="slider-with-input">
              <input type="range" min="0" max="2" step="0.05" value={temperature}
                onChange={(e) => setTemperature(e.target.value)} />
              <span className="slider-val">{temperature}</span>
            </div>
          </label>
          <label>Top-P
            <div className="slider-with-input">
              <input type="range" min="0" max="1" step="0.05" value={topP}
                onChange={(e) => setTopP(e.target.value)} />
              <span className="slider-val">{topP}</span>
            </div>
          </label>

          <label>最大令牌 (max_tokens)
            <div className="slider-with-input">
              <input type="range" min="256" max="32768" step="256" value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)} />
              <span className="slider-val">{parseInt(maxTokens).toLocaleString()}</span>
            </div>
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            <span>启用模型</span>
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
            <span>设为默认模型</span>
          </label>

          <label className="span-2">描述
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="例如：本地运行的 Qwen2.5 7B 模型，用于报告生成" />
          </label>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={async () => {
            setSaving(true);
            try {
              await onSave({
                id, name, provider, description: description || null,
                base_url: baseUrl || null,
                ...(apiKey ? { api_key: apiKey } : {}),
                model_name: modelName, is_active: isActive, is_default: isDefault,
                temperature: parseFloat(temperature), max_tokens: parseInt(maxTokens), top_p: parseFloat(topP),
              });
            } catch (e) { alert(e instanceof Error ? e.message : "保存失败"); }
            setSaving(false);
          }} disabled={saving || !id || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
