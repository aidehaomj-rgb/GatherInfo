import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, Anchor, BatteryCharging, Building2, ChevronDown, Crosshair, ExternalLink, Factory,
  FileSearch, FlaskConical, Landmark, Link2, Network, PackageSearch, Plus,
  Pause, Play, RadioTower, Route, Search, ShieldCheck, ShipWheel, Sparkles, Warehouse, X,
} from "lucide-react";

import {
  analyzeSupplyChain, createSupplyChainCase, createSupplyChainEntity,
  createSupplyChainInvestigation,
  createSupplyChainShipment, fetchModels, fetchSupplyChainCases,
  fetchSupplyChainDashboard, fetchSupplyChainEntities, fetchSupplyChainEvidence,
  fetchSupplyChainInvestigations,
  fetchSupplyChainOpenSourceEvidence, fetchSupplyChainReports,
  fetchSupplyChainShipments, generateSupplyChainReport,
} from "../api";
import type {
  ModelConfig, SupplyChainCase, SupplyChainDashboard, SupplyChainEntity,
  SupplyChainEvidence, SupplyChainOpenSourceEvidence, SupplyChainReport,
  SupplyChainInvestigation, SupplyChainShipment,
} from "../types";
import { RenderMarkdown } from "./shared/RenderMarkdown";

type Tab = "overview" | "map" | "procurement" | "trade" | "evidence" | "reports";
type Direction = "United States" | "India" | "Japan" | "Taiwan";

const directions: { id: Direction; label: string; short: string }[] = [
  { id: "United States", label: "美国方向", short: "美国" },
  { id: "India", label: "印度方向", short: "印度" },
  { id: "Japan", label: "日本方向", short: "日本" },
  { id: "Taiwan", label: "中国台湾方向", short: "中国台湾" },
];

const emptyDashboard: SupplyChainDashboard = {
  country: "United States", entities: 0, cases: 0, shipments: 0,
  evidence: 0, open_source_evidence: 0, reportable: 0, reports: 0,
};

