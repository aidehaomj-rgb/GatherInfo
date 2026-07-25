import { useState } from "react";
import type { ModelConfig } from "../types";

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

  const handleProviderChange = (p: string) => {
    setProvider(p);
    if (!model) {
      if (p === "ollama") setBaseUrl("http://localhost:11434");
      if (p === "cc_switch") { setBaseUrl("http://localhost:8080"); setModelName("openclaw-channel"); }
      if (p === "lmstudio") setBaseUrl("http://localhost:1234");
    }
  };

  // group providers
  const groups = [...new Set(PROVIDERS.map((p) => p.group))];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 640 }}>
        <h3>{model ? "编辑模型" : "添加 AI 模型"}</h3>

        <div className="form-grid" style={{ gap: 14 }}>
          <label>名称 <span className="text-red">*</span>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="例如：本地 Llama3" autoFocus />
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
                        className={`provider-option ${provider === p.value && (p.label.includes(baseUrl) || !baseUrl) ? "provider-option--active" : ""}`}
                        onClick={() => {
                          handleProviderChange(p.value);
                          // Quick-fill for known providers
                          if (p.label.includes("DeepSeek")) { setBaseUrl("https://api.deepseek.com/v1"); setModelName("deepseek-chat"); }
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
              placeholder={provider === "ollama" ? "http://localhost:11434" : "http://localhost:1234/v1"} />
          </label>

          <label>模型名称
            <input value={modelName} onChange={(e) => setModelName(e.target.value)}
              placeholder={provider === "ollama" ? "llama3.1" : "gpt-4o-mini"} />
          </label>
          <label>API Key {provider !== "ollama" ? <span className="text-red">*</span> : null}
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === "ollama" ? "可留空" : "sk-..."} />
          </label>

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
                base_url: baseUrl || null, api_key: apiKey || null,
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
