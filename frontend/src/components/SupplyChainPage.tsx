import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Anchor, BatteryCharging, Building2, Crosshair, ExternalLink, Factory,
  FileSearch, FlaskConical, Landmark, Link2, Network, PackageSearch, Plus,
  RadioTower, ShieldCheck, ShipWheel, Sparkles, Warehouse,
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
  const loadToken = useRef(0);

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
    fetchSupplyChainInvestigations(direction)
      .then((rows) => {
        setInvestigations(rows);
        setInvestigationId((current) => (
          rows.some((item) => item.id === current) ? current : (rows[0]?.id || "")
        ));
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "供应链项目加载失败"));
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
    <div className="page supply-chain-page">
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
                onClick={() => { setDirection(item.id); setInvestigationId(""); setForm(null); }}
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
            <Link2 size={16} />构建证据链
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void generate()} disabled={busy}>
            <Sparkles size={16} />生成报告
          </button>
        </div>
      </div>
      {message && <div className="supply-chain-message">{message}</div>}

      <div className="supply-chain-project-bar">
        <span className="supply-chain-project-label">当前供应链</span>
        <div className="supply-chain-projects" role="group" aria-label="供应链项目">
          {investigations.map((item) => (
            <button
              key={item.id}
              type="button"
              className={investigationId === item.id ? "active" : ""}
              onClick={() => setInvestigationId(item.id)}
              title={item.description || item.name}
            >
              {item.name}
            </button>
          ))}
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

      <nav className="supply-chain-tabs">
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
                <div className="supply-chain-finding-grid">
                  <article>
                    <strong>军工项目与供应关系</strong>
                    {procurementFindings.length ? (
                      <ul>{procurementFindings.map((item) => <li key={item}>{item}</li>)}</ul>
                    ) : <p>尚未录入军方采购或合作项目。</p>}
                  </article>
                  <article>
                    <strong>跨境贸易产品与流向</strong>
                    {tradeFindings.length ? (
                      <ul>{tradeFindings.map((item) => <li key={item}>{item}</li>)}</ul>
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
                {reports.slice(0, 4).map((report) => (
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
        investigationId === "inv-us-ultralife-battery"
          ? <BatterySupplyChainMap />
          : investigationId === "inv-us-gadolinium-oxide"
            ? <GadoliniumSupplyChainMap />
            : investigationId === "inv-india-csbc-pump-chain"
              ? <IndiaShipComponentsMap />
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
          <h3>涉印关键船配件供应链图谱</h3>
        </div>
        <small>中国产部件 → 印度泵组集成 → 台船项目交付与终端关联</small>
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
          <div><strong>台船终端与项目关联</strong><small>船舶交付、无人艇及待核军工线索</small></div>
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
        <span className="chain-relation-label india-label--application">终端关联</span>
        <span className="chain-relation-label india-label--review">线索待核</span>

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
          eyebrow="终端船舶企业"
          name="CSBC Corporation, Taiwan"
          role="接收至少6批次、11台/套离心泵组"
          tone="distribution"
        />
        <NetworkNode
          className="india-node--manta"
          icon={RadioTower}
          eyebrow="军用级无人水面载具"
          name="Endeavor Manta"
          role="终端场景高度相关 · 具体安装尚未证实"
          tone="application"
        />
        <NetworkNode
          className="india-node--lockheed"
          icon={ShieldCheck}
          eyebrow="潜舰战斗系统关联线索"
          name="Lockheed Martin Corporation"
          role="高概率候选主体 · 需合同或设备资料终核"
          tone="contract"
        />
      </div>
      <div className="supply-chain-visual-note">
        <span><i className="chain-dot chain-dot--trade" />中国产部件</span>
        <span><i className="chain-dot chain-dot--personnel" />集团控制关系</span>
        <span><i className="chain-dot chain-dot--distribution" />印度集成交付</span>
        <span><i className="chain-dot chain-dot--application" />终端项目关联</span>
        <p>贸易链路已经核实；具体泵组安装船号和军用项目用途仍需以装箱单、铭牌及验收文件确认。</p>
      </div>
    </section>
  );
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