export function SupplyChainPage() {
  const [direction, setDirection] = useState<Direction>("United States");
  const [investigationId, setInvestigationId] = useState("");
  const [investigations, setInvestigations] = useState<SupplyChainInvestigation[]>([]);
  const [showInvestigationForm, setShowInvestigationForm] = useState(false);
  const [showInvestigationPicker, setShowInvestigationPicker] = useState(false);
  const [investigationQuery, setInvestigationQuery] = useState("");
  const [investigationsLoading, setInvestigationsLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [entities, setEntities] = useState<SupplyChainEntity[]>([]);
  const [cases, setCases] = useState<SupplyChainCase[]>([]);
  const [shipments, setShipments] = useState<SupplyChainShipment[]>([]);
  const [evidence, setEvidence] = useState<SupplyChainEvidence[]>([]);
  const [openSourceEvidence, setOpenSourceEvidence] =
    useState<SupplyChainOpenSourceEvidence[]>([]);
  const [reports, setReports] = useState<SupplyChainReport[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [modelId, setModelId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState<"entity" | "case" | "shipment" | null>(null);
  const [motionEnabled, setMotionEnabled] = useState(true);
  const loadToken = useRef(0);
  const investigationLoadToken = useRef(0);

  const load = useCallback(async () => {
    const token = ++loadToken.current;
    const [dash, entityRows, caseRows, shipmentRows, evidenceRows, openSourceRows, reportRows, modelRows] =
      await Promise.all([
        fetchSupplyChainDashboard(direction, investigationId || undefined),
        fetchSupplyChainEntities(direction, investigationId || undefined),
        fetchSupplyChainCases(direction, investigationId || undefined),
        fetchSupplyChainShipments(direction, investigationId || undefined),
        fetchSupplyChainEvidence(direction, investigationId || undefined),
        fetchSupplyChainOpenSourceEvidence(direction, investigationId || undefined),
        fetchSupplyChainReports(direction, investigationId || undefined), fetchModels(),
      ]);
    if (token !== loadToken.current) return;
    setDashboard(dash);
    setEntities(entityRows);
    setCases(caseRows);
    setShipments(shipmentRows);
    setEvidence(evidenceRows);
    setOpenSourceEvidence(openSourceRows);
    setReports(reportRows);
    const activeModels = modelRows.filter((model) => model.is_active);
    setModels(activeModels);
    setModelId((current) => current || activeModels.find((model) => model.is_default)?.id || "");
  }, [direction, investigationId]);

  useEffect(() => {
    const token = ++investigationLoadToken.current;
    setInvestigations([]);
    setInvestigationId("");
    setInvestigationsLoading(true);
    fetchSupplyChainInvestigations(direction)
      .then((rows) => {
        if (token !== investigationLoadToken.current) return;
        setInvestigations(rows);
        setInvestigationId(rows[0]?.id || "");
        setInvestigationsLoading(false);
      })
      .catch((error) => {
        if (token !== investigationLoadToken.current) return;
        setInvestigationsLoading(false);
        setMessage(error instanceof Error ? error.message : "供应链项目加载失败");
      });
  }, [direction]);

  useEffect(() => {
    if (!investigationId) {
      loadToken.current += 1;
      setDashboard({ ...emptyDashboard, country: direction });
      setEntities([]);
      setCases([]);
      setShipments([]);
      setEvidence([]);
      setOpenSourceEvidence([]);
      setReports([]);
      return;
    }
    load().catch((error) => setMessage(error instanceof Error ? error.message : "加载失败"));
  }, [direction, investigationId, load]);

  const entityById = useMemo(() => new Map(entities.map((item) => [item.id, item])), [entities]);
  const entityByName = useMemo(() => {
    const rows = new Map<string, SupplyChainEntity>();
    entities.forEach((item) => {
      [item.name, item.name_zh, ...(item.aliases || [])].filter(Boolean).forEach((name) => {
        rows.set(String(name).trim().toLocaleLowerCase(), item);
      });
    });
    return rows;
  }, [entities]);
  const caseById = useMemo(() => new Map(cases.map((item) => [item.id, item])), [cases]);
  const shipmentById = useMemo(() => new Map(shipments.map((item) => [item.id, item])), [shipments]);
  const selectedInvestigation = useMemo(
    () => investigations.find((item) => item.id === investigationId) || null,
    [investigations, investigationId],
  );
  const filteredInvestigations = useMemo(() => {
    const query = investigationQuery.trim().toLocaleLowerCase();
    if (!query) return investigations;
    return investigations.filter((item) =>
      `${item.name} ${item.description || ""}`.toLocaleLowerCase().includes(query),
    );
  }, [investigationQuery, investigations]);
  const procurementFindings = useMemo(() => cases.map((item) => {
    const supplier = entityById.get(item.supplier_entity_id || "");
    const subject = supplier ? entityDisplayName(supplier) : (item.procurement_agency || "相关供应主体");
    const project = item.target_program || item.procurement_agency || "军方采购项目";
    const product = item.product ? `，供应或涉及${item.product}` : "";
    const reference = item.procurement_reference ? `（${item.procurement_reference}）` : "";
    return `${subject}参与${project}${reference}${product}`;
  }), [cases, entityById]);
  const tradeFindings = useMemo(() => shipments.map((item) => {
    const amount = item.weight_kg ? `${item.weight_kg.toLocaleString("zh-CN")}千克` : "";
    const product = `${amount}${item.product}`;
    const exporter = entityByName.get(item.exporter_name.trim().toLocaleLowerCase());
    const importer = entityById.get(item.importer_entity_id || "")
      || entityByName.get(item.importer_name.trim().toLocaleLowerCase());
    return `${exporter ? entityDisplayName(exporter) : item.exporter_name}向${importer ? entityDisplayName(importer) : item.importer_name}供应${product}`;
  }), [shipments, entityById, entityByName]);
  const reportDirectionLabel = {
    "United States": "涉美",
    India: "涉印",
    Japan: "涉日",
    Taiwan: "涉台",
  }[direction];

  const analyze = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await analyzeSupplyChain({
        model_id: modelId || undefined, country: direction,
        investigation_id: investigationId || undefined,
      });
      setMessage(`分析完成：扫描${result.cases_scanned}个项目和${result.shipments_scanned}条贸易记录，新增${result.evidence_created}条证据链。`);
      await load();
      setTab("evidence");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "证据链分析失败");
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const report = await generateSupplyChainReport({
        model_id: modelId || undefined, country: direction,
        investigation_id: investigationId || undefined,
      });
      setMessage(report.status === "completed" ? "供应链报告已生成。" : `报告生成失败：${report.error_log || "未知错误"}`);
      await load();
      setTab("reports");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "报告生成失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`page supply-chain-page${motionEnabled ? "" : " supply-chain-page--motion-paused"}`}>
      <div className="page-header supply-chain-header">
        <div className="supply-chain-heading-copy">
          <span className="supply-chain-eyebrow">DEFENSE SUPPLY CHAIN INTELLIGENCE</span>
          <h2>军工供应链穿透分析</h2>
          <p className="text-muted">串联{directions.find((item) => item.id === direction)?.short}方向关键企业、政府采购、军工项目与跨境贸易记录，形成可核验的证据链和专题报告。</p>
          <div className="supply-chain-direction" role="group" aria-label="分析方向">
            {directions.map((item) => (
              <button
                key={item.id}
                type="button"
                className={direction === item.id ? "active" : ""}
                onClick={() => {
                  setDirection(item.id);
                  setInvestigationId("");
                  setForm(null);
                  setShowInvestigationPicker(false);
                  setInvestigationQuery("");
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="supply-chain-actions">
          <select value={modelId} onChange={(event) => setModelId(event.target.value)} aria-label="分析模型">
            <option value="">默认模型</option>
            {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
          </select>
          <button type="button" className="btn btn-secondary" onClick={() => void analyze()} disabled={busy}>
            <Link2 size={16} />{busy ? "正在处理" : "构建证据链"}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void generate()} disabled={busy}>
            <Sparkles size={16} />{busy ? "智能分析中" : "生成报告"}
          </button>
        </div>
      </div>
      {message && <div className="supply-chain-message">{message}</div>}

      <div className="supply-chain-project-bar">
        <span className="supply-chain-project-label">当前供应链</span>
        <div className="supply-chain-project-selector">
          <button
            type="button"
            className="supply-chain-project-trigger"
            onClick={() => setShowInvestigationPicker((value) => !value)}
            aria-expanded={showInvestigationPicker}
            aria-haspopup="listbox"
          >
            <span>
              <strong>{selectedInvestigation?.name || "请选择供应链"}</strong>
              <small>{investigationsLoading ? "正在加载..." : `${investigations.length} 条供应链`}</small>
            </span>
            <ChevronDown size={17} />
          </button>
          {showInvestigationPicker && (
            <div className="supply-chain-project-picker">
              <header>
                <div>
                  <strong>{directions.find((item) => item.id === direction)?.label}供应链</strong>
                  <small>{investigationsLoading ? "正在加载供应链..." : `共 ${investigations.length} 条，点击即可切换`}</small>
                </div>
                <button type="button" onClick={() => setShowInvestigationPicker(false)} aria-label="关闭供应链选择">
                  <X size={17} />
                </button>
              </header>
              <label className="supply-chain-project-search">
                <Search size={16} />
                <input
                  value={investigationQuery}
                  onChange={(event) => setInvestigationQuery(event.target.value)}
                  placeholder="搜索供应链名称或关键内容"
                  autoFocus
                />
              </label>
              <div className="supply-chain-project-grid" role="listbox" aria-label="全部供应链">
                {filteredInvestigations.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="option"
                    aria-selected={investigationId === item.id}
                    className={investigationId === item.id ? "active" : ""}
                    onClick={() => {
                      setInvestigationId(item.id);
                      setShowInvestigationPicker(false);
                      setInvestigationQuery("");
                    }}
                  >
                    <strong>{item.name}</strong>
                  </button>
                ))}
                {!investigationsLoading && !filteredInvestigations.length && <p>未找到匹配的供应链。</p>}
              </div>
            </div>
          )}
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => setShowInvestigationForm((value) => !value)}>
          <Plus size={15} />新增供应链
        </button>
      </div>
      {showInvestigationForm && (
        <InvestigationForm
          country={direction}
          done={(item) => {
            setInvestigations((rows) => [...rows, item]);
            setInvestigationId(item.id);
            setShowInvestigationForm(false);
          }}
        />
      )}

      <ChainStatusStrip
        investigation={selectedInvestigation}
        dashboard={dashboard}
        entityCount={entities.length}
        relationCount={shipments.length + cases.length + evidence.length}
      />

      <nav className="supply-chain-tabs" aria-label="供应链分析视图">
        {([
          ["overview", "供应链总览", Building2], ["map", "供应链条展示", Network],
          ["procurement", "军用采购项目", FileSearch],
          ["trade", "跨境贸易记录", PackageSearch], ["evidence", "供应链证据链", Link2],
          ["reports", "专题报告", Sparkles],
        ] as [Tab, string, typeof Building2][]).map(([id, label, Icon]) => (
          <button key={id} type="button" className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            <Icon size={15} />{label}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <>
          <div className="supply-chain-kpis">
            <Metric icon={Building2} label="企业主体" value={dashboard.entities} />
            <Metric icon={FileSearch} label="军用采购项目" value={dashboard.cases} />
            <Metric icon={PackageSearch} label="跨境贸易记录" value={dashboard.shipments} />
            <Metric icon={Network} label="证据链" value={dashboard.evidence} />
            <Metric icon={Link2} label="可用于报告" value={dashboard.reportable} />
          </div>
          <section className="supply-chain-findings">
            <header>
              <div>
                <span>REPORT INSIGHTS</span>
                <h3>报告关键发现</h3>
              </div>
              <small>{selectedInvestigation?.name || `${directions.find((item) => item.id === direction)?.short}方向`}</small>
            </header>
            {selectedInvestigation ? (
              <div className="supply-chain-finding-detail">
                <p className="supply-chain-finding-lead">
                  <strong>链条概览</strong>
                  {selectedInvestigation.description || "该供应链项目的主体、采购、贸易和证据关系已纳入持续穿透分析。"}
                </p>
                <div className="supply-chain-completeness">
                  <div>
                    <strong>供应链证据完整度</strong>
                    <span>{selectedInvestigation.completeness_level} · {selectedInvestigation.completeness_score}%</span>
                  </div>
                  <div className="supply-chain-completeness-track" aria-label={`供应链证据完整度 ${selectedInvestigation.completeness_score}%`}>
                    <span style={{ width: `${selectedInvestigation.completeness_score}%` }} />
                  </div>
                  <div className="supply-chain-completeness-parts">
                    {Object.entries(selectedInvestigation.completeness_details || {}).map(([label, value]) => (
                      <span
                        key={label}
                        className={value === selectedInvestigation.completeness_maximums?.[label] ? "complete" : value ? "partial" : ""}
                      >
                        {label} {value}/{selectedInvestigation.completeness_maximums?.[label] || 0}
                      </span>
                    ))}
                  </div>
                  {!!selectedInvestigation.verification_gaps?.length && (
                    <div className="supply-chain-verification-gaps">
                      <strong>尚待核实</strong>
                      <ul>
                        {selectedInvestigation.verification_gaps.map((gap) => <li key={gap}>{gap}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="supply-chain-finding-grid">
                  <article>
                    <strong>军工项目与供应关系</strong>
                    {procurementFindings.length ? (
                      <ul>{procurementFindings.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                    ) : <p>尚未录入军方采购或合作项目。</p>}
                  </article>
                  <article>
                    <strong>跨境贸易产品与流向</strong>
                    {tradeFindings.length ? (
                      <ul>{tradeFindings.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                    ) : <p>尚未录入可核验的跨境贸易记录。</p>}
                  </article>
                  <article>
                    <strong>综合风险判断</strong>
                    <p>{reports[0]?.summary || "尚未形成可展示的报告摘要，需继续补充采购、贸易和最终用途证据。"}</p>
                  </article>
                </div>
              </div>
            ) : reports.length ? (
              <div className="supply-chain-finding-list">
                {reports.map((report) => (
                  <article key={report.id}>
                    <strong>{report.title}</strong>
                    <p>{report.summary || "报告已生成，暂无摘要。"}</p>
                  </article>
                ))}
              </div>
            ) : (
              <Empty text="当前方向暂无分析报告，选择或新增供应链后可形成关键发现。" />
            )}
          </section>
        </>
      )}

      {tab === "map" && (
        selectedInvestigation && (entities.length || cases.length || shipments.length)
            ? <GenericSupplyChainMap
                investigation={selectedInvestigation}
                entities={entities}
                cases={cases}
                shipments={shipments}
                motionEnabled={motionEnabled}
                onMotionChange={setMotionEnabled}
              />
            : <Section title="供应链条展示" actions={null}>
                <Empty text="当前供应链尚未构建可视化图谱。" />
              </Section>
      )}

      {tab === "procurement" && (
        <Section title="军用采购项目" actions={<><Action text="新增企业" onClick={() => setForm("entity")} /><Action text="新增采购项目" primary onClick={() => setForm("case")} /></>}>
          {form === "entity" && <EntityForm entities={entities} country={direction} investigationId={investigationId} done={() => { setForm(null); void load(); }} />}
          {form === "case" && <CaseForm entities={entities} country={direction} investigationId={investigationId} done={() => { setForm(null); void load(); }} />}
          <div className="supply-chain-list">
            {cases.map((item) => <article key={item.id} className="supply-chain-row">
              <div><strong>{item.title}</strong><p>{item.procurement_agency || "采购机关待补充"} · {item.procurement_reference || "公告编号待补充"}</p></div>
              <div>
                <span>{item.product || "产品待补充"}</span>
                <small>{entityById.get(item.supplier_entity_id || "")?.name || "供应商待关联"}</small>
                {item.source_url && (
                  <a className="supply-chain-contract-link" href={item.source_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} />查看合同
                  </a>
                )}
              </div>
            </article>)}
            {!cases.length && <Empty text="暂无采购项目，请先录入美国军用采购公告。" />}
          </div>
        </Section>
      )}

      {tab === "trade" && (
        <Section title="跨境贸易记录" actions={<Action text="新增贸易记录" primary onClick={() => setForm("shipment")} />}>
          {form === "shipment" && <ShipmentForm entities={entities} country={direction} investigationId={investigationId} done={() => { setForm(null); void load(); }} />}
          <div className="supply-chain-list">
            {shipments.map((item) => <article key={item.id} className="supply-chain-row">
              <div><strong>{tradePartyName(item.exporter_name, entityByName)} → {tradePartyName(item.importer_name, entityByName, entityById.get(item.importer_entity_id || ""))}</strong><p>{item.product}</p></div>
              <div><span>{item.weight_kg ? `${item.weight_kg.toLocaleString()} kg` : "重量待补充"}</span><small>{dateText(item.shipment_date)}</small></div>
            </article>)}
            {!shipments.length && <Empty text="暂无贸易记录，可从授权提单数据库导入后录入。" />}
          </div>
        </Section>
      )}

      {tab === "evidence" && (
        <Section title="供应链证据链" actions={<button type="button" className="btn btn-primary" onClick={() => void analyze()} disabled={busy}><Link2 size={15} />重新分析</button>}>
          <div className="supply-chain-list">
            {evidence.map((item) => {
              const caseItem = caseById.get(item.case_id);
              const shipment = shipmentById.get(item.shipment_id);
              return <article key={item.id} className="supply-chain-evidence-row">
                <span className={`evidence-grade evidence-grade--${item.evidence_grade.toLowerCase()}`}>{item.evidence_grade}</span>
                <div><strong>{caseItem?.title || item.case_id}</strong><p>{shipment?.exporter_name} → {shipment?.importer_name} · {shipment?.product}</p><small>{item.reasoning}</small></div>
                <div className="evidence-state"><span>{item.score}分</span><small>{item.is_reportable ? "可用于报告" : "待进一步核验"}</small></div>
              </article>;
            })}
            {!evidence.length && <Empty text="录入采购项目和贸易记录后，点击“构建证据链”。" />}
          </div>
          <div className="supply-chain-evidence-sources">
            <h4>开源核验依据</h4>
            {openSourceEvidence.map((item) => (
              <article key={item.id} className="supply-chain-source-evidence">
                <span className={`evidence-grade evidence-grade--${item.evidence_grade.toLowerCase()}`}>{item.evidence_grade}</span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.source_publisher || "来源机构待补充"} · {item.source_type}</p>
                  {item.source_excerpt && <small>{item.source_excerpt}</small>}
                </div>
                <a className="supply-chain-contract-link" href={item.source_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} />查看原文
                </a>
              </article>
            ))}
            {!openSourceEvidence.length && <Empty text="暂无独立开源核验依据。" />}
          </div>
        </Section>
      )}

      {tab === "reports" && (
        <Section title={`${reportDirectionLabel}供应链专题报告`} actions={<button type="button" className="btn btn-primary" onClick={() => void generate()} disabled={busy}><Sparkles size={15} />生成报告</button>}>
          <div className="supply-chain-reports">
            {reports.map((report) => <details key={report.id}>
              <summary><strong>{report.title}</strong><span>{report.status} · {dateText(report.generated_at)}</span></summary>
              {report.summary && <p className="report-summary">{report.summary}</p>}
              {report.content && <div className="report-content"><RenderMarkdown content={report.content} /></div>}
              {report.error_log && <p className="error-banner">{report.error_log}</p>}
            </details>)}
            {!reports.length && <Empty text="至少需要一条经模型审核且可用于报告的证据链。" />}
          </div>
        </Section>
      )}
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Building2; label: string; value: number }) {
  return <div className="supply-chain-metric"><Icon size={19} /><div><strong>{value}</strong><span>{label}</span></div></div>;
}
function Section({ title, actions, children }: { title: string; actions: React.ReactNode; children: React.ReactNode }) {
  return <section className="supply-chain-section"><header><h3>{title}</h3><div>{actions}</div></header>{children}</section>;
}
function Action({ text, onClick, primary = false }: { text: string; onClick: () => void; primary?: boolean }) {
  return <button type="button" className={`btn ${primary ? "btn-primary" : "btn-secondary"}`} onClick={onClick}><Plus size={15} />{text}</button>;
}
function Field({ label, value, set, type = "text", required = false }: { label: string; value: string; set: (value: string) => void; type?: string; required?: boolean }) {
  return <label>{label}<input type={type} value={value} onChange={(event) => set(event.target.value)} required={required} /></label>;
}
function Empty({ text }: { text: string }) { return <div className="supply-chain-empty">{text}</div>; }

function ChainStatusStrip({ investigation, dashboard, entityCount, relationCount }: {
  investigation: SupplyChainInvestigation | null;
  dashboard: SupplyChainDashboard;
  entityCount: number;
  relationCount: number;
}) {
  const score = investigation?.completeness_score || 0;
  const statusText = !investigation
    ? "等待选择供应链"
    : score >= 80 ? "链路证据充足" : score >= 50 ? "持续核验中" : "重点补证中";
  return (
    <section className="supply-chain-status-strip" aria-label="当前供应链运行状态">
      <div className="supply-chain-status-main">
        <span className="supply-chain-live-dot" aria-hidden="true" />
        <Activity size={16} />
        <div><small>CHAIN STATUS</small><strong>{statusText}</strong></div>
      </div>
      <div><small>证据完整度</small><strong>{investigation ? `${score}%` : "—"}</strong></div>
      <div><small>穿透节点</small><strong>{entityCount.toLocaleString("zh-CN")}</strong></div>
      <div><small>已识别关系</small><strong>{relationCount.toLocaleString("zh-CN")}</strong></div>
      <div><small>可报告证据</small><strong>{dashboard.reportable.toLocaleString("zh-CN")}</strong></div>
    </section>
  );
}

function BatterySupplyChainMap() {
  return (
    <section className="supply-chain-visual">
      <header>
        <div>
          <span>SUPPLY CHAIN MAP</span>
          <h3>供应链条展示</h3>
        </div>
        <small>中国供应端、美国整合节点与军方采购项目关联图谱</small>
      </header>
      <div className="chain-network">
        <div className="chain-network-grid" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />

        <div className="chain-network-group chain-network-group--suppliers">
          <Factory size={18} />
          <div><strong>中国供应端</strong><small>电池、电芯与在华制造节点</small></div>
        </div>
        <div className="chain-network-group chain-network-group--programs">
          <ShieldCheck size={18} />
          <div><strong>美国军方应用端</strong><small>采购合同与装备项目</small></div>
        </div>

        <svg className="chain-network-lines" viewBox="0 0 1200 680" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="arrow-contract" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
            <marker id="arrow-application" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
          </defs>

          <path id="trade-path-1" className="chain-path chain-path--trade" d="M286 196 C360 196 372 300 458 318" markerEnd="url(#arrow-trade)" />
          <path id="trade-path-2" className="chain-path chain-path--trade" d="M286 338 C356 338 384 338 458 338" markerEnd="url(#arrow-trade)" />
          <path id="trade-path-3" className="chain-path chain-path--trade" d="M286 480 C360 480 374 382 458 358" markerEnd="url(#arrow-trade)" />
          <path id="contract-path" className="chain-path chain-path--contract" d="M600 150 C600 204 600 235 600 276" markerEnd="url(#arrow-contract)" />
          <path id="application-path-1" className="chain-path chain-path--application" d="M742 318 C816 306 830 196 900 196" markerEnd="url(#arrow-application)" />
          <path id="application-path-2" className="chain-path chain-path--application" d="M742 338 C816 338 830 338 900 338" markerEnd="url(#arrow-application)" />
          <path id="application-path-3" className="chain-path chain-path--application" d="M742 358 C816 370 830 480 900 480" markerEnd="url(#arrow-application)" />

          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#trade-path-1" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.2s" begin="-1.6s" repeatCount="indefinite"><mpath href="#trade-path-3" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="2.6s" repeatCount="indefinite"><mpath href="#contract-path" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#application-path-2" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label chain-relation-label--trade">自华进口</span>
        <span className="chain-relation-label chain-relation-label--contract">合同授予</span>
        <span className="chain-relation-label chain-relation-label--application">军方供货</span>

        <NetworkNode
          className="chain-network-node--supplier-one"
          icon={Factory}
          eyebrow="全资制造节点"
          name="深圳市艾博尔新能源有限公司"
          role="锂离子电池、锂金属一次电池"
          tone="trade"
        />
        <NetworkNode
          className="chain-network-node--supplier-two"
          icon={Factory}
          eyebrow="电池供应商"
          name="山东精工电源科技有限公司"
          role="7,454千克锂离子电池"
          tone="trade"
        />
        <NetworkNode
          className="chain-network-node--supplier-three"
          icon={Factory}
          eyebrow="电芯供应商"
          name="天津力神电池股份有限公司"
          role="5,055千克锂离子电芯"
          tone="trade"
        />
        <NetworkNode
          className="chain-network-node--dla"
          icon={Landmark}
          eyebrow="美国政府采购机构"
          name="U.S. Defense Logistics Agency"
          role="BA-5390军用电池采购 · 约520万美元"
          tone="contract"
        />
        <NetworkNode
          className="chain-network-node--center"
          icon={BatteryCharging}
          eyebrow="军用电池整合与交付"
          name="Ultralife Corporation"
          role="研发、制造、认证及军方合同履约"
          tone="focus"
          emphasis
        />
        <NetworkNode
          className="chain-network-node--program-one"
          icon={BatteryCharging}
          eyebrow="国防后勤保障"
          name="BA-5390 Battery Program"
          role="非充电式锂二氧化锰军用电池"
          tone="application"
        />
        <NetworkNode
          className="chain-network-node--program-two"
          icon={Anchor}
          eyebrow="美国海军装备项目"
          name="U.S. Navy MK 68"
          role="BA-5390A/U锂电池独家采购"
          tone="application"
        />
        <NetworkNode
          className="chain-network-node--program-three"
          icon={Crosshair}
          eyebrow="美国陆军单兵系统"
          name="U.S. Army Nett Warrior"
          role="Conformal Wearable Battery"
          tone="application"
        />
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />自华贸易关系</span>
        <span><i className="chain-dot chain-dot--contract" />政府采购合同</span>
        <span><i className="chain-dot chain-dot--application" />装备应用关系</span>
        <p>图谱反映企业、贸易与军方合同之间的关联，不代表每批自华进口货物均已证实进入具体军用项目。</p>
      </div>
    </section>
  );
}

function GadoliniumSupplyChainMap() {
  return (
    <section className="supply-chain-visual supply-chain-visual--rare-earth">
      <header>
        <div>
          <span>RARE EARTH SUPPLY NETWORK</span>
          <h3>高纯稀土供应链关系图谱</h3>
        </div>
        <small>中国稀土供应端 → 美国进口仓储网络 → 国防储备与军工材料体系</small>
      </header>
      <div className="chain-network chain-network--rare-earth">
        <div className="chain-network-grid" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />

        <div className="chain-network-group chain-network-group--suppliers">
          <Factory size={18} />
          <div><strong>中国稀土供应端</strong><small>高纯稀土化合物出口节点</small></div>
        </div>
        <div className="chain-network-group chain-network-group--programs">
          <ShieldCheck size={18} />
          <div><strong>美国防务关联网络</strong><small>储备、材料与海军应用体系</small></div>
        </div>

        <svg className="chain-network-lines" viewBox="0 0 1200 760" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="rare-arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="rare-arrow-contract" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
            <marker id="rare-arrow-distribution" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--distribution" />
            </marker>
            <marker id="rare-arrow-personnel" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--personnel" />
            </marker>
            <marker id="rare-arrow-application" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
          </defs>

          <path id="rare-trade-1" className="chain-path chain-path--trade" d="M286 170 C360 170 375 296 458 326" markerEnd="url(#rare-arrow-trade)" />
          <path id="rare-trade-2" className="chain-path chain-path--trade" d="M286 302 C364 302 380 330 458 340" markerEnd="url(#rare-arrow-trade)" />
          <path id="rare-trade-3" className="chain-path chain-path--trade" d="M286 434 C364 434 380 380 458 356" markerEnd="url(#rare-arrow-trade)" />
          <path id="rare-trade-4" className="chain-path chain-path--trade" d="M286 566 C356 566 380 603 458 610" markerEnd="url(#rare-arrow-trade)" />
          <path id="rare-contract-ge" className="chain-path chain-path--contract" d="M600 132 C600 198 600 238 600 280" markerEnd="url(#rare-arrow-contract)" />
          <path id="rare-contract-res" className="chain-path chain-path--contract" d="M730 90 C846 90 806 365 900 365" markerEnd="url(#rare-arrow-contract)" />
          <path id="rare-distribution-ge" className="chain-path chain-path--distribution" d="M742 334 C820 312 826 206 900 206" markerEnd="url(#rare-arrow-distribution)" />
          <path id="rare-distribution-c5" className="chain-path chain-path--distribution" d="M742 610 C826 590 822 238 900 220" markerEnd="url(#rare-arrow-distribution)" />
          <path id="rare-personnel" className="chain-path chain-path--personnel" d="M742 355 C818 355 828 365 900 365" markerEnd="url(#rare-arrow-personnel)" />
          <path id="rare-application" className="chain-path chain-path--application" d="M1022 272 C1022 352 1022 448 1022 520" markerEnd="url(#rare-arrow-application)" />

          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#rare-trade-1" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.4s" begin="-1.7s" repeatCount="indefinite"><mpath href="#rare-trade-4" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="2.7s" repeatCount="indefinite"><mpath href="#rare-contract-ge" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--distribution">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#rare-distribution-ge" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--personnel">
            <animateMotion dur="2.8s" repeatCount="indefinite"><mpath href="#rare-personnel" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#rare-application" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label rare-label--trade">稀土产品输入</span>
        <span className="chain-relation-label rare-label--contract">国防合同</span>
        <span className="chain-relation-label rare-label--distribution">分销/流转</span>
        <span className="chain-relation-label rare-label--personnel">人员关联</span>
        <span className="chain-relation-label rare-label--application">材料应用</span>

        <NetworkNode
          className="rare-node--supplier-one"
          icon={Factory}
          eyebrow="高纯稀土供应商"
          name="四川沃耐稀新材料科技有限公司"
          role="20,060千克氯化镧"
          tone="trade"
        />
        <NetworkNode
          className="rare-node--supplier-two"
          icon={Factory}
          eyebrow="稀土出口商"
          name="江苏省有色金属进出口有限公司"
          role="10,050千克氧化镱"
          tone="trade"
        />
        <NetworkNode
          className="rare-node--supplier-three"
          icon={Factory}
          eyebrow="稀土产品供应节点"
          name="内蒙古包钢稀土相关出口主体"
          role="60,240千克氧化镧 · 经釜山中转"
          tone="trade"
        />
        <NetworkNode
          className="rare-node--supplier-four"
          icon={Factory}
          eyebrow="受控氧化钆出口商"
          name="福建省金龙稀土股份有限公司"
          role="22,340千克高纯氧化钆"
          tone="trade"
        />
        <NetworkNode
          className="rare-node--dla"
          icon={Landmark}
          eyebrow="美国政府采购机构"
          name="U.S. Defense Logistics Agency"
          role="国家国防储备 · 钐钆战时保障评估"
          tone="contract"
        />
        <NetworkNode
          className="rare-node--center"
          icon={FlaskConical}
          eyebrow="进口、采购及分销节点"
          name="G.E. Chaplin, Inc."
          role="DLA储备合同供应商 · CREaTe成员"
          tone="focus"
          emphasis
        />
        <NetworkNode
          className="rare-node--warehouse"
          icon={Warehouse}
          eyebrow="美国仓储与物流节点"
          name="C5 Warehousing and Logistics LLC"
          role="氧化钆收货及稀土产品流转节点"
          tone="distribution"
        />
        <NetworkNode
          className="rare-node--tci"
          icon={FlaskConical}
          eyebrow="先进陶瓷与磁性材料体系"
          name="TCI Ceramics / National Magnetics Group"
          role="含钆材料能力 · 美国海军供应链节点"
          tone="distribution"
        />
        <NetworkNode
          className="rare-node--salts"
          icon={FlaskConical}
          eyebrow="美国国防生产法项目"
          name="Rare Earth Salts"
          role="获422万美元支持扩大氧化铽产能"
          tone="personnel"
        />
        <NetworkNode
          className="rare-node--navy"
          icon={RadioTower}
          eyebrow="美国海军应用网络"
          name="Lockheed Martin Sippican"
          role="潜艇通信及多功能桅杆天线供应链"
          tone="application"
        />
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />自华贸易关系</span>
        <span><i className="chain-dot chain-dot--contract" />政府采购合同</span>
        <span><i className="chain-dot chain-dot--distribution" />仓储分拨关系</span>
        <span><i className="chain-dot chain-dot--personnel" />人员关联</span>
        <span><i className="chain-dot chain-dot--application" />装备应用关系</span>
        <p>图谱展示已核验主体及关联路径；具体批次进入军事项目的最终用途仍需持续核查。</p>
      </div>
    </section>
  );
}

function IndiaShipComponentsMap() {
  return (
    <section className="supply-chain-visual supply-chain-visual--india">
      <header>
        <div>
          <span>INDIA INTEGRATED SUPPLY NETWORK</span>
          <h3>涉印—台船石化工程泵供应链图谱</h3>
        </div>
        <small>中国产部件 → 印度泵组集成 → 台船EPC采购 → 中油石化储运项目</small>
      </header>
      <div className="chain-network chain-network--india">
        <div className="chain-network-grid" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />

        <div className="chain-network-group chain-network-group--suppliers">
          <Factory size={18} />
          <div><strong>中国关键配件供应端</strong><small>流体部件与泵组动力配套</small></div>
        </div>
        <div className="chain-network-group chain-network-group--programs">
          <ShipWheel size={18} />
          <div><strong>台船EPC与石化项目</strong><small>储槽、槽车装卸和码头装卸工艺系统</small></div>
        </div>

        <svg className="chain-network-lines" viewBox="0 0 1200 680" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="india-arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="india-arrow-group" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--personnel" />
            </marker>
            <marker id="india-arrow-delivery" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--distribution" />
            </marker>
            <marker id="india-arrow-application" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
            <marker id="india-arrow-review" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
          </defs>

          <path id="india-trade-pump" className="chain-path chain-path--trade" d="M286 235 C365 235 380 310 458 330" markerEnd="url(#india-arrow-trade)" />
          <path id="india-trade-motor" className="chain-path chain-path--trade" d="M286 445 C365 445 380 370 458 350" markerEnd="url(#india-arrow-trade)" />
          <path id="india-group-link" className="chain-path chain-path--personnel" d="M600 140 C600 195 600 235 600 278" markerEnd="url(#india-arrow-group)" />
          <path id="india-delivery-link" className="chain-path chain-path--distribution" d="M742 338 C816 318 830 218 900 210" markerEnd="url(#india-arrow-delivery)" />
          <path id="india-project-link" className="chain-path chain-path--application" d="M1022 274 C1022 320 1022 350 1022 388" markerEnd="url(#india-arrow-application)" />
          <path id="india-review-link" className="chain-path chain-path--contract chain-path--review" d="M1022 585 C1022 550 1022 515 1022 486" markerEnd="url(#india-arrow-review)" />

          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.1s" repeatCount="indefinite"><mpath href="#india-trade-pump" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.1s" begin="-1.55s" repeatCount="indefinite"><mpath href="#india-trade-motor" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--personnel">
            <animateMotion dur="2.8s" repeatCount="indefinite"><mpath href="#india-group-link" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--distribution">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#india-delivery-link" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="2.8s" repeatCount="indefinite"><mpath href="#india-project-link" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label india-label--trade">配件输入</span>
        <span className="chain-relation-label india-label--group">集团关系</span>
        <span className="chain-relation-label india-label--delivery">泵组交付</span>
        <span className="chain-relation-label india-label--application">EPC项目</span>
        <span className="chain-relation-label india-label--review">军工排除</span>

        <NetworkNode
          className="india-node--pump"
          icon={Factory}
          eyebrow="泵体与流体部件供应商"
          name="苏州苏尔寿泵业有限公司"
          role="9条裸轴泵、泵体及备件供货记录"
          tone="trade"
        />
        <NetworkNode
          className="india-node--motor"
          icon={Factory}
          eyebrow="泵组动力配套供应商"
          name="卧龙电气南阳防爆集团股份有限公司"
          role="7条工业电机供货记录"
          tone="trade"
        />
        <NetworkNode
          className="india-node--parent"
          icon={Building2}
          eyebrow="跨国集团控制层"
          name="Sulzer Ltd"
          role="中国供应节点与印度集成节点的集团主体"
          tone="personnel"
        />
        <NetworkNode
          className="india-node--integrator"
          icon={PackageSearch}
          eyebrow="印度集成、组装与项目交付"
          name="Sulzer Pumps India Private Limited"
          role="多来源部件整合为可交付离心泵组"
          tone="focus"
          emphasis
        />
        <NetworkNode
          className="india-node--csbc"
          icon={ShipWheel}
          eyebrow="石化工程EPC承包方"
          name="CSBC Corporation, Taiwan"
          role="接收至少6批次、11台/套石化工艺泵组"
          tone="distribution"
        />
        <NetworkNode
          className="india-node--manta"
          icon={Factory}
          eyebrow="石化项目最终业主"
          name="台湾中油大林石化油品储运中心"
          role="26座石化储槽及槽车装卸工场统包工程"
          tone="application"
        />
        <NetworkNode
          className="india-node--lockheed"
          icon={ShieldCheck}
          eyebrow="已排除的军工关联"
          name="奋进魔鬼鱼 / 海鲲潜艇"
          role="泵型与标签指向石化工程，不纳入军工供应链"
          tone="contract"
        />
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />中国产部件</span>
        <span><i className="chain-dot chain-dot--personnel" />集团控制关系</span>
        <span><i className="chain-dot chain-dot--distribution" />印度集成交付</span>
        <span><i className="chain-dot chain-dot--application" />石化项目归属</span>
        <p>贸易链路与石化EPC项目已经交叉核验；同一收货企业同时承接军民项目，不能据此推定货物进入军用平台。</p>
      </div>
    </section>
  );
}

function DhakshaDroneSupplyChainMap() {
  return (
    <section className="supply-chain-visual supply-chain-visual--dhaksha">
      <header>
        <div>
          <span>INDIA MILITARY DRONE SUPPLY NETWORK</span>
          <h3>Dhaksha军用物流无人机供应链</h3>
        </div>
        <small>中国测试设备供应端 → 印度无人机制造端 → 印度陆军采购项目</small>
      </header>
      <div className="chain-network chain-network--dhaksha">
        <div className="chain-network-grid" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />

        <div className="chain-network-group chain-network-group--suppliers">
          <Factory size={18} />
          <div><strong>中国设备供应端</strong><small>推力校准与生产检测设备</small></div>
        </div>
        <div className="chain-network-group chain-network-group--programs">
          <ShieldCheck size={18} />
          <div><strong>印度军方应用端</strong><small>陆军物流无人机采购与审查</small></div>
        </div>

        <svg className="chain-network-lines" viewBox="0 0 1200 680" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="dhaksha-arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="dhaksha-arrow-control" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--personnel" />
            </marker>
            <marker id="dhaksha-arrow-contract" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
            <marker id="dhaksha-arrow-review" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
          </defs>

          <path id="dhaksha-trade" className="chain-path chain-path--trade" d="M286 338 C360 338 384 338 458 338" markerEnd="url(#dhaksha-arrow-trade)" />
          <path id="dhaksha-control" className="chain-path chain-path--personnel" d="M600 150 C600 205 600 232 600 278" markerEnd="url(#dhaksha-arrow-control)" />
          <path id="dhaksha-contract" className="chain-path chain-path--contract" d="M742 328 C816 312 832 225 900 214" markerEnd="url(#dhaksha-arrow-contract)" />
          <path id="dhaksha-review" className="chain-path chain-path--application" d="M1020 280 C1020 338 1020 382 1020 430" markerEnd="url(#dhaksha-arrow-review)" />

          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="2.8s" repeatCount="indefinite"><mpath href="#dhaksha-trade" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--personnel">
            <animateMotion dur="2.7s" repeatCount="indefinite"><mpath href="#dhaksha-control" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#dhaksha-contract" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#dhaksha-review" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label dhaksha-label--trade">自华进口</span>
        <span className="chain-relation-label dhaksha-label--control">控股关系</span>
        <span className="chain-relation-label dhaksha-label--contract">200架采购</span>
        <span className="chain-relation-label dhaksha-label--review">供应链审查</span>

        <NetworkNode
          className="dhaksha-node--supplier"
          icon={Factory}
          eyebrow="中国测试设备供应商"
          name="天津新翼先进科技有限公司（待工商核名）"
          role="LY-70KGF推力测试台、校准工具及AOI检测设备"
          tone="trade"
        />
        <NetworkNode
          className="dhaksha-node--parent"
          icon={Building2}
          eyebrow="印度控股母公司"
          name="Coromandel International Limited"
          role="Dhaksha控股与产业资源支持"
          tone="personnel"
        />
        <NetworkNode
          className="dhaksha-node--integrator"
          icon={PackageSearch}
          eyebrow="无人机研发制造与系统集成"
          name="Dhaksha Unmanned Systems"
          role="接收中国测试设备，承担物流无人机生产与交付"
          tone="focus"
          emphasis
        />
        <NetworkNode
          className="dhaksha-node--army"
          icon={ShieldCheck}
          eyebrow="军方采购与最终用户"
          name="Indian Army"
          role="200架中空物流无人机采购项目"
          tone="contract"
        />
        <NetworkNode
          className="dhaksha-node--review"
          icon={FileSearch}
          eyebrow="供应链风险审查"
          name="中国来源部件与设备核查"
          role="合同一度因中国来源疑虑受到审查"
          tone="application"
        />
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />已核实贸易记录</span>
        <span><i className="chain-dot chain-dot--personnel" />企业控制关系</span>
        <span><i className="chain-dot chain-dot--contract" />军方采购关系</span>
        <span><i className="chain-dot chain-dot--application" />风险审查关系</span>
        <p>贸易记录确认中国测试设备进入Dhaksha生产供应链；设备是否专用于印度陆军200架物流无人机合同仍需结合序列号、产线资料或合同附件核验。</p>
      </div>
    </section>
  );
}

function QuadrantSupplyChainMap() {
  return (
    <section className="supply-chain-visual supply-chain-visual--quadrant">
      <header>
        <div>
          <span>QUADRANT DEFENSE MAGNET NETWORK</span>
          <h3>Quadrant稀土磁体军工供应链图谱</h3>
        </div>
        <small>中国制造与贸易节点 → Quadrant Magnetics → 美国零部件企业 → 军用装备</small>
      </header>
      <div className="quadrant-network">
        <div className="quadrant-network-grid" aria-hidden="true" />
        <svg className="quadrant-network-lines" viewBox="0 0 1280 620" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="quadrant-arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="quadrant-arrow-group" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--personnel" />
            </marker>
            <marker id="quadrant-arrow-supply" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
            <marker id="quadrant-arrow-application" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
          </defs>
          <path id="quadrant-trade-link" className="chain-path chain-path--trade" d="M268 190 C350 190 365 300 458 310" markerEnd="url(#quadrant-arrow-trade)" />
          <path id="quadrant-group-link" className="chain-path chain-path--personnel" d="M268 430 C350 430 365 340 458 330" markerEnd="url(#quadrant-arrow-group)" />
          <path id="quadrant-component-one" className="chain-path chain-path--contract" d="M708 305 C790 275 800 190 872 185" markerEnd="url(#quadrant-arrow-supply)" />
          <path id="quadrant-component-two" className="chain-path chain-path--contract" d="M708 335 C790 365 800 430 872 435" markerEnd="url(#quadrant-arrow-supply)" />
          <path id="quadrant-program-one" className="chain-path chain-path--application" d="M1090 185 C1140 185 1155 235 1190 250" markerEnd="url(#quadrant-arrow-application)" />
          <path id="quadrant-program-two" className="chain-path chain-path--application" d="M1090 435 C1140 435 1155 385 1190 370" markerEnd="url(#quadrant-arrow-application)" />
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#quadrant-trade-link" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--personnel">
            <animateMotion dur="3.2s" begin="-1.4s" repeatCount="indefinite"><mpath href="#quadrant-group-link" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="2.8s" repeatCount="indefinite"><mpath href="#quadrant-component-one" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="2.8s" begin="-1.4s" repeatCount="indefinite"><mpath href="#quadrant-component-two" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="2.6s" repeatCount="indefinite"><mpath href="#quadrant-program-one" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="2.6s" begin="-1.3s" repeatCount="indefinite"><mpath href="#quadrant-program-two" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label quadrant-label--trade">历史提单 · 稀土磁体</span>
        <span className="chain-relation-label quadrant-label--group">集团制造节点</span>
        <span className="chain-relation-label quadrant-label--supply">磁体供应</span>
        <span className="chain-relation-label quadrant-label--application">组件进入装备</span>

        <NetworkNode
          className="quadrant-node--xmag"
          icon={Factory}
          eyebrow="中国历史贸易关联供应商"
          name="杭州X-Mag公司"
          role="2024年5月向Quadrant发运3,050千克稀土磁体"
          tone="trade"
        />
        <NetworkNode
          className="quadrant-node--hangzhou"
          icon={Building2}
          eyebrow="集团在华制造节点"
          name="Quadrant杭州制造中心"
          role="磁性技术、模块设计与量产中心"
          tone="personnel"
        />
        <NetworkNode
          className="quadrant-node--center"
          icon={PackageSearch}
          eyebrow="美国磁体设计与供应主体"
          name="Quadrant Magnetics LLC"
          role="进口中国制造稀土磁体，并向美国零部件企业供应"
          tone="focus"
          emphasis
        />
        <NetworkNode
          className="quadrant-node--component-one"
          icon={Factory}
          eyebrow="美国下游零部件企业"
          name="U.S. Component Company 1"
          role="司法材料未披露企业名称"
          tone="contract"
        />
        <NetworkNode
          className="quadrant-node--component-two"
          icon={Factory}
          eyebrow="美国下游零部件企业"
          name="U.S. Component Company 2"
          role="司法材料未披露企业名称"
          tone="contract"
        />
        <article className="quadrant-programs">
          <div><ShieldCheck size={20} /><span>美国国防部装备端</span></div>
          <strong>F-16 · F/A-18 · 其他国防资产</strong>
          <small>美国司法部材料确认下游组件进入上述装备体系，具体部件与合同批次仍待穿透。</small>
        </article>
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />直接贸易记录</span>
        <span><i className="chain-dot chain-dot--personnel" />集团制造关系</span>
        <span><i className="chain-dot chain-dot--contract" />下游供应关系</span>
        <span><i className="chain-dot chain-dot--application" />装备应用关系</span>
        <p>2026年杭州X-Mag仍有对美出口，但公开记录未确认买方为Quadrant，暂不并入直接链路；匿名企业不作推测性命名。</p>
      </div>
    </section>
  );
}

function GenericSupplyChainMap({
  investigation, entities, cases, shipments, motionEnabled, onMotionChange,
}: {
  investigation: SupplyChainInvestigation;
  entities: SupplyChainEntity[];
  cases: SupplyChainCase[];
  shipments: SupplyChainShipment[];
  motionEnabled: boolean;
  onMotionChange: (enabled: boolean) => void;
}) {
  const isUpstream = (item: SupplyChainEntity) => (
    item.country === "China"
    || ["component_supplier", "trading_company", "parent_company", "china_exporter"].includes(item.entity_type)
  );
  const isPumpChain = investigation.id === "inv-india-csbc-pump-chain";
  const isRejectedRossellCandidate = investigation.id === "inv-india-rossell-china-cables-ah64-taiwan";
  const isPumpContextOnly = (item: SupplyChainEntity) => isPumpChain && item.id === "ent-sulzer-ltd";
  const isEndUser = (item: SupplyChainEntity) => (
    ["military_end_user", "government_end_user", "government_agency", "industrial_end_user", "end_user"].includes(item.entity_type)
    || (!isPumpChain && item.entity_type === "terminal_shipyard")
  );
  const upstreamCandidates = entities.filter((item) => !isPumpContextOnly(item) && isUpstream(item));
  const primaryCase = cases[0];
  const fixedIntegratorIds: Record<string, string> = {
    "inv-taiwan-lead-moog-tianhe-pac3-magnets": "ent-taiwan-moog",
    "inv-taiwan-quadrant-china-magnets-f16": "ent-us-lead-quadrant-fighter-magnets",
    "inv-taiwan-m1a2-china-samarium": "ent-taiwan-m1a2-us-smco-maker",
    "inv-india-rossell-china-cables-ah64-taiwan": "ent-india-rossell-techsys",
  };
  const fixedIntegratorId = fixedIntegratorIds[investigation.id] || null;
  const integrator = entities.find((item) => item.id === fixedIntegratorId)
    || entities.find((item) => item.id === primaryCase?.supplier_entity_id)
    || entities.find((item) => ["integrator", "defense_supplier", "importer"].includes(item.entity_type))
    || entities.find((item) => !upstreamCandidates.some((row) => row.id === item.id))
    || entities[0];
  const upstream = upstreamCandidates.filter((item) => item.id !== integrator?.id);
  const endUsers = entities.filter((item) => item.id !== integrator?.id && !isPumpContextOnly(item) && isEndUser(item));
  const entityOnlyApplicationInvestigations = new Set([
    "inv-taiwan-lead-moog-tianhe-pac3-magnets",
    "inv-taiwan-quadrant-china-magnets-f16",
    "inv-taiwan-m1a2-china-samarium",
    "inv-india-rossell-china-cables-ah64-taiwan",
  ]);
  const applicationCases = entityOnlyApplicationInvestigations.has(investigation.id) ? [] : cases;
  const downstream = entities.filter((item) => (
    item.id !== integrator?.id
    && !isPumpContextOnly(item)
    && !upstream.some((row) => row.id === item.id)
    && !endUsers.some((row) => row.id === item.id)
  ));
  const shipmentProducts = shipments.reduce<Map<string, string[]>>((rows, item) => {
    const key = item.exporter_name.trim().toLocaleLowerCase();
    const products = rows.get(key) || [];
    return new Map(rows).set(key, products.includes(item.product) ? products : [...products, item.product]);
  }, new Map());
  const productsFor = (entity: SupplyChainEntity) => {
    const products = [entity.name, entity.name_zh, ...(entity.aliases || [])]
      .filter(Boolean)
      .flatMap((name) => shipmentProducts.get(String(name).trim().toLocaleLowerCase()) || []);
    return [...new Set(products)].join("；") || entity.defense_roles?.join(" · ") || "关联产品或供应关系待进一步细化";
  };
  const destinationCountry = downstream.find((item) => (
    ["military_end_user", "government_end_user", "industrial_end_user", "terminal_shipyard", "end_user"].includes(item.entity_type)
  ))?.country || shipments.find((item) => item.destination_country)?.destination_country || investigation.country;
  const destinationLabel = directions.find((item) => item.id === destinationCountry)?.short || destinationCountry;
  const stages: NetworkGraphStage[] = [
    {
      key: "upstream",
      title: "上游供应端",
      subtitle: `${upstream.length}个供应、制造或贸易节点`,
      tone: "trade",
      icon: Factory,
      nodes: upstream.map((entity) => ({
        id: entity.id,
        eyebrow: entityTypeLabel(entity.entity_type),
        name: entityDisplayName(entity),
        detail: productsFor(entity),
        icon: Factory,
      })),
    },
    {
      key: "integrator",
      title: "核心整合端",
      subtitle: "集成、生产与项目交付",
      tone: "focus",
      icon: Building2,
      nodes: integrator ? [{
        id: integrator.id,
        eyebrow: "核心整合与交付节点",
        name: entityDisplayName(integrator),
        detail: integrator.defense_roles?.join(" · ") || primaryCase?.product || "供应链集成与项目交付",
        icon: Building2,
      }] : [],
    },
    {
      key: "downstream",
      title: "下游承接端",
      subtitle: `${downstream.length}个制造、仓储或协作节点`,
      tone: "contract",
      icon: ShipWheel,
      nodes: downstream.map((entity) => ({
        id: entity.id,
        eyebrow: entityTypeLabel(entity.entity_type),
        name: entityDisplayName(entity),
        detail: entity.defense_roles?.join(" · ") || "下游承接、制造或协作节点",
        icon: ShipWheel,
      })),
    },
    {
      key: "application",
      title: `${destinationLabel}应用端`,
      subtitle: `${endUsers.length + applicationCases.length}个最终用户或项目`,
      tone: "application",
      icon: Landmark,
      nodes: [
        ...endUsers.map((entity) => ({
          id: entity.id,
          eyebrow: entityTypeLabel(entity.entity_type),
          name: entityDisplayName(entity),
          detail: entity.defense_roles?.join(" · ") || "最终用户或装备应用节点",
          icon: Landmark,
        })),
        ...applicationCases.map((item) => ({
          id: item.id,
          eyebrow: item.procurement_agency || "采购或应用项目",
          name: item.target_program || item.title,
          detail: item.product || item.procurement_reference || "项目内容待补充",
          icon: Crosshair,
        })),
      ],
    },
  ].filter((stage) => stage.nodes.length > 0) as NetworkGraphStage[];
  const graphHeight = Math.max(660, Math.max(...stages.map((stage) => stage.nodes.length), 1) * 148 + 170);
  const stagePositions = graphStagePositions(stages.length);
  const positionedStages = stages.map((stage, stageIndex) => ({
    ...stage,
    x: stagePositions[stageIndex],
    nodes: stage.nodes.map((node, nodeIndex) => ({
      ...node,
      x: stagePositions[stageIndex],
      y: graphNodeY(nodeIndex, stage.nodes.length, graphHeight),
    })),
  }));
  const graphEdges = isRejectedRossellCandidate ? [] : positionedStages.slice(0, -1).flatMap((stage, stageIndex) => {
    const nextStage = positionedStages[stageIndex + 1];
    const tone = nextStage.key === "application" ? "application" : stage.key === "upstream" ? "trade" : "contract";
    return connectGraphStages(stage.nodes, nextStage.nodes, tone);
  });
  const graphKey = investigation.id.replace(/[^a-zA-Z0-9_-]/g, "-");
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const allNodes = positionedStages.flatMap((stage) => stage.nodes.map((node) => ({
    ...node,
    stageTitle: stage.title,
    tone: stage.tone,
  })));
  const hasActiveNode = activeNodeId ? allNodes.some((node) => node.id === activeNodeId) : false;
  const effectiveActiveNodeId = hasActiveNode ? activeNodeId : integrator?.id || allNodes[0]?.id || null;
  const activeNode = allNodes.find((node) => node.id === effectiveActiveNodeId) || null;

  return (
    <section className="supply-chain-visual supply-chain-visual--network">
      <header>
        <div><span>SUPPLY CHAIN MAP</span><h3>供应链条展示</h3></div>
        <div className="supply-chain-map-toolbar">
          <span><Network size={14} />{allNodes.length} 个节点</span>
          <span><Route size={14} />{graphEdges.length} 条关系</span>
          <button
            type="button"
            onClick={() => onMotionChange(!motionEnabled)}
            aria-pressed={!motionEnabled}
            title={motionEnabled ? "暂停图谱动态效果" : "启用图谱动态效果"}
          >
            {motionEnabled ? <Pause size={14} /> : <Play size={14} />}
            {motionEnabled ? "暂停动态" : "启用动态"}
          </button>
        </div>
      </header>
      <div className="supply-chain-map-context">
        <div>
          <span className="supply-chain-live-dot" aria-hidden="true" />
          <strong>{investigation.name}</strong>
        </div>
        <span>{investigation.completeness_level}</span>
        <span>证据完整度 {investigation.completeness_score}%</span>
      </div>
      {isRejectedRossellCandidate && (
        <div className="supply-chain-map-context" role="note">
          <span>排歧结论：贸易记录保留，但现有料号证据不支持连接至AH-64或台湾机队，跨层关系已断开。</span>
        </div>
      )}
      <div className="dynamic-network-map">
        <div className="dynamic-network-canvas" style={{ height: graphHeight }}>
          <div className="dynamic-network-scan" aria-hidden="true" />
          <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
          <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />
          {positionedStages.map((stage) => (
            <div
              key={stage.key}
              className={`dynamic-network-band dynamic-network-band--${stage.tone}`}
              style={{ left: `${stage.x}%` }}
            >
              <stage.icon size={17} />
              <div><strong>{stage.title}</strong><small>{stage.subtitle}</small></div>
            </div>
          ))}
          <svg className="dynamic-network-lines" viewBox={`0 0 1000 ${graphHeight}`} preserveAspectRatio="none" aria-hidden="true">
            <defs>
              {(["trade", "contract", "application"] as const).map((tone) => (
                <marker key={tone} id={`${graphKey}-${tone}-arrow`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                  <path d="M0,0 L8,4 L0,8 Z" className={`chain-marker chain-marker--${tone}`} />
                </marker>
              ))}
            </defs>
            {graphEdges.map((edge, index) => {
              const pathId = `${graphKey}-edge-${index}`;
              const startX = edge.from.x * 10 + graphNodeHalfWidth(stages.length);
              const endX = edge.to.x * 10 - graphNodeHalfWidth(stages.length);
              const bend = Math.max(34, (endX - startX) * .42);
              const d = `M${startX} ${edge.from.y} C${startX + bend} ${edge.from.y} ${endX - bend} ${edge.to.y} ${endX} ${edge.to.y}`;
              return <g key={pathId}>
                <path id={pathId} className={`chain-path chain-path--${edge.tone}`} d={d} markerEnd={`url(#${graphKey}-${edge.tone}-arrow)`} />
                <circle r="4.5" className={`chain-particle chain-particle--${edge.tone}`}>
                  <animateMotion dur={`${2.7 + (index % 4) * .22}s`} begin={`${index * -.31}s`} repeatCount="indefinite"><mpath href={`#${pathId}`} /></animateMotion>
                </circle>
              </g>;
            })}
          </svg>
          {positionedStages.flatMap((stage) => stage.nodes.map((node) => (
            <DynamicNetworkNode
              key={`${stage.key}-${node.id}`}
              node={node}
              tone={stage.tone}
              stageCount={stages.length}
              active={node.id === effectiveActiveNodeId}
              onSelect={setActiveNodeId}
            />
          )))}
        </div>
      </div>
      {activeNode && (
        <div className={`supply-chain-node-inspector supply-chain-node-inspector--${activeNode.tone}`} aria-live="polite">
          <span>{activeNode.stageTitle}</span>
          <div><strong>{activeNode.name}</strong><p>{activeNode.detail}</p></div>
          <small>{activeNode.eyebrow}</small>
        </div>
      )}
      <div className="supply-chain-map-ledger" aria-label="穿透链路完整清单">
        <header><div><span>FULL PATH LEDGER</span><strong>穿透链路清单</strong></div><small>完整展示当前图谱全部节点</small></header>
        <div>
          {positionedStages.map((stage) => (
            <section key={stage.key} className={`supply-chain-ledger-stage supply-chain-ledger-stage--${stage.tone}`}>
              <header><stage.icon size={15} /><div><strong>{stage.title}</strong><small>{stage.nodes.length} 个节点</small></div></header>
              <div>
                {stage.nodes.map((node) => (
                  <button key={node.id} type="button" onClick={() => setActiveNodeId(node.id)}>
                    <strong>{node.name}</strong><span>{node.detail}</span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />上游贸易与供应</span>
        <span><i className="chain-dot chain-dot--contract" />企业集成与承接</span>
        <span><i className="chain-dot chain-dot--application" />合同及项目应用</span>
        <p>图谱完整展示当前供应链已关联的全部主体和采购项目；证据等级及尚待核实事项以“供应链证据链”页面为准。</p>
      </div>
    </section>
  );
}

type NetworkTone = "trade" | "focus" | "contract" | "application";
type NetworkGraphNode = {
  id: string;
  eyebrow: string;
  name: string;
  detail: string;
  icon: typeof Factory;
};
type PositionedNetworkGraphNode = NetworkGraphNode & { x: number; y: number };
type NetworkGraphStage = {
  key: string;
  title: string;
  subtitle: string;
  tone: NetworkTone;
  icon: typeof Factory;
  nodes: NetworkGraphNode[];
};

function graphStagePositions(count: number) {
  if (count <= 1) return [50];
  if (count === 2) return [22, 78];
  if (count === 3) return [14, 50, 86];
  return [11.5, 37, 63, 88.5];
}

function graphNodeY(index: number, count: number, height: number) {
  if (count <= 1) return height / 2 + 25;
  const top = 130;
  const bottom = height - 70;
  return top + ((bottom - top) * index) / (count - 1);
}

function graphNodeHalfWidth(stageCount: number) {
  return stageCount >= 4 ? 91 : stageCount === 3 ? 108 : 120;
}

function connectGraphStages(
  fromNodes: PositionedNetworkGraphNode[],
  toNodes: PositionedNetworkGraphNode[],
  tone: "trade" | "contract" | "application",
) {
  const edgeCount = Math.max(fromNodes.length, toNodes.length);
  return Array.from({ length: edgeCount }, (_, index) => ({
    from: fromNodes[index % fromNodes.length],
    to: toNodes[index % toNodes.length],
    tone,
  }));
}

function DynamicNetworkNode({ node, tone, stageCount, active, onSelect }: {
  node: PositionedNetworkGraphNode;
  tone: NetworkTone;
  stageCount: number;
  active: boolean;
  onSelect: (id: string) => void;
}) {
  const Icon = node.icon;
  return <button
    type="button"
    className={`dynamic-network-node dynamic-network-node--${tone}${active ? " dynamic-network-node--active" : ""}`}
    style={{ left: `${node.x}%`, top: node.y, width: `${graphNodeHalfWidth(stageCount) * .2}%` }}
    onClick={() => onSelect(node.id)}
    aria-pressed={active}
  >
    <span className="dynamic-network-node-icon"><Icon size={17} /></span>
    <div>
      <span>{node.eyebrow}</span>
      <strong>{node.name}</strong>
      <small>{node.detail}</small>
    </div>
  </button>;
}

function LegacyGenericSupplyChainMap({
  investigation, entities, cases, shipments,
}: {
  investigation: SupplyChainInvestigation;
  entities: SupplyChainEntity[];
  cases: SupplyChainCase[];
  shipments: SupplyChainShipment[];
}) {
  const suppliers = entities.filter((item) => (
    item.country === "China"
    || item.entity_type === "component_supplier"
    || item.entity_type === "trading_company"
    || item.entity_type === "parent_company"
  ));
  const endUsers = entities.filter((item) => (
    item.entity_type === "military_end_user"
    || item.entity_type === "government_end_user"
    || item.entity_type === "government_agency"
    || item.entity_type === "industrial_end_user"
    || item.entity_type === "terminal_shipyard"
    || item.entity_type === "end_user"
  ));
  const primaryCase = cases[0];
  const integrator = entities.find((item) => item.id === primaryCase?.supplier_entity_id)
    || entities.find((item) => item.entity_type === "integrator")
    || entities.find((item) => item.entity_type === "defense_supplier")
    || entities.find((item) => !suppliers.some((supplier) => supplier.id === item.id))
    || entities[0];
  const shipmentByExporter = new Map(
    shipments.map((item) => [item.exporter_name.trim().toLocaleLowerCase(), item]),
  );
  const visibleSuppliers = suppliers.filter((item) => item.id !== integrator?.id).slice(0, 3);
  const projectNodes = [
    ...endUsers.slice(0, 3).map((entity) => ({
      id: entity.id,
      name: entityDisplayName(entity),
      eyebrow: "政府或军方最终用户",
      role: entity.defense_roles?.[0] || "最终用户与装备应用端",
      icon: Landmark,
    })),
    ...cases.map((item) => ({
      id: item.id,
      name: item.target_program || item.title,
      eyebrow: item.procurement_agency || "军方采购项目",
      role: item.product || "采购与项目供应关系",
      icon: Crosshair,
    })),
  ].filter((item, index, rows) => rows.findIndex((row) => row.name === item.name) === index).slice(0, 3);
  const targetCountry = directions.find((item) => item.id === investigation.country)?.short
    || investigation.country;
  const supplierPositions = [
    "chain-network-node--supplier-one",
    "chain-network-node--supplier-two",
    "chain-network-node--supplier-three",
  ];
  const programPositions = [
    "chain-network-node--program-one",
    "chain-network-node--program-two",
    "chain-network-node--program-three",
  ];

  return (
    <section className="supply-chain-visual">
      <header>
        <div>
          <span>SUPPLY CHAIN MAP</span>
          <h3>供应链条展示</h3>
        </div>
        <small>{investigation.name} · {investigation.completeness_level} · 证据完整度 {investigation.completeness_score}%</small>
      </header>
      <div className="chain-network">
        <div className="chain-network-grid" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--one" aria-hidden="true" />
        <div className="chain-network-orbit chain-network-orbit--two" aria-hidden="true" />

        <div className="chain-network-group chain-network-group--suppliers">
          <Factory size={18} />
          <div><strong>上游供应端</strong><small>集团、供应商、制造与贸易节点</small></div>
        </div>
        <div className="chain-network-group chain-network-group--programs">
          <ShieldCheck size={18} />
          <div><strong>{targetCountry}应用端</strong><small>采购合同、最终用户与装备项目</small></div>
        </div>

        <svg className="chain-network-lines" viewBox="0 0 1200 680" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="generic-arrow-trade" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--trade" />
            </marker>
            <marker id="generic-arrow-contract" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--contract" />
            </marker>
            <marker id="generic-arrow-application" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" className="chain-marker chain-marker--application" />
            </marker>
          </defs>
          <path id="generic-trade-1" className="chain-path chain-path--trade" d="M286 196 C360 196 372 300 458 318" markerEnd="url(#generic-arrow-trade)" />
          <path id="generic-trade-2" className="chain-path chain-path--trade" d="M286 338 C356 338 384 338 458 338" markerEnd="url(#generic-arrow-trade)" />
          <path id="generic-trade-3" className="chain-path chain-path--trade" d="M286 480 C360 480 374 382 458 358" markerEnd="url(#generic-arrow-trade)" />
          <path id="generic-contract" className="chain-path chain-path--contract" d="M600 150 C600 204 600 235 600 276" markerEnd="url(#generic-arrow-contract)" />
          <path id="generic-application-1" className="chain-path chain-path--application" d="M742 318 C816 306 830 196 900 196" markerEnd="url(#generic-arrow-application)" />
          <path id="generic-application-2" className="chain-path chain-path--application" d="M742 338 C816 338 830 338 900 338" markerEnd="url(#generic-arrow-application)" />
          <path id="generic-application-3" className="chain-path chain-path--application" d="M742 358 C816 370 830 480 900 480" markerEnd="url(#generic-arrow-application)" />
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#generic-trade-1" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--trade">
            <animateMotion dur="3.2s" begin="-1.6s" repeatCount="indefinite"><mpath href="#generic-trade-3" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--contract">
            <animateMotion dur="2.6s" repeatCount="indefinite"><mpath href="#generic-contract" /></animateMotion>
          </circle>
          <circle r="5" className="chain-particle chain-particle--application">
            <animateMotion dur="3s" repeatCount="indefinite"><mpath href="#generic-application-2" /></animateMotion>
          </circle>
        </svg>

        <span className="chain-relation-label chain-relation-label--trade">跨境输入</span>
        <span className="chain-relation-label chain-relation-label--contract">合同授予</span>
        <span className="chain-relation-label chain-relation-label--application">项目供应</span>

        {visibleSuppliers.map((entity, index) => {
          const shipment = shipmentByExporter.get(entity.name.trim().toLocaleLowerCase())
            || (entity.name_zh ? shipmentByExporter.get(entity.name_zh.trim().toLocaleLowerCase()) : undefined);
          return <NetworkNode
            key={entity.id}
            className={supplierPositions[index]}
            icon={Factory}
            eyebrow={
              entity.entity_type === "parent_company" ? "集团控制与技术节点"
                : entity.entity_type === "trading_company" ? "贸易供应节点"
                  : "制造供应节点"
            }
            name={entityDisplayName(entity)}
            role={shipment?.product || entity.defense_roles?.[0] || "部件或设备供应"}
            tone="trade"
          />;
        })}
        {!visibleSuppliers.length && <NetworkNode
          className="chain-network-node--supplier-two"
          icon={Factory}
          eyebrow="待穿透节点"
          name="上游供应主体待识别"
          role="需补充完整提单、制造商或出口商信息"
          tone="trade"
        />}
        {primaryCase && <NetworkNode
          className="chain-network-node--dla"
          icon={Landmark}
          eyebrow={primaryCase.procurement_agency || "政府采购机构"}
          name={primaryCase.title}
          role={primaryCase.procurement_reference || primaryCase.product || "采购合同"}
          tone="contract"
        />}
        <NetworkNode
          className="chain-network-node--center"
          icon={Building2}
          eyebrow="核心整合与交付节点"
          name={integrator ? entityDisplayName(integrator) : "核心企业待识别"}
          role={integrator?.defense_roles?.join(" · ") || primaryCase?.product || "供应链集成与项目交付"}
          tone="focus"
          emphasis
        />
        {projectNodes.map((item, index) => <NetworkNode
          key={item.id}
          className={programPositions[index]}
          icon={item.icon}
          eyebrow={item.eyebrow}
          name={item.name}
          role={item.role}
          tone="application"
        />)}
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />跨境贸易关系</span>
        <span><i className="chain-dot chain-dot--contract" />政府采购合同</span>
        <span><i className="chain-dot chain-dot--application" />装备应用关系</span>
        <p>图中贸易记录证明相关产品进入企业供应链；除非另有物料清单或最终用途文件，不代表该批货物已被确认用于具体军方项目。</p>
      </div>
    </section>
  );
}

function CsbcPumpSupplyChainMap({
  investigation, entities, cases, shipments,
}: {
  investigation: SupplyChainInvestigation;
  entities: SupplyChainEntity[];
  cases: SupplyChainCase[];
  shipments: SupplyChainShipment[];
}) {
  const byId = new Map(entities.map((item) => [item.id, item]));
  const sulzerIndia = byId.get("ent-sulzer-pumps-india");
  const csbc = byId.get("ent-csbc-taiwan");
  const endUser = byId.get("ent-cpc-dalin-petrochemical-center");
  const upstream = [byId.get("ent-sulzer-suzhou"), byId.get("ent-wolong-nanyang")]
    .filter((item): item is SupplyChainEntity => Boolean(item));
  const productByExporter = new Map(
    shipments.map((item) => [item.exporter_name.trim().toLocaleLowerCase(), item.product]),
  );
  const delivery = shipments.find((item) => item.importer_entity_id === csbc?.id)
    || shipments.find((item) => item.destination_country === "Taiwan");
  const project = cases[0];

  return (
    <section className="supply-chain-visual supply-chain-visual--pump">
      <header>
        <div>
          <span>SUPPLY CHAIN MAP</span>
          <h3>供应链条展示</h3>
        </div>
        <small>{investigation.name} · {investigation.completeness_level} · 证据完整度 {investigation.completeness_score}%</small>
      </header>
      <div className="pump-chain-map">
        <div className="pump-chain-zone pump-chain-zone--upstream">
          <div className="pump-chain-zone-title"><Factory size={17} /><span>中国上游供应端</span></div>
          <div className="pump-chain-suppliers">
            {upstream.map((entity) => (
              <article key={entity.id} className="pump-chain-node pump-chain-node--supplier">
                <Factory size={18} />
                <div>
                  <strong>{entityDisplayName(entity)}</strong>
                  <small>{productByExporter.get(entity.name.trim().toLocaleLowerCase()) || entity.defense_roles?.[0] || "泵组部件及配套产品"}</small>
                </div>
              </article>
            ))}
          </div>
        </div>

        <FlowArrow label="部件供应" />

        <article className="pump-chain-node pump-chain-node--integrator">
          <Building2 size={20} />
          <div>
            <span>印度集成与交付节点</span>
            <strong>{sulzerIndia?.name || "Sulzer Pumps India"}</strong>
            <small>{sulzerIndia?.defense_roles?.join(" · ") || "接收中国产泵体、电机等部件，完成泵组集成与项目交付"}</small>
          </div>
        </article>

        <FlowArrow label="泵组交付" />

        <article className="pump-chain-node pump-chain-node--epc">
          <ShipWheel size={20} />
          <div>
            <span>中国台湾EPC承接端</span>
            <strong>{csbc?.name || "CSBC Corporation, Taiwan"}</strong>
            <small>{delivery?.product || "接收石化工艺泵组并承担项目工程实施"}</small>
          </div>
        </article>

        <FlowArrow label="项目安装应用" />

        <div className="pump-chain-zone pump-chain-zone--application">
          <div className="pump-chain-zone-title"><Landmark size={17} /><span>中国台湾应用端</span></div>
          <article className="pump-chain-node pump-chain-node--application">
            <Landmark size={20} />
            <div>
              <strong>{endUser?.name || "CPC Dalin Petrochemical Storage Center"}</strong>
              <small>{project?.target_program || project?.product || "台湾中油大林石化油品储运中心项目"}</small>
            </div>
          </article>
        </div>
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />中国部件输入</span>
        <span><i className="chain-dot chain-dot--contract" />泵组集成交付</span>
        <span><i className="chain-dot chain-dot--application" />EPC项目应用</span>
        <p>链条终点为台湾中油大林石化储运中心项目；台船在该链条中是EPC承接和项目实施节点，不是军用最终用户。</p>
      </div>
    </section>
  );
}

function FlowArrow({ label }: { label: string }) {
  return <div className="pump-chain-arrow" aria-label={label}><span>{label}</span><i /></div>;
}

function NetworkNode({
  className, icon: Icon, eyebrow, name, role, tone, emphasis = false,
}: {
  className: string;
  icon: typeof Factory;
  eyebrow: string;
  name: string;
  role: string;
  tone: "trade" | "contract" | "application" | "distribution" | "personnel" | "focus";
  emphasis?: boolean;
}) {
  return (
    <article className={`chain-network-node chain-network-node--${tone} ${className} ${emphasis ? "chain-network-node--emphasis" : ""}`}>
      <div className="chain-network-node-icon"><Icon size={19} /></div>
      <div className="chain-network-node-copy">
        <span>{eyebrow}</span>
        <strong>{name}</strong>
        <small>{role}</small>
      </div>
    </article>
  );
}

function entityDisplayName(entity: SupplyChainEntity) {
  return entity.country === "China" ? (entity.name_zh || entity.name) : entity.name;
}

function entityTypeLabel(type: string) {
  const labels: Record<string, string> = {
    china_exporter: "中国出口主体",
    component_supplier: "上游部件供应商",
    trading_company: "贸易协调主体",
    parent_company: "集团母公司",
    subsidiary: "集团关联企业",
    manufacturer: "制造企业",
    importer: "进口与承接主体",
    integrator: "系统集成商",
    defense_supplier: "军工供应商",
    warehouse: "仓储与分拨节点",
    terminal_shipyard: "终端船厂",
    industrial_end_user: "工业最终用户",
    military_end_user: "军事最终用户",
    government_end_user: "政府最终用户",
    government_agency: "政府机构",
    end_user: "最终用户",
  };
  return labels[type] || type.replace(/_/g, " ");
}

function tradePartyName(
  rawName: string,
  entityByName: Map<string, SupplyChainEntity>,
  entity?: SupplyChainEntity,
) {
  const matched = entity || entityByName.get(rawName.trim().toLocaleLowerCase());
  return matched ? entityDisplayName(matched) : rawName;
}

function InvestigationForm({ country, done }: { country: Direction; done: (item: SupplyChainInvestigation) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return <form className="supply-chain-form supply-chain-project-form" onSubmit={async (event) => {
    event.preventDefault();
    const item = await createSupplyChainInvestigation({ name, description, country });
    done(item);
  }}>
    <Field label="供应链名称*" value={name} set={setName} required />
    <Field label="调查方向说明" value={description} set={setDescription} />
    <button className="btn btn-primary" type="submit">创建供应链</button>
  </form>;
}

function EntityForm({ entities, country, investigationId, done }: { entities: SupplyChainEntity[]; country: Direction; investigationId: string; done: () => void }) {
  const [data, setData] = useState({ name: "", name_zh: "", entity_type: "defense_supplier", parent_id: "", aliases: "", defense_roles: "", source_url: "" });
  return <form className="supply-chain-form" onSubmit={async (event) => {
    event.preventDefault();
    await createSupplyChainEntity({ ...data, country, investigation_id: investigationId || null, parent_id: data.parent_id || null, aliases: split(data.aliases), defense_roles: split(data.defense_roles) });
    done();
  }}>
    <Field label="企业英文名称*" value={data.name} set={(name) => setData({ ...data, name })} required />
    <Field label="企业中文名称" value={data.name_zh} set={(name_zh) => setData({ ...data, name_zh })} />
    <label>主体类型<select value={data.entity_type} onChange={(event) => setData({ ...data, entity_type: event.target.value })}><option value="defense_supplier">军工供应商</option><option value="subsidiary">关联子公司</option><option value="importer">进口商</option><option value="warehouse">仓储/中间商</option></select></label>
    <label>母公司<select value={data.parent_id} onChange={(event) => setData({ ...data, parent_id: event.target.value })}><option value="">无</option>{entities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <Field label="别名（逗号分隔）" value={data.aliases} set={(aliases) => setData({ ...data, aliases })} />
    <Field label="军工角色（逗号分隔）" value={data.defense_roles} set={(defense_roles) => setData({ ...data, defense_roles })} />
    <Field label="证据网址" value={data.source_url} set={(source_url) => setData({ ...data, source_url })} />
    <button className="btn btn-primary" type="submit">保存企业</button>
  </form>;
}

function CaseForm({ entities, country, investigationId, done }: { entities: SupplyChainEntity[]; country: Direction; investigationId: string; done: () => void }) {
  const [data, setData] = useState({ title: "", procurement_agency: "", procurement_reference: "", procurement_date: "", supplier_entity_id: "", product: "", target_program: "", source_url: "", source_excerpt: "" });
  return <form className="supply-chain-form" onSubmit={async (event) => {
    event.preventDefault();
    await createSupplyChainCase({ ...data, country, investigation_id: investigationId || null, supplier_entity_id: data.supplier_entity_id || null, procurement_date: data.procurement_date || null });
    done();
  }}>
    <Field label="项目标题*" value={data.title} set={(title) => setData({ ...data, title })} required />
    <Field label="采购机关" value={data.procurement_agency} set={(procurement_agency) => setData({ ...data, procurement_agency })} />
    <Field label="合同/公告编号" value={data.procurement_reference} set={(procurement_reference) => setData({ ...data, procurement_reference })} />
    <Field label="采购日期" type="date" value={data.procurement_date} set={(procurement_date) => setData({ ...data, procurement_date })} />
    <label>采购供应商<select value={data.supplier_entity_id} onChange={(event) => setData({ ...data, supplier_entity_id: event.target.value })}><option value="">待关联</option>{entities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <Field label="采购产品" value={data.product} set={(product) => setData({ ...data, product })} />
    <Field label="军用项目/用途" value={data.target_program} set={(target_program) => setData({ ...data, target_program })} />
    <Field label="公告网址" value={data.source_url} set={(source_url) => setData({ ...data, source_url })} />
    <label className="wide">原文证据摘录<textarea value={data.source_excerpt} onChange={(event) => setData({ ...data, source_excerpt: event.target.value })} /></label>
    <button className="btn btn-primary" type="submit">保存项目</button>
  </form>;
}

function ShipmentForm({ entities, country, investigationId, done }: { entities: SupplyChainEntity[]; country: Direction; investigationId: string; done: () => void }) {
  const [data, setData] = useState({ exporter_name: "", importer_name: "", importer_entity_id: "", product: "", hs_code: "", shipment_date: "", weight_kg: "", bill_no: "", source_name: "", source_url: "" });
  return <form className="supply-chain-form" onSubmit={async (event) => {
    event.preventDefault();
    await createSupplyChainShipment({ ...data, destination_country: country, investigation_id: investigationId || null, importer_entity_id: data.importer_entity_id || null, shipment_date: data.shipment_date || null, weight_kg: data.weight_kg ? Number(data.weight_kg) : null });
    done();
  }}>
    <Field label="中国出口商*" value={data.exporter_name} set={(exporter_name) => setData({ ...data, exporter_name })} required />
    <Field label="美国进口商*" value={data.importer_name} set={(importer_name) => setData({ ...data, importer_name })} required />
    <label>关联企业<select value={data.importer_entity_id} onChange={(event) => { const id = event.target.value; setData({ ...data, importer_entity_id: id, importer_name: entities.find((item) => item.id === id)?.name || data.importer_name }); }}><option value="">待关联</option>{entities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <Field label="货物名称*" value={data.product} set={(product) => setData({ ...data, product })} required />
    <Field label="HS编码" value={data.hs_code} set={(hs_code) => setData({ ...data, hs_code })} />
    <Field label="运输日期" type="date" value={data.shipment_date} set={(shipment_date) => setData({ ...data, shipment_date })} />
    <Field label="重量（kg）" type="number" value={data.weight_kg} set={(weight_kg) => setData({ ...data, weight_kg })} />
    <Field label="提单号" value={data.bill_no} set={(bill_no) => setData({ ...data, bill_no })} />
    <Field label="数据来源" value={data.source_name} set={(source_name) => setData({ ...data, source_name })} />
    <Field label="原始记录网址" value={data.source_url} set={(source_url) => setData({ ...data, source_url })} />
    <button className="btn btn-primary" type="submit">保存记录</button>
  </form>;
}

function split(value: string) { return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean); }
function dateText(value: string | null) {
  return value ? new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", dateStyle: "medium" }).format(new Date(value)) : "日期待补充";
}
