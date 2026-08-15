import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import {
  ArrowLeft, Check, ChevronRight, Network, Play, Radar,
  Search, Settings2, ShieldCheck, Sparkles,
} from "lucide-react";

import { fetchMCPToolCatalog, fetchModels, fetchSupplyChainCandidates, reviewSupplyChainCandidate } from "../api";
import type { MCPToolCatalogItem, ModelConfig, SupplyChainDiscovery } from "../types";
import {
  getSupplyChainExpertRun,
  startSupplyChainExpertRun,
  subscribeSupplyChainExpertRun,
} from "../supplyChainExpertRunStore";

const directions = [
  { id: "United States", label: "美国" },
  { id: "India", label: "印度" },
  { id: "Japan", label: "日本" },
  { id: "Taiwan", label: "中国台湾" },
];

const supplyChainMcpTools = [
  { id: "resolve_supply_chain_entity", name: "企业身份消歧", description: "核验法定主体及关联企业" },
  { id: "search_supply_chain_contracts", name: "军工合同检索", description: "核验合同号与官方来源" },
  { id: "search_supply_chain_trade_records", name: "贸易记录检索", description: "核验提单号与贸易批次" },
  { id: "deep_search_china_trade_records", name: "中国进口与提单深度检索", description: "按企业、地址、产品和时间深挖中国贸易记录" },
  { id: "search_supply_chain_part_numbers", name: "精确料号检索", description: "匹配P/N、NSN与具体型号" },
  { id: "verify_supply_chain_end_use", name: "最终用途核验", description: "核验平台、交付与最终用户" },
];

const mcpToolLabels: Record<string, string> = {
  list_topics: "主题清单", start_research: "启动深度研究", get_research: "研究进度",
  get_research_items: "研究证据", resume_research: "恢复研究", search_items: "已有情报检索",
  open_item: "条目全文读取", research_entity: "实体深挖", read_document: "网页与文档解析",
  extract_document_entities: "文档实体抽取", run_tool_research: "智能工具研究",
  list_research_cases: "案件图谱清单", open_research_case: "案件图谱读取",
  broad_web_search: "公开网络搜索", multilingual_news_search: "多语种新闻搜索",
  case_image_search: "案件图片搜索", official_pdf_search: "官方PDF搜索",
  ...Object.fromEntries(supplyChainMcpTools.map((tool) => [tool.id, tool.name])),
};

const EXPERT_SETTINGS_KEY = "intelligence-expert:supply-chain-settings";

interface ExpertSettings {
  selectedDirections: string[];
  minimumScore: number;
  maxCandidates: number;
  selectedMcpTools: string[];
  modelId: string;
  researchRounds: number;
  importRecordWindowDays: 90 | 180 | 365;
}

function readExpertSettings(): ExpertSettings {
  const defaults: ExpertSettings = {
    selectedDirections: directions.map((item) => item.id),
    minimumScore: 60,
    maxCandidates: 5,
    selectedMcpTools: supplyChainMcpTools.map((tool) => tool.id),
    modelId: "ollama-cloud-free",
    researchRounds: 3,
    importRecordWindowDays: 365,
  };
  try {
    const saved = window.sessionStorage.getItem(EXPERT_SETTINGS_KEY);
    if (!saved) return defaults;
    const parsed = JSON.parse(saved) as Partial<ExpertSettings>;
    return {
      selectedDirections: Array.isArray(parsed.selectedDirections)
        ? parsed.selectedDirections.filter((id) => directions.some((item) => item.id === id))
        : defaults.selectedDirections,
      minimumScore: typeof parsed.minimumScore === "number" ? parsed.minimumScore : defaults.minimumScore,
      maxCandidates: typeof parsed.maxCandidates === "number" ? parsed.maxCandidates : defaults.maxCandidates,
      selectedMcpTools: Array.isArray(parsed.selectedMcpTools)
        ? Array.from(new Set([
            ...parsed.selectedMcpTools.filter((id): id is string => typeof id === "string"),
            ...(parsed.selectedMcpTools.includes("search_supply_chain_trade_records")
              ? ["deep_search_china_trade_records"] : []),
          ]))
        : defaults.selectedMcpTools,
      modelId: typeof parsed.modelId === "string" ? parsed.modelId : defaults.modelId,
      researchRounds: typeof parsed.researchRounds === "number" ? Math.min(6, Math.max(1, parsed.researchRounds)) : defaults.researchRounds,
      importRecordWindowDays: [90, 180, 365].includes(Number(parsed.importRecordWindowDays))
        ? Number(parsed.importRecordWindowDays) as 90 | 180 | 365
        : defaults.importRecordWindowDays,
    };
  } catch {
    return defaults;
  }
}

interface Props {
  detailOpen: boolean;
  onDetailOpenChange: (open: boolean) => void;
  onOpenSupplyChain: () => void;
}

export function IntelligenceExpertsPage({ detailOpen, onDetailOpenChange, onOpenSupplyChain }: Props) {
  const [initialSettings] = useState(readExpertSettings);
  const [expertQuery, setExpertQuery] = useState("");
  const [selectedDirections, setSelectedDirections] = useState(initialSettings.selectedDirections);
  const [minimumScore, setMinimumScore] = useState(initialSettings.minimumScore);
  const [maxCandidates, setMaxCandidates] = useState(initialSettings.maxCandidates);
  const [selectedMcpTools, setSelectedMcpTools] = useState(initialSettings.selectedMcpTools);
  const [mcpTools, setMcpTools] = useState<MCPToolCatalogItem[]>([]);
  const [mcpQuery, setMcpQuery] = useState("");
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [modelId, setModelId] = useState(initialSettings.modelId);
  const [researchRounds, setResearchRounds] = useState(initialSettings.researchRounds);
  const [importRecordWindowDays, setImportRecordWindowDays] = useState(initialSettings.importRecordWindowDays);
  const [runElapsedSeconds, setRunElapsedSeconds] = useState(0);
  const [candidates, setCandidates] = useState<SupplyChainDiscovery[]>([]);
  const [reviewingId, setReviewingId] = useState("");
  const [localError, setLocalError] = useState("");
  const runSnapshot = useSyncExternalStore(
    subscribeSupplyChainExpertRun,
    getSupplyChainExpertRun,
    getSupplyChainExpertRun,
  );
  const { running, result } = runSnapshot;
  const error = localError || runSnapshot.error;
  const lastRunDuration = runSnapshot.startedAt && runSnapshot.finishedAt
    ? Math.max(1, Math.round((runSnapshot.finishedAt - runSnapshot.startedAt) / 1000))
    : null;

  useEffect(() => {
    window.sessionStorage.setItem(EXPERT_SETTINGS_KEY, JSON.stringify({
      selectedDirections,
      minimumScore,
      maxCandidates,
      selectedMcpTools,
      modelId,
      researchRounds,
      importRecordWindowDays,
    } satisfies ExpertSettings));
  }, [selectedDirections, minimumScore, maxCandidates, selectedMcpTools, modelId, researchRounds, importRecordWindowDays]);

  useEffect(() => {
    fetchMCPToolCatalog().then((catalog) => setMcpTools(catalog.mcp_tools)).catch(() => {
      setMcpTools(supplyChainMcpTools.map((tool) => ({
        ...tool, category: "供应链核验", kind: "mcp", is_active: true,
        requires_api_key: false,
      })));
    });
  }, []);

  useEffect(() => {
    fetchModels().then((rows) => {
      const active = rows.filter((model) => model.is_active && model.is_configured);
      setModels(active);
      setModelId((current) => active.some((model) => model.id === current)
        ? current
        : active.find((model) => model.id === "ollama-cloud-free")?.id
          || active.find((model) => model.is_default)?.id
          || active[0]?.id
          || "");
    }).catch(() => setModels([]));
  }, []);

  const visibleMcpTools = useMemo(() => {
    const needle = mcpQuery.trim().toLowerCase();
    if (!needle) return mcpTools;
    return mcpTools.filter((tool) => `${tool.id} ${tool.name} ${tool.description} ${tool.category}`.toLowerCase().includes(needle));
  }, [mcpQuery, mcpTools]);

  useEffect(() => {
    if (!running) return;
    const startedAt = runSnapshot.startedAt || Date.now();
    const refreshElapsed = () => setRunElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    refreshElapsed();
    const timer = window.setInterval(() => {
      refreshElapsed();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, runSnapshot.startedAt]);

  useEffect(() => {
    if (!detailOpen) return;
    fetchSupplyChainCandidates().then(setCandidates).catch((reason) => {
      setLocalError(reason instanceof Error ? reason.message : "候选链加载失败");
    });
  }, [detailOpen, runSnapshot.finishedAt]);

  const toggleDirection = (id: string) => {
    setSelectedDirections((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : [...current, id]);
  };

  const runExpert = async () => {
    if (!selectedDirections.length) {
      setLocalError("请至少选择一个调查方向");
      return;
    }
    setLocalError("");
    void startSupplyChainExpertRun({
      countries: selectedDirections,
      minimum_score: minimumScore,
      max_candidates: maxCandidates,
      mcp_tools: selectedMcpTools,
      model_id: modelId || undefined,
      research_rounds: researchRounds,
      import_record_window_days: importRecordWindowDays,
    });
  };

  const runStage = runElapsedSeconds < 3
    ? { title: "正在准备联网调查", detail: "生成国家、军工合同和中国进口检索式" }
    : runElapsedSeconds < 20
      ? { title: "正在进行第一轮搜索", detail: "检索公开网页、多语种新闻与官方PDF" }
      : runElapsedSeconds < 45
        ? { title: "正在规划补充调查", detail: "分析证据缺口并生成合同号、企业别名、提单和料号查询" }
        : runElapsedSeconds < 90
          ? { title: "正在深挖并读取原文", detail: "执行第二轮精确检索，读取合同、贸易记录与官方报道" }
          : runElapsedSeconds < 140
            ? { title: "正在交叉核验证据", detail: "核对企业、产品、合同与中国来源进口关系" }
          : { title: "正在整理候选供应链", detail: "仅保留具有两类独立来源的可审核线索" };

  const reviewCandidate = async (id: string, action: "approve" | "reject") => {
    setReviewingId(id);
    setLocalError("");
    try {
      await reviewSupplyChainCandidate(id, action);
      setCandidates((current) => current.filter((item) => item.id !== id));
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "候选链审核失败");
    } finally {
      setReviewingId("");
    }
  };

  return (
    <div className="page expert-page">
      {!detailOpen ? (
        <main className="expert-home">
          <header className="expert-home-heading">
            <div><span className="section-kicker">EXPERT CATALOG</span><h2>专家工作台</h2><p>选择一位专家，配置并运行对应的情报工作流。</p></div>
            <div className="expert-home-tools">
              <label className="expert-search">
                <Search size={16} />
                <input value={expertQuery} onChange={(event) => setExpertQuery(event.target.value)} placeholder="搜索专家职能或调查场景" aria-label="搜索专家" />
              </label>
              <span><Radar size={15} />1 位可用</span>
            </div>
          </header>
          <section className="expert-home-grid" aria-label="可用专家">
            {"供应链穿透专家 供应链风险 企业消歧 规则评分 证据边界".includes(expertQuery.trim()) && <button type="button" className="expert-home-card" onClick={() => onDetailOpenChange(true)}>
              <div className="expert-home-card-top">
                <div className="expert-avatar"><Network size={27} /></div>
                <span className="expert-ready"><i />可执行</span>
              </div>
              <div className="expert-home-card-copy">
                <span className="section-kicker">供应链风险</span>
                <h3>供应链穿透专家</h3>
                <p>交叉军工采购与中国来源贸易事实，识别未闭合候选链，并安全写入供应链穿透调查。</p>
              </div>
              <div className="expert-tags"><span>企业消歧</span><span>规则评分</span><span>证据边界</span></div>
              <footer><span>进入专家配置</span><ChevronRight size={18} /></footer>
            </button>}
            {expertQuery.trim() && !"供应链穿透专家 供应链风险 企业消歧 规则评分 证据边界".includes(expertQuery.trim()) && <div className="expert-home-empty">没有匹配的专家</div>}
          </section>
        </main>
      ) : <>
      <div className="expert-detail-heading">
        <button type="button" onClick={() => onDetailOpenChange(false)}><ArrowLeft size={16} />返回专家列表</button>
        <span>供应链穿透专家</span>
      </div>
      <div className="expert-layout">
        <section className="expert-config">
          <header>
            <div><Settings2 size={20} /><span><strong>专家配置</strong><small>供应链穿透专家 · v1.0</small></span></div>
            <span className="expert-ready"><i />可执行</span>
          </header>

          <div className="expert-config-grid">
          <div className="expert-config-section">
            <label className="expert-field-label">调查方向</label>
            <div className="expert-direction-grid">
              {directions.map((item) => {
                const selected = selectedDirections.includes(item.id);
                return <button key={item.id} type="button" className={selected ? "is-selected" : ""} onClick={() => toggleDirection(item.id)}>
                  <span>{selected && <Check size={14} />}</span>{item.label}
                </button>;
              })}
            </div>
          </div>

          <div className="expert-config-section expert-range-field">
            <label htmlFor="expert-score"><span>最低发现分数</span><strong>{minimumScore}</strong></label>
            <input id="expert-score" type="range" min="35" max="100" step="5" value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} />
            <div><span>更多探索</span><span>更高精度</span></div>
          </div>

          <div className="expert-config-section">
            <div className="expert-mcp-heading">
              <label className="expert-field-label">MCP核验能力</label>
              <button type="button" onClick={() => setSelectedMcpTools(
                selectedMcpTools.length === mcpTools.length
                  ? [] : supplyChainMcpTools.map((tool) => tool.id),
              )}>{selectedMcpTools.length === mcpTools.length ? "全部取消" : "恢复推荐"}</button>
            </div>
            <details className="expert-mcp-select">
              <summary><span>{selectedMcpTools.length ? `已选择 ${selectedMcpTools.length} 项能力` : "请选择 MCP 能力"}</span></summary>
              <div className="expert-mcp-menu">
                <label className="expert-mcp-search"><Search size={14} /><input value={mcpQuery} onChange={(event) => setMcpQuery(event.target.value)} placeholder="搜索 MCP 能力" /></label>
                {(["供应链核验", "通用能力"] as const).map((group) => {
                  const tools = visibleMcpTools.filter((tool) => group === "供应链核验" ? tool.category === "供应链核验" : tool.category !== "供应链核验");
                  if (!tools.length) return null;
                  return <section key={group}><header>{group}<span>{tools.length}</span></header>{tools.map((tool) => {
                    const selected = selectedMcpTools.includes(tool.id);
                    return <button key={tool.id} type="button" className={selected ? "is-selected" : ""} onClick={() => setSelectedMcpTools((current) => selected ? current.filter((id) => id !== tool.id) : [...current, tool.id])}>
                      <span>{selected && <Check size={12} />}</span><strong>{mcpToolLabels[tool.id] || tool.name}</strong>
                    </button>;
                  })}</section>;
                })}
              </div>
            </details>
            <div className="expert-setting-divider" />
            <label className="expert-field-label">调查轮次</label>
            <div className="expert-round-presets" role="group" aria-label="联网调查轮次">
              {[1, 2, 3, 4, 5, 6].map((value) => <button key={value} type="button" className={researchRounds === value ? "is-selected" : ""} onClick={() => setResearchRounds(value)}>{value}</button>)}
            </div>
          </div>

          <div className="expert-config-section expert-execution-settings">
            <label className="expert-field-label" htmlFor="expert-model">研究模型</label>
            <select id="expert-model" value={modelId} onChange={(event) => setModelId(event.target.value)}>
              {models.map((model) => <option key={model.id} value={model.id}>
                {model.name} · {model.model_name}{model.id === "ollama-cloud-free" ? "（默认）" : ""}
              </option>)}
            </select>
            <div className="expert-setting-divider" />
            <label className="expert-field-label">进口记录时间</label>
            <div className="expert-time-presets" role="group" aria-label="中国进口记录时间范围">
              {([
                [365, "近一年"], [180, "近半年"], [90, "近一季度"],
              ] as const).map(([value, label]) => <button
                key={value}
                type="button"
                className={importRecordWindowDays === value ? "is-selected" : ""}
                onClick={() => setImportRecordWindowDays(value)}
              >{label}</button>)}
            </div>
            <div className="expert-setting-divider" />
            <label className="expert-field-label" htmlFor="expert-limit">单次最多新增</label>
            <div className="expert-limit-control">
              <div className="expert-limit-presets" role="group" aria-label="单次最多新增快捷选项">
                {[3, 5, 10].map((value) => <button
                  key={value}
                  type="button"
                  className={maxCandidates === value ? "is-selected" : ""}
                  onClick={() => setMaxCandidates(value)}
                >{value}</button>)}
              </div>
              <label className="expert-limit-input">
                <span>自定义</span>
                <input
                  id="expert-limit"
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={maxCandidates}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (Number.isFinite(value)) setMaxCandidates(Math.min(100, Math.max(1, Math.trunc(value))));
                  }}
                  aria-label="自定义单次最多新增数量"
                />
                <small>条</small>
              </label>
            </div>
          </div>
          </div>

          <button type="button" className="btn btn-primary expert-run" onClick={() => void runExpert()} disabled={running}>
            {running ? <Sparkles size={17} /> : <Play size={17} />}{running ? "正在穿透分析" : "运行供应链穿透专家"}
          </button>
          {running && <section className="expert-run-progress" aria-live="polite">
            <header>
              <span className="expert-run-spinner"><Radar size={17} /></span>
              <div><strong>{runStage.title}</strong><small>{runStage.detail}</small></div>
              <time>{formatDuration(runElapsedSeconds)}</time>
            </header>
            <div className="expert-run-progress-bar"><span /></div>
            <p>任务完成后会自动显示发现结果；当前为阶段提示，不代表精确完成百分比。</p>
          </section>}
          {!running && lastRunDuration !== null && result && <div className="expert-run-complete" role="status">
            <Check size={16} />本次运行已结束，用时 {formatDuration(lastRunDuration)}，新增 {result.candidates_created} 条待审核候选链。
          </div>}
          {error && <p className="inline-error">{error}</p>}

          {result && <section className="expert-result" aria-live="polite">
            <header>
              <div><span className="section-kicker">本次运行</span><h3>发现结果</h3></div>
              <button type="button" onClick={onOpenSupplyChain}>进入供应链穿透 <ChevronRight size={15} /></button>
            </header>
            <div className="expert-result-metrics">
              <span><strong>{result.cases_scanned}</strong><small>联网来源</small></span>
              <span><strong>{result.shipments_scanned}</strong><small>读取原文</small></span>
              <span><strong>{result.candidates_matched}</strong><small>候选线索</small></span>
              <span><strong>{result.candidates_created}</strong><small>新增候选链</small></span>
            </div>
            {result.discoveries.length === 0 && <p className="expert-empty">本次没有生成新的候选链，已有命中可能正在等待审核。</p>}
          </section>}

          <section className="expert-result expert-review-queue" aria-live="polite">
            <header>
              <div><span className="section-kicker">REVIEW QUEUE</span><h3>待审核候选链</h3></div>
              <span>{candidates.length} 条</span>
            </header>
            {candidates.length === 0
              ? <p className="expert-empty">暂无待审核候选链。运行专家后，新发现会先出现在这里。</p>
              : <div className="expert-discoveries">{candidates.map((item) => {
                const contractUrl = typeof item.verified_facts?.contract_evidence_url === "string" ? item.verified_facts.contract_evidence_url : "";
                const tradeUrl = typeof item.verified_facts?.trade_evidence_url === "string" ? item.verified_facts.trade_evidence_url : "";
                const evidenceStatus = item.verified_facts?.evidence_status;
                const configuredGap = typeof item.verified_facts?.evidence_gap === "string" ? item.verified_facts.evidence_gap : "";
                const tradeDate = typeof item.verified_facts?.trade_date === "string" ? item.verified_facts.trade_date : "";
                const evidenceGap = configuredGap || (evidenceStatus === "contract_only"
                  ? "待补所选时间内的中国进口/提单证据"
                  : evidenceStatus === "trade_only"
                    ? "待补军工合同/用途证据"
                    : "");
                const directionLabel = directions.find((direction) => direction.id === item.country)?.label ?? item.country;
                return <article key={item.id} className="expert-candidate">
                <div className="expert-candidate-copy">
                  <strong><b className="expert-direction-badge">{directionLabel}方向</b>{item.importer_name}中国供应线索</strong>
                  <small>{item.exporter_name} → {item.importer_name} · {item.product}</small>
                  <p>{item.title}{item.target_program ? ` · ${item.target_program}` : ""}</p>
                  {(contractUrl || tradeUrl) && <div className="expert-candidate-sources">
                    {contractUrl && <a href={contractUrl} target="_blank" rel="noreferrer">合同/官方证据</a>}
                    {tradeUrl && <a href={tradeUrl} target="_blank" rel="noreferrer">中国进口证据{tradeDate ? ` · ${tradeDate}` : ""}</a>}
                    {evidenceGap && <em>{evidenceGap}</em>}
                  </div>}
                </div>
                <span>{item.score} 分 · {item.evidence_grade}级线索</span>
                <div className="expert-candidate-actions">
                  <button type="button" className="btn btn-secondary" disabled={reviewingId === item.id} onClick={() => void reviewCandidate(item.id, "reject")}>驳回</button>
                  <button type="button" className="btn btn-primary" disabled={reviewingId === item.id} onClick={() => void reviewCandidate(item.id, "approve")}>审核通过</button>
                </div>
              </article>})}</div>}
            <p className="expert-review-note"><ShieldCheck size={14} />只有审核通过的候选链才会进入供应链穿透模块。</p>
          </section>
        </section>
      </div>
      </>}
    </div>
  );
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}分${String(seconds).padStart(2, "0")}秒` : `${seconds}秒`;
}
