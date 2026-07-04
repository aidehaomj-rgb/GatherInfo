// GatherInfo 推介 PPT - Full 17 slides
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "GatherInfo - global trade intelligence platform";
pres.author = "GatherInfo";

const C = {
  bgDeep:    "0B1B34",
  bgPanel:   "102544",
  bgCard:    "18324F",
  ink:       "F4F6FB",
  inkSoft:   "B8C2D9",
  inkDim:    "8C97B0",
  line:      "28466E",
  primary:   "2F6BFF",
  primaryDk: "1E4ECF",
  ice:       "9CC2FF",
  amber:     "F5B544",
  amberDk:   "C98A1A",
  success:   "2EC27E",
  warn:      "E25C5C",
  cream:     "F4ECD8",
  surface:   "F7F9FC",
  surfaceTxt:"0B1B34",
};

const FONT_H = "Calibri";
const FONT_B = "Calibri";
const FONT_M = "Consolas";

const makeShadow = () => ({ type: "outer", blur: 10, offset: 3, angle: 90, color: "000000", opacity: 0.18 });

const TOTAL = 17;

function addPageHeader(slide, idx, sectionLabel) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 0.5,
    fill: { color: C.bgDeep }, line: { color: C.bgDeep, width: 0 }
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 0.18, w: 0.16, h: 0.16,
    fill: { color: C.amber }, line: { color: C.amber, width: 0 }
  });
  slide.addText("GatherInfo", {
    x: 0.72, y: 0.06, w: 3, h: 0.4,
    fontSize: 12, fontFace: FONT_H, color: C.ink, bold: true, margin: 0, valign: "middle"
  });
  if (sectionLabel) {
    slide.addText(sectionLabel, {
      x: 4.5, y: 0.06, w: 4.5, h: 0.4,
      fontSize: 10, fontFace: FONT_B, color: C.inkSoft, align: "center", margin: 0, valign: "middle",
      charSpacing: 4
    });
  }
  slide.addText(idx + " / " + TOTAL, {
    x: 11.5, y: 0.06, w: 1.3, h: 0.4,
    fontSize: 10, fontFace: FONT_B, color: C.inkDim, align: "right", margin: 0, valign: "middle"
  });
  slide.addShape(pres.shapes.LINE, {
    x: 0.5, y: 7.2, w: 12.3, h: 0,
    line: { color: C.line, width: 0.75 }
  });
  slide.addText("GatherInfo . global trade intelligence platform", {
    x: 0.5, y: 7.22, w: 8, h: 0.28,
    fontSize: 9, fontFace: FONT_B, color: C.inkDim, margin: 0, valign: "middle"
  });
  slide.addText("topic-driven . multi-source . smart reports", {
    x: 9, y: 7.22, w: 3.8, h: 0.28,
    fontSize: 9, fontFace: FONT_B, color: C.inkDim, align: "right", margin: 0, valign: "middle"
  });
}

function darkSlide() {
  const s = pres.addSlide();
  s.background = { color: C.bgDeep };
  return s;
}

// =============================================================
// SLIDE 1: Cover
// =============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.bgDeep };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.3, h: 7.5, fill: { color: C.bgDeep }, line: { width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 8.5, y: 0, w: 4.8, h: 7.5, fill: { color: C.bgPanel }, line: { width: 0 } });
  for (let i = 0; i < 6; i++) for (let j = 0; j < 4; j++) {
    s.addShape(pres.shapes.OVAL, {
      x: 8.9 + i * 0.7, y: 0.8 + j * 0.7, w: 0.08, h: 0.08,
      fill: { color: C.line }, line: { width: 0 }
    });
  }
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 2.4, w: 0.12, h: 1.5, fill: { color: C.amber }, line: { width: 0 } });
  s.addText("GatherInfo", { x: 0.95, y: 2.25, w: 7, h: 0.9, fontSize: 56, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Global Trade Intelligence Collection & Monitoring Platform", { x: 0.95, y: 3.15, w: 7, h: 0.6, fontSize: 20, fontFace: FONT_H, color: C.ice, margin: 0 });
  s.addText("Topic-driven  .  multi-source  .  tagged persistence  .  AI reports", { x: 0.95, y: 3.85, w: 7, h: 0.4, fontSize: 14, fontFace: FONT_B, color: C.inkSoft, italic: true, margin: 0, charSpacing: 2 });
  const stats = [
    { v: "92", l: "pre-configured sources" },
    { v: "9", l: "collection channels" },
    { v: "258", l: "test cases" },
  ];
  stats.forEach((st, i) => {
    const x = 0.95 + i * 2.2;
    s.addText(st.v, { x, y: 4.9, w: 1.8, h: 0.6, fontSize: 32, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(st.l, { x, y: 5.5, w: 1.8, h: 0.4, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  s.addText("BUILT FOR", { x: 8.9, y: 2.0, w: 4, h: 0.3, fontSize: 10, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 6, margin: 0 });
  s.addText("Cross-border trade analysts", { x: 8.9, y: 2.3, w: 4.2, h: 0.5, fontSize: 20, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Customs compliance teams", { x: 8.9, y: 2.8, w: 4.2, h: 0.5, fontSize: 20, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Market intelligence researchers", { x: 8.9, y: 3.3, w: 4.2, h: 0.5, fontSize: 20, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addShape(pres.shapes.LINE, { x: 8.9, y: 4.2, w: 3.8, h: 0, line: { color: C.line, width: 1 } });
  s.addText("PRODUCT BRIEFING", { x: 8.9, y: 4.35, w: 4, h: 0.3, fontSize: 9, fontFace: FONT_B, color: C.inkDim, charSpacing: 4, margin: 0 });
  s.addText("v1.0 . 2026", { x: 8.9, y: 4.7, w: 4, h: 0.3, fontSize: 11, fontFace: FONT_B, color: C.ink, margin: 0 });
  s.addText("React 18  .  TypeScript  .  FastAPI  .  SQLAlchemy 2.0  .  SQLite FTS5  .  APScheduler", {
    x: 0.5, y: 6.95, w: 12.3, h: 0.4, fontSize: 10, fontFace: FONT_B, color: C.inkDim, align: "center", margin: 0, charSpacing: 2
  });
}

// =============================================================
// SLIDE 2: Pain points
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 2, "01  .  why GatherInfo");
  s.addText("In an age of information overload, intelligence work is held back by tools", {
    x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 28, fontFace: FONT_H, color: C.ink, bold: true, margin: 0
  });
  s.addText("Analysts spend 70% of their time on data plumbing - not on analysis.", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  const pains = [
    { t: "Fragmented sources", d: "WTO, customs, ministries, industry media scattered across hundreds of sites - manual patrol is slow and error-prone", i: "01" },
    { t: "Fragile crawlers", d: "One bespoke scraper per site, broken by the next HTML change - maintenance cost dwarfs collection value", i: "02" },
    { t: "Hard to reuse data", d: "Excel files everywhere, no cross-topic aggregation, no time-series or correlation analysis", i: "03" },
    { t: "Slow report output", d: "Weekly manual roll-up then writing then delivering - the decision window shrinks to the last mile", i: "04" },
  ];
  pains.forEach((p, i) => {
    const x = 0.5 + i * 3.15, y = 2.4;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.95, h: 3.2, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.95, h: 0.08, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(p.i, { x: x + 0.2, y: y + 0.25, w: 1, h: 0.5, fontSize: 28, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(p.t, { x: x + 0.2, y: y + 0.95, w: 2.6, h: 0.5, fontSize: 18, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(p.d, { x: x + 0.2, y: y + 1.55, w: 2.6, h: 1.5, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0, valign: "top", paraSpaceAfter: 4 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 6.0, w: 12.3, h: 0.95, fill: { color: C.bgPanel }, line: { color: C.primary, width: 0.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 6.0, w: 0.12, h: 0.95, fill: { color: C.primary }, line: { width: 0 } });
  s.addText("GatherInfo's answer", { x: 0.85, y: 6.1, w: 3, h: 0.4, fontSize: 13, fontFace: FONT_H, color: C.ice, bold: true, margin: 0 });
  s.addText("Wire 9 collection channels, 92 pre-built sources, a tagging system, and AI report orchestration into a single closed loop - analysts only define the topic, the rest is automated.", {
    x: 0.85, y: 6.45, w: 11.7, h: 0.5, fontSize: 13, fontFace: FONT_B, color: C.ink, margin: 0
  });
}

// =============================================================
// SLIDE 3: Core loop
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 3, "02  .  core closed loop");
  s.addText("One pipeline, from keyword to deliverable report", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("ONE PIPELINE  .  SIX STAGES", { x: 0.5, y: 1.5, w: 12.3, h: 0.4, fontSize: 10, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 6, margin: 0 });
  const stages = [
    { n: "01", t: "Define topic", d: "Keyword templates + sources + window + cron schedule", k: "Topic" },
    { n: "02", t: "Scheduled / manual collect", d: "9 connectors run in parallel, unified batch_id tracking", k: "Collect" },
    { n: "03", t: "Dedupe and persist", d: "URL hash + content fingerprint double-dedupe, FTS5 indexed", k: "Persist" },
    { n: "04", t: "Auto-tag", d: "auto_tag_rules keyword rules + namespace tag system", k: "Tag" },
    { n: "05", t: "Smart report", d: "LLM call -> Markdown -> DOCX / PDF / HTML export", k: "Report" },
    { n: "06", t: "Export and deliver", d: "Webhook / Email + CSV / JSON / XLSX data export", k: "Deliver" },
  ];
  stages.forEach((st, i) => {
    const x = 0.5 + i * 2.13, y = 2.3;
    s.addText(st.n, { x, y, w: 2, h: 0.6, fontSize: 32, fontFace: FONT_H, color: C.primary, bold: true, margin: 0 });
    s.addText(st.t, { x, y: 0.7 + 2.3, w: 2, h: 0.5, fontSize: 15, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(st.d, { x, y: 1.2 + 2.3, w: 2, h: 1.0, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.4 + 2.3, w: 1.4, h: 0.3, fill: { color: C.bgPanel }, line: { color: C.line, width: 0.5 } });
    s.addText(st.k, { x, y: 2.4 + 2.3, w: 1.4, h: 0.3, fontSize: 9, fontFace: FONT_M, color: C.ice, align: "center", valign: "middle", margin: 0 });
    if (i < 5) {
      s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + 1.85, y: 2.55, w: 0.18, h: 0.22, fill: { color: C.amber }, line: { width: 0 }, rotate: 90 });
    }
  });
  const sup = [
    { t: "Observable", d: "Batch view + live active-task tracking" },
    { t: "Extensible", d: "12+ adapters, new source in ~30 lines" },
    { t: "Auditable", d: "Full run + error_log retention, replayable" },
  ];
  sup.forEach((p, i) => {
    const x = 0.5 + i * 4.2, y = 5.8;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 1.2, fill: { color: C.bgPanel }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.3, w: 0.3, h: 0.3, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(p.t, { x: x + 0.6, y: y + 0.2, w: 3, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(p.d, { x: x + 0.6, y: y + 0.65, w: 3.4, h: 0.5, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
}

// =============================================================
// SLIDE 4: Platform overview quadrants
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 4, "03  .  platform overview");
  s.addText("GatherInfo at a glance", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("PLATFORM AT A GLANCE", { x: 0.5, y: 1.5, w: 12.3, h: 0.4, fontSize: 10, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 6, margin: 0 });
  s.addShape(pres.shapes.OVAL, { x: 5.85, y: 3.0, w: 1.6, h: 1.6, fill: { color: C.bgDeep }, line: { color: C.amber, width: 2 } });
  s.addText("Gather\nInfo", { x: 5.85, y: 3.0, w: 1.6, h: 1.6, fontSize: 18, fontFace: FONT_H, color: C.amber, bold: true, align: "center", valign: "middle", margin: 0 });
  const quads = [
    { x: 0.5, y: 2.0, t: "Ingestion Layer", items: ["9 connectors", "92 pre-built sources", "Cron + manual trigger", "Batch tracking"] },
    { x: 7.9, y: 2.0, t: "Storage Layer", items: ["SQLite WAL", "FTS5 full-text search", "URL / content dedupe", "Auto schema migration"] },
    { x: 0.5, y: 4.6, t: "Intelligence Layer", items: ["Multi-LLM support", "Auto summary / translate", "Batch report generation", "DOCX / PDF export"] },
    { x: 7.9, y: 4.6, t: "Application Layer", items: ["Dark theme UI", "11 main views", "25 + 6 shared components", "Dev Dashboard"] },
  ];
  quads.forEach((q) => {
    s.addShape(pres.shapes.RECTANGLE, { x: q.x, y: q.y, w: 4.9, h: 2.4, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: q.x, y: q.y, w: 0.1, h: 2.4, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(q.t, { x: q.x + 0.25, y: q.y + 0.15, w: 4.5, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(q.items.map((it, idx) => ({ text: it, options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: idx < q.items.length - 1 } })), {
      x: q.x + 0.3, y: q.y + 0.6, w: 4.5, h: 1.7, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 4, margin: 0
    });
  });
  s.addShape(pres.shapes.LINE, { x: 5.4, y: 3.7, w: 0.45, h: 0, line: { color: C.amber, width: 1.5 } });
  s.addShape(pres.shapes.LINE, { x: 7.45, y: 3.7, w: 0.45, h: 0, line: { color: C.amber, width: 1.5 } });
}

// =============================================================
// SLIDE 5: Tech stack
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 5, "04  .  tech architecture");
  s.addText("Separated frontend/backend, modular, extensible", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 28, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("TECH STACK", { x: 0.5, y: 1.5, w: 12.3, h: 0.4, fontSize: 10, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 6, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 2.2, w: 6.0, h: 4.7, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 2.2, w: 6.0, h: 0.5, fill: { color: C.primary }, line: { width: 0 } });
  s.addText("Frontend", { x: 0.7, y: 2.2, w: 5, h: 0.5, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, valign: "middle", margin: 0 });
  const fe = [
    { k: "Build", v: "Vite (Rolldown) + @vitejs/plugin-react" },
    { k: "Framework", v: "React 18 + TypeScript" },
    { k: "Charts", v: "ECharts (dashboard, trend, distribution)" },
    { k: "Icons", v: "Lucide React (lightweight vector)" },
    { k: "Routing", v: "11 views, ViewId state-driven" },
    { k: "Hooks", v: "useApi . useDebounce . usePagination" },
    { k: "Design", v: "Dark theme + 4px scale + 8px radius" },
  ];
  fe.forEach((it, i) => {
    const y = 2.85 + i * 0.55;
    s.addText(it.k, { x: 0.7, y, w: 1.2, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.ice, bold: true, margin: 0 });
    s.addText(it.v, { x: 2.0, y, w: 4.4, h: 0.4, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 2.2, w: 6.0, h: 4.7, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 2.2, w: 6.0, h: 0.5, fill: { color: C.amber }, line: { width: 0 } });
  s.addText("Backend", { x: 7.0, y: 2.2, w: 5, h: 0.5, fontSize: 14, fontFace: FONT_H, color: C.bgDeep, bold: true, valign: "middle", margin: 0 });
  const be = [
    { k: "Framework", v: "FastAPI (create_app factory + lifespan)" },
    { k: "ORM", v: "SQLAlchemy 2.0 + Pydantic v2" },
    { k: "DB", v: "SQLite WAL + FTS5 full-text index" },
    { k: "Collection", v: "httpx async + BeautifulSoup4 parsing" },
    { k: "Scheduler", v: "APScheduler (Cron + interval)" },
    { k: "AI", v: "Multi-LLM: OpenAI / Ollama / custom" },
    { k: "Export", v: "WeasyPrint (PDF) . Pandoc (DOCX)" },
  ];
  be.forEach((it, i) => {
    const y = 2.85 + i * 0.55;
    s.addText(it.k, { x: 7.0, y, w: 1.2, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(it.v, { x: 8.3, y, w: 4.4, h: 0.4, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  s.addText("Scale: backend 45 files / ~7000 LOC . frontend 25 + 6 shared + 3 hooks / ~5400 LOC . 50+ API endpoints . 258 test cases", {
    x: 0.5, y: 6.95, w: 12.3, h: 0.3, fontSize: 10, fontFace: FONT_B, color: C.inkDim, align: "center", margin: 0
  });
}

// =============================================================
// SLIDE 6: 9 collection channels
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 6, "05  .  9 collection channels");
  s.addText("9 connectors, one unified contract", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("BaseCollector + ConnectorRegistry plug-in model", { x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0 });
  const chans = [
    { code: "official",   n: "01", t: "Official API",  d: "WTO ePing, EUR-Lex, China Customs, MOFCOM, UN Comtrade" },
    { code: "rss",        n: "02", t: "RSS / Atom",    d: "Universal feed reader with auto category & language detection" },
    { code: "web_scrape", n: "03", t: "Web Scrape",    d: "CSS selector + BeautifulSoup4, robust to layout changes" },
    { code: "api_search", n: "04", t: "Web Search",    d: "Tavily (default) + Baidu / Bing / 360 delegated dispatch" },
    { code: "json_api",   n: "05", t: "JSON API",      d: "Generic JSON adapter: NewsAPI, Comtrade, Trading Economics" },
    { code: "commercial", n: "06", t: "Commercial DB", d: "Authorized vendor data (Inoreader, Feedly) plug-in" },
    { code: "social",     n: "07", t: "Social Media",  d: "Targeted scrape + API for Twitter / LinkedIn monitoring" },
    { code: "deepweb",    n: "08", t: "Deep Web",      d: "Onion / dark-net sources with safety guard" },
    { code: "manual",     n: "09", t: "Manual Entry",  d: "Operator-curated items for human intelligence input" },
  ];
  chans.forEach((c, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * 4.2, y = 2.3 + row * 1.55;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 1.4, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.08, h: 1.4, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(c.n, { x: x + 0.2, y: y + 0.1, w: 0.6, h: 0.35, fontSize: 16, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(c.t, { x: x + 0.75, y: y + 0.1, w: 3.2, h: 0.35, fontSize: 15, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(c.code, { x: x + 0.2, y: y + 0.5, w: 3.7, h: 0.25, fontSize: 9, fontFace: FONT_M, color: C.ice, margin: 0 });
    s.addText(c.d, { x: x + 0.2, y: y + 0.75, w: 3.7, h: 0.65, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  s.addText("All connectors implement BaseCollector.fetch(keywords) -> CollectResult - new source in ~30 lines.", {
    x: 0.5, y: 6.95, w: 12.3, h: 0.3, fontSize: 10, fontFace: FONT_B, color: C.inkDim, align: "center", margin: 0, italic: true
  });
}

// =============================================================
// SLIDE 7: 92 pre-built sources
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 7, "06  .  92 pre-built sources");
  s.addText("92 sources, 83 ready out of the box", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Coverage: 30+ economies, 8 international organizations, 7 RSS categories", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Big stat row
  const bigStats = [
    { v: "92", l: "Total sources", c: C.amber },
    { v: "83", l: "Ready now", c: C.success },
    { v: "9",  l: "Need API key", c: C.warn },
  ];
  bigStats.forEach((st, i) => {
    const x = 0.5 + i * 2.2, y = 2.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.0, h: 1.5, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addText(st.v, { x, y: y + 0.15, w: 2.0, h: 0.85, fontSize: 60, fontFace: FONT_H, color: st.c, bold: true, align: "center", margin: 0 });
    s.addText(st.l, { x, y: y + 1.05, w: 2.0, h: 0.35, fontSize: 12, fontFace: FONT_B, color: C.inkSoft, align: "center", margin: 0 });
  });
  // Source categories list
  const cats = [
    { t: "Intl. orgs & agreements", d: "WTO . UNCTAD . OECD . IMF . World Bank . IISD . ADB . ASEAN . PIIE . CSIS . GTA . EAEU" },
    { t: "Major economies (customs & trade)", d: "US (CBP / USTR / USITC / BIS / OFAC) . EU . UK . Canada . Australia . NZ . Singapore . HK . JP METI . KR" },
    { t: "Emerging markets (customs)", d: "India DGFT . Brazil MDIC . South Africa SARS . Turkey . Vietnam . Indonesia . Mexico . Thailand . Philippines . Malaysia . Chile . Argentina . Nigeria . Kenya . Egypt . Colombia . Peru . Pakistan . Bangladesh . Sri Lanka" },
    { t: "China regulators", d: "General Administration of Customs . MOFCOM . Free Trade Zone Service Network" },
  ];
  cats.forEach((c, i) => {
    const y = 4.0 + i * 0.7;
    s.addShape(pres.shapes.RECTANGLE, { x: 4.3, y, w: 0.08, h: 0.6, fill: { color: C.primary }, line: { width: 0 } });
    s.addText(c.t, { x: 4.5, y, w: 3.0, h: 0.6, fontSize: 12, fontFace: FONT_H, color: C.ice, bold: true, margin: 0, valign: "middle" });
    s.addText(c.d, { x: 7.6, y, w: 5.2, h: 0.6, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0, valign: "middle" });
  });
}

// =============================================================
// SLIDE 8: Topic management
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 8, "07  .  topic management");
  s.addText("Define a topic once, harvest forever", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Topic = keywords + sources + window + cron + auto-tag + auto-report", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Left: features
  const feats = [
    { t: "Keyword templates", d: "Pre-built templates for common themes (sanctions, tariffs, customs notices)" },
    { t: "Multi-source binding", d: "One topic -> N sources, batch_id tracks all runs together" },
    { t: "Cron schedule", d: "Standard cron expressions, APScheduler drives execution" },
    { t: "Collect window", d: "Limit by publish time (e.g. last 7 days) to keep data fresh" },
    { t: "Auto-tag rules", d: "Rule engine tags new items by keyword match" },
    { t: "Auto-report", d: "After collection, fire-and-forget LLM report generation" },
  ];
  feats.forEach((f, i) => {
    const x = 0.5 + (i % 2) * 4.2, y = 2.3 + Math.floor(i / 2) * 1.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 1.05, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.08, h: 1.05, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(f.t, { x: x + 0.2, y: y + 0.1, w: 3.8, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(f.d, { x: x + 0.2, y: y + 0.5, w: 3.8, h: 0.5, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  // Right: example topic card
  s.addShape(pres.shapes.RECTANGLE, { x: 9.0, y: 2.3, w: 3.8, h: 4.5, fill: { color: C.bgPanel }, line: { color: C.primary, width: 0.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 9.0, y: 2.3, w: 3.8, h: 0.5, fill: { color: C.primary }, line: { width: 0 } });
  s.addText("EXAMPLE TOPIC", { x: 9.15, y: 2.3, w: 3.6, h: 0.5, fontSize: 11, fontFace: FONT_H, color: C.ink, bold: true, valign: "middle", charSpacing: 4, margin: 0 });
  s.addText("US-China Tariff Tracker", { x: 9.15, y: 2.9, w: 3.6, h: 0.5, fontSize: 17, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  const ex = [
    { k: "Keywords",  v: '"tariff", "Section 301", "USTR"' },
    { k: "Sources",   v: "USTR, USITC, MOFCOM, GTA" },
    { k: "Window",    v: "last 7 days" },
    { k: "Schedule",  v: "0 8 * * * (daily 8am)" },
    { k: "Auto-tag",  v: "3 rules active" },
    { k: "Auto-report", v: "on (weekly summary)" },
  ];
  ex.forEach((e, i) => {
    const y = 3.5 + i * 0.5;
    s.addText(e.k, { x: 9.15, y, w: 1.3, h: 0.4, fontSize: 10, fontFace: FONT_H, color: C.ice, bold: true, margin: 0 });
    s.addText(e.v, { x: 10.5, y, w: 2.2, h: 0.4, fontSize: 10, fontFace: FONT_M, color: C.ink, margin: 0 });
  });
}

// =============================================================
// SLIDE 9: Smart dashboard
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 9, "08  .  smart dashboard");
  s.addText("All your intelligence, in one screen", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("ECharts-powered: trend . distribution . top tags . quick actions", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Mock dashboard grid
  // Top KPIs
  const kpis = [
    { v: "12,847", l: "Total items", c: C.amber },
    { v: "27",     l: "Active topics", c: C.ice },
    { v: "92",     l: "Active sources", c: C.success },
    { v: "98.2%",  l: "Success rate (7d)", c: C.primary },
  ];
  kpis.forEach((k, i) => {
    const x = 0.5 + i * 3.15, y = 2.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.95, h: 1.1, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addText(k.v, { x, y: y + 0.1, w: 2.95, h: 0.55, fontSize: 28, fontFace: FONT_H, color: k.c, bold: true, align: "center", margin: 0 });
    s.addText(k.l, { x, y: y + 0.7, w: 2.95, h: 0.35, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, align: "center", margin: 0 });
  });
  // Chart cards
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 3.6, w: 7.9, h: 3.2, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("Collection trend (30 days)", { x: 0.7, y: 3.7, w: 6, h: 0.4, fontSize: 13, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addChart(pres.charts.LINE, [
    { name: "Items collected", labels: ["D-30","D-25","D-20","D-15","D-10","D-5","Now"], values: [120, 180, 240, 320, 410, 480, 530] }
  ], {
    x: 0.7, y: 4.1, w: 7.5, h: 2.6,
    chartColors: [C.amber],
    lineSize: 3, lineSmooth: true,
    showLegend: false,
    catAxisLabelColor: C.inkDim, catAxisLabelFontSize: 9,
    valAxisLabelColor: C.inkDim, valAxisLabelFontSize: 9,
    valGridLine: { color: C.line, size: 0.5 },
    catGridLine: { style: "none" },
    chartArea: { fill: { color: C.bgCard } },
  });
  // Right: top tags
  s.addShape(pres.shapes.RECTANGLE, { x: 8.6, y: 3.6, w: 4.2, h: 3.2, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("Top tags", { x: 8.8, y: 3.7, w: 4, h: 0.4, fontSize: 13, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  const tags = [
    { t: "tariff",     n: 312, c: C.amber },
    { t: "sanctions",  n: 247, c: C.warn },
    { t: "Section301", n: 198, c: C.primary },
    { t: "antidumping",n: 156, c: C.ice },
    { t: "MOFCOM",     n: 134, c: C.success },
    { t: "EU CBAM",    n: 98,  c: C.amber },
    { t: "RCEP",       n: 87,  c: C.primary },
    { t: "WTO",        n: 76,  c: C.ice },
  ];
  tags.forEach((tg, i) => {
    const y = 4.2 + i * 0.3;
    s.addText(tg.t, { x: 8.8, y, w: 1.6, h: 0.25, fontSize: 10, fontFace: FONT_M, color: C.inkSoft, margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: 10.4, y: y + 0.07, w: Math.min(1.8, tg.n / 180), h: 0.12, fill: { color: tg.c }, line: { width: 0 } });
    s.addText(String(tg.n), { x: 12.2, y, w: 0.5, h: 0.25, fontSize: 10, fontFace: FONT_M, color: C.ink, margin: 0 });
  });
}

// =============================================================
// SLIDE 10: Items & search
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 10, "09  .  items & full-text search");
  s.addText("FTS5 full-text search across every item", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("title:keyword . content:phrase . boolean ops . sub-100ms on 100k+ items", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Left: capabilities
  const caps = [
    { t: "Faceted filters", d: "topic, source, tag, language, category, run_id, status" },
    { t: "FTS5 syntax", d: "title:tariff . content:\"anti-dumping\" . boolean AND/OR/NOT" },
    { t: "Full history", d: "Pagination, batch select, batch delete, item detail modal" },
    { t: "Export", d: "CSV . JSON . XLSX - filtered subsets or full match" },
  ];
  caps.forEach((c, i) => {
    const y = 2.3 + i * 0.95;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 6.5, h: 0.85, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.25, w: 0.35, h: 0.35, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(String(i + 1), { x: 0.7, y: y + 0.27, w: 0.35, h: 0.3, fontSize: 11, fontFace: FONT_H, color: C.bgDeep, bold: true, align: "center", margin: 0 });
    s.addText(c.t, { x: 1.2, y: y + 0.05, w: 5.5, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(c.d, { x: 1.2, y: y + 0.45, w: 5.7, h: 0.4, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  // Right: search bar mock + result
  s.addShape(pres.shapes.RECTANGLE, { x: 7.2, y: 2.3, w: 5.6, h: 4.5, fill: { color: C.bgPanel }, line: { color: C.line, width: 0.5 } });
  s.addText("LIVE PREVIEW", { x: 7.4, y: 2.4, w: 5, h: 0.3, fontSize: 9, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 7.4, y: 2.75, w: 5.2, h: 0.5, fill: { color: C.bgDeep }, line: { color: C.amber, width: 0.5 } });
  s.addText("title:tariff AND source:USTR", { x: 7.55, y: 2.75, w: 5.0, h: 0.5, fontSize: 12, fontFace: FONT_M, color: C.ink, valign: "middle", margin: 0 });
  s.addText("34 results . 18ms", { x: 7.4, y: 3.3, w: 5, h: 0.3, fontSize: 10, fontFace: FONT_B, color: C.inkDim, margin: 0 });
  const res = [
    { t: "USTR Final Tariff List - Section 301 Update", s: "USTR . 2026-05-28 . EN" },
    { t: "Public Hearing on Proposed Tariff Adjustments", s: "USTR . 2026-05-22 . EN" },
    { t: "Tariff Exclusion Process - Q2 Review", s: "USTR . 2026-05-15 . EN" },
    { t: "USTR Announces New Tariff Investigation", s: "USTR . 2026-05-10 . EN" },
  ];
  res.forEach((r, i) => {
    const y = 3.7 + i * 0.65;
    s.addShape(pres.shapes.RECTANGLE, { x: 7.4, y, w: 5.2, h: 0.55, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 7.4, y, w: 0.06, h: 0.55, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(r.t, { x: 7.55, y: y + 0.05, w: 5.0, h: 0.3, fontSize: 11, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(r.s, { x: 7.55, y: y + 0.32, w: 5.0, h: 0.22, fontSize: 9, fontFace: FONT_M, color: C.inkDim, margin: 0 });
  });
}

// =============================================================
// SLIDE 11: Tag system
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 11, "10  .  tag system");
  s.addText("Turn raw items into a queryable knowledge graph", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Namespace + value + color, M:N relation to items, mergeable", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Left side: namespaces list
  s.addText("NAMESPACES", { x: 0.5, y: 2.3, w: 6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const ns = [
    { ns: "policy",  t: "tariff | sanctions | anti-dumping | safeguard" },
    { ns: "region",  t: "US | EU | CN | ASEAN | RCEP | CPTPP" },
    { ns: "sector",  t: "semiconductor | EV | steel | agriculture | pharma" },
    { ns: "source",  t: "official | industry | academic | news" },
    { ns: "action",  t: "monitor | alert | report | archived" },
  ];
  ns.forEach((n, i) => {
    const y = 2.7 + i * 0.65;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 6.3, h: 0.55, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 1.2, h: 0.55, fill: { color: C.bgPanel }, line: { width: 0 } });
    s.addText(n.ns, { x: 0.5, y, w: 1.2, h: 0.55, fontSize: 11, fontFace: FONT_M, color: C.ice, bold: true, align: "center", valign: "middle", margin: 0 });
    s.addText(n.t, { x: 1.85, y, w: 4.85, h: 0.55, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, valign: "middle", margin: 0 });
  });
  // Right side: tag cloud + features
  s.addText("TAG CLOUD", { x: 7.1, y: 2.3, w: 6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 7.1, y: 2.7, w: 5.7, h: 2.6, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  const cloud = [
    { t: "tariff", s: 22, c: C.amber },
    { t: "Section301", s: 18, c: C.primary },
    { t: "sanctions", s: 16, c: C.warn },
    { t: "EU", s: 14, c: C.ice },
    { t: "MOFCOM", s: 14, c: C.ice },
    { t: "CBAM", s: 12, c: C.success },
    { t: "anti-dumping", s: 12, c: C.amber },
    { t: "semiconductor", s: 11, c: C.primary },
    { t: "EV", s: 10, c: C.warn },
    { t: "WTO", s: 9, c: C.ice },
    { t: "RCEP", s: 9, c: C.success },
    { t: "safeguard", s: 8, c: C.amber },
    { t: "pharma", s: 9, c: C.primary },
    { t: "agriculture", s: 9, c: C.ice },
  ];
  let cx = 7.3, cy = 2.85;
  cloud.forEach((tg) => {
    const w = tg.t.length * 0.085 * (tg.s / 10) + 0.25;
    if (cx + w > 12.6) { cx = 7.3; cy += 0.4; }
    s.addText(tg.t, { x: cx, y: cy, w: w, h: 0.35, fontSize: tg.s, fontFace: FONT_H, color: tg.c, bold: true, margin: 0 });
    cx += w + 0.1;
  });
  // Bottom right: features
  s.addShape(pres.shapes.RECTANGLE, { x: 7.1, y: 5.5, w: 5.7, h: 1.3, fill: { color: C.bgPanel }, line: { color: C.amber, width: 0.5 } });
  s.addText("Tag operations", { x: 7.3, y: 5.6, w: 5, h: 0.35, fontSize: 13, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
  s.addText("Auto-tag rules . merge dialog . per-namespace analytics . item_count tracking", {
    x: 7.3, y: 5.95, w: 5.4, h: 0.4, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0
  });
  s.addText("All tag -> item relations stored in M:N table for fast faceted query.", {
    x: 7.3, y: 6.35, w: 5.4, h: 0.4, fontSize: 10, fontFace: FONT_B, color: C.inkDim, italic: true, margin: 0
  });
}

// =============================================================
// SLIDE 12: Smart reports & AI
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 12, "11  .  smart reports & AI");
  s.addText("From raw items to analyst-grade report, in one click", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("LLM client + prompt templates + multi-format export", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Left: pipeline
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 2.3, w: 6.0, h: 4.5, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("REPORT GENERATION PIPELINE", { x: 0.7, y: 2.4, w: 5.6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const pipe = [
    { n: "1", t: "Pull items", d: "by topic_id / run_id / tag filter" },
    { n: "2", t: "Apply prompt", d: "topic.description_prompt or default template" },
    { n: "3", t: "Call LLM", d: "OpenAI / Ollama / custom endpoint" },
    { n: "4", t: "Persist", d: "save to reports table, item_ids link back" },
    { n: "5", t: "Export", d: "Markdown . HTML . DOCX (Pandoc) . PDF (WeasyPrint)" },
  ];
  pipe.forEach((p, i) => {
    const y = 2.85 + i * 0.7;
    s.addShape(pres.shapes.OVAL, { x: 0.7, y, w: 0.5, h: 0.5, fill: { color: C.primary }, line: { width: 0 } });
    s.addText(p.n, { x: 0.7, y, w: 0.5, h: 0.5, fontSize: 16, fontFace: FONT_H, color: C.ink, bold: true, align: "center", valign: "middle", margin: 0 });
    s.addText(p.t, { x: 1.4, y, w: 2.0, h: 0.3, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(p.d, { x: 1.4, y: y + 0.3, w: 4.8, h: 0.3, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
    if (i < pipe.length - 1) {
      s.addShape(pres.shapes.LINE, { x: 0.95, y: y + 0.5, w: 0, h: 0.2, line: { color: C.line, width: 1.5 } });
    }
  });
  // Right: model config & batch panel
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 2.3, w: 6.0, h: 2.1, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("MULTI-MODEL SUPPORT", { x: 7.0, y: 2.4, w: 5.6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const models = [
    { k: "OpenAI", v: "GPT-4o / GPT-4-turbo / GPT-3.5" },
    { k: "Ollama", v: "Local Llama3 / Qwen / Mistral" },
    { k: "Custom", v: "Any OpenAI-compatible endpoint" },
    { k: "Auto-discover", v: "Probe local Ollama for installed models" },
  ];
  models.forEach((m, i) => {
    const y = 2.85 + i * 0.34;
    s.addText(m.k, { x: 7.0, y, w: 1.5, h: 0.3, fontSize: 11, fontFace: FONT_H, color: C.ice, bold: true, margin: 0 });
    s.addText(m.v, { x: 8.6, y, w: 4.0, h: 0.3, fontSize: 10, fontFace: FONT_M, color: C.inkSoft, margin: 0 });
  });
  // Batch panel
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.6, w: 6.0, h: 2.2, fill: { color: C.bgPanel }, line: { color: C.amber, width: 0.5 } });
  s.addText("BATCH REPORT PANEL", { x: 7.0, y: 4.7, w: 5.6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  s.addText("Generate weekly summary for all active topics in one click. Reports auto-attach to topic history with full item_ids lineage.", {
    x: 7.0, y: 5.1, w: 5.6, h: 0.8, fontSize: 11, fontFace: FONT_B, color: C.ink, margin: 0
  });
  // Stats
  const rs = [
    { v: "1 click", l: "batch trigger" },
    { v: "4 formats", l: "MD / HTML / DOCX / PDF" },
    { v: "fire-and-forget", l: "no pipeline block" },
  ];
  rs.forEach((r, i) => {
    const x = 7.0 + i * 1.95;
    s.addText(r.v, { x, y: 5.95, w: 1.9, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(r.l, { x, y: 6.35, w: 1.9, h: 0.3, fontSize: 9, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
}

// =============================================================
// SLIDE 13: Scheduling
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 13, "12  .  scheduling & automation");
  s.addText("Hands-off intelligence, always on time", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Cron-driven collection + auto-report + auto-notify, no babysitting", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Timeline
  s.addText("TYPICAL DAILY RHYTHM", { x: 0.5, y: 2.3, w: 12, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  // Timeline bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 3.2, w: 12.3, h: 0.04, fill: { color: C.line }, line: { width: 0 } });
  const events = [
    { x: 1.0,  t: "08:00", h: "Daily tariff\ntopics collect", c: C.amber },
    { x: 3.2,  t: "09:30", h: "Sanctions\nwatch refresh", c: C.warn },
    { x: 5.4,  t: "11:00", h: "EU customs\nRSS pull", c: C.ice },
    { x: 7.6,  t: "14:00", h: "Auto-report:\ntariff tracker", c: C.primary },
    { x: 9.8,  t: "16:00", h: "Weekly summary\n(batch)", c: C.success },
    { x: 12.0, t: "18:00", h: "Email digest\nto subscribers", c: C.amber },
  ];
  events.forEach((e) => {
    s.addShape(pres.shapes.OVAL, { x: e.x - 0.12, y: 3.1, w: 0.24, h: 0.24, fill: { color: e.c }, line: { color: C.bgDeep, width: 2 } });
    s.addText(e.t, { x: e.x - 0.6, y: 2.7, w: 1.2, h: 0.3, fontSize: 12, fontFace: FONT_M, color: C.ink, bold: true, align: "center", margin: 0 });
    s.addText(e.h, { x: e.x - 0.85, y: 3.5, w: 1.7, h: 0.7, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, align: "center", margin: 0 });
  });
  // Two cards
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.5, w: 6.0, h: 2.3, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("Topic-level scheduling", { x: 0.7, y: 4.6, w: 5.6, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText([
    { text: "Cron expression per topic", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Collect window (publish-time filter)", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Auto-tag rules executed post-collect", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Auto-report flag triggers LLM call", options: { bullet: { code: "25A0" }, color: C.inkSoft } },
  ], { x: 0.7, y: 5.0, w: 5.6, h: 1.7, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 4, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.5, w: 6.0, h: 2.3, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("Global scheduling", { x: 7.0, y: 4.6, w: 5.6, h: 0.4, fontSize: 14, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText([
    { text: "Bind multiple topics + sources in one rule", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Standard cron, no proprietary syntax", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Run history with full error_log", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Lifespan-managed APScheduler instance", options: { bullet: { code: "25A0" }, color: C.inkSoft } },
  ], { x: 7.0, y: 5.0, w: 5.6, h: 1.7, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 4, margin: 0 });
}

// =============================================================
// SLIDE 14: Notifications
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 14, "13  .  notifications & delivery");
  s.addText("Push intelligence to the people who need it", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("Fire-and-forget - never blocks the collection pipeline", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Channels
  s.addText("CHANNELS", { x: 0.5, y: 2.3, w: 6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const chs = [
    { t: "Webhook", d: "Generic HTTP POST with JSON payload - integrate with Slack, Teams, Lark, custom services" },
    { t: "Email",   d: "SMTP with HTML body + attachment support for the full report file" },
  ];
  chs.forEach((c, i) => {
    const y = 2.75 + i * 1.0;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 6.0, h: 0.9, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 0.1, h: 0.9, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(c.t, { x: 0.75, y: y + 0.1, w: 5.6, h: 0.35, fontSize: 16, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(c.d, { x: 0.75, y: y + 0.45, w: 5.6, h: 0.45, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  // Triggers
  s.addText("TRIGGERS", { x: 7.1, y: 2.3, w: 6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const trs = [
    { t: "On collection complete", d: "All items for a run available in payload" },
    { t: "On auto-report ready",   d: "Attach the full report file (PDF/DOCX)" },
    { t: "On error",               d: "Optional failure notification to ops" },
  ];
  trs.forEach((c, i) => {
    const y = 2.75 + i * 0.7;
    s.addShape(pres.shapes.RECTANGLE, { x: 7.1, y, w: 5.7, h: 0.6, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.OVAL, { x: 7.25, y: y + 0.17, w: 0.26, h: 0.26, fill: { color: C.amber }, line: { width: 0 } });
    s.addText(c.t, { x: 7.6, y: y + 0.05, w: 5.0, h: 0.3, fontSize: 13, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
    s.addText(c.d, { x: 7.6, y: y + 0.32, w: 5.1, h: 0.25, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  // Bottom: export
  s.addShape(pres.shapes.RECTANGLE, { x: 7.1, y: 5.0, w: 5.7, h: 1.8, fill: { color: C.bgPanel }, line: { color: C.amber, width: 0.5 } });
  s.addText("ALSO: data export", { x: 7.3, y: 5.1, w: 5.4, h: 0.35, fontSize: 12, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 2, margin: 0 });
  s.addText("Filtered item subsets exportable as CSV . JSON . XLSX - feeds directly into downstream BI tools or compliance archives.", {
    x: 7.3, y: 5.45, w: 5.4, h: 0.8, fontSize: 11, fontFace: FONT_B, color: C.ink, margin: 0
  });
  s.addText("Test-send available in UI for every configured channel.", {
    x: 7.3, y: 6.3, w: 5.4, h: 0.4, fontSize: 10, fontFace: FONT_B, color: C.inkDim, italic: true, margin: 0
  });
}

// =============================================================
// SLIDE 15: Quality & observability
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 15, "14  .  quality & observability");
  s.addText("Production-grade rigor, not a weekend hack", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("258 tests . full TypeScript . error logs . audit trail . backups", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Big stat row
  const qs = [
    { v: "258", l: "Test cases (backend)" },
    { v: "100%", l: "Pass rate" },
    { v: "0", l: "TypeScript errors" },
    { v: "170ms", l: "Production build" },
  ];
  qs.forEach((q, i) => {
    const x = 0.5 + i * 3.15, y = 2.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.95, h: 1.4, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.95, h: 0.06, fill: { color: C.success }, line: { width: 0 } });
    s.addText(q.v, { x, y: y + 0.2, w: 2.95, h: 0.7, fontSize: 38, fontFace: FONT_H, color: C.amber, bold: true, align: "center", margin: 0 });
    s.addText(q.l, { x, y: y + 0.95, w: 2.95, h: 0.4, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, align: "center", margin: 0 });
  });
  // Two columns: practices + observability
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.0, w: 6.0, h: 2.8, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("ENGINEERING PRACTICES", { x: 0.7, y: 4.1, w: 5.6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  s.addText([
    { text: "TDD loop (red . green . improve) with 80%+ coverage target", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Function <= 50 lines, file <= 400 lines, max 800 in extreme cases", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Immutability discipline (spread, never mutate)", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Explicit error handling, structured server logs", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Conventional commits: feat / fix / refactor / docs / test", options: { bullet: { code: "25A0" }, color: C.inkSoft } },
  ], { x: 0.7, y: 4.5, w: 5.6, h: 2.2, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 4, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.0, w: 6.0, h: 2.8, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("OBSERVABILITY", { x: 7.0, y: 4.1, w: 5.6, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  s.addText([
    { text: "Batch view: group runs by batch_id, drill into errors", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Active tasks: real-time view of running collections", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Error log per run, retained for audit replay", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Database backup utilities, WAL mode for crash safety", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Auto schema migration (no manual DDL on upgrade)", options: { bullet: { code: "25A0" }, color: C.inkSoft } },
  ], { x: 7.0, y: 4.5, w: 5.6, h: 2.2, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 4, margin: 0 });
}

// =============================================================
// SLIDE 16: Getting started & dev experience
// =============================================================
{
  const s = darkSlide();
  addPageHeader(s, 16, "15  .  getting started");
  s.addText("Up and running in 5 minutes", { x: 0.5, y: 0.8, w: 12.3, h: 0.7, fontSize: 30, fontFace: FONT_H, color: C.ink, bold: true, margin: 0 });
  s.addText("One-command dev launch, Docker-ready, no DevOps required", {
    x: 0.5, y: 1.55, w: 12.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.ice, italic: true, margin: 0
  });
  // Terminal mock
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 2.3, w: 7.5, h: 3.6, fill: { color: "06121F" }, line: { color: C.line, width: 0.5 } });
  s.addShape(pres.shapes.OVAL, { x: 0.7, y: 2.45, w: 0.18, h: 0.18, fill: { color: "FF5F57" }, line: { width: 0 } });
  s.addShape(pres.shapes.OVAL, { x: 0.95, y: 2.45, w: 0.18, h: 0.18, fill: { color: "FEBC2E" }, line: { width: 0 } });
  s.addShape(pres.shapes.OVAL, { x: 1.20, y: 2.45, w: 0.18, h: 0.18, fill: { color: "28C840" }, line: { width: 0 } });
  s.addText("zsh  .  ~/GatherInfo", { x: 1.6, y: 2.4, w: 5, h: 0.3, fontSize: 10, fontFace: FONT_M, color: C.inkDim, valign: "middle", margin: 0 });
  const lines = [
    { c: C.inkDim, t: "# 1. install dependencies (one time)" },
    { c: C.ice,     t: "npm --prefix frontend install" },
    { c: C.ice,     t: "python3 -m venv backend/.venv" },
    { c: C.ice,     t: "backend/.venv/bin/pip install -r backend/requirements.txt" },
    { c: C.inkDim, t: "" },
    { c: C.inkDim, t: "# 2. launch dev environment" },
    { c: C.success, t: "npm run dev" },
    { c: C.inkDim, t: "" },
    { c: C.inkDim, t: "# 3. open in browser" },
    { c: C.amber,  t: "open http://localhost:5178" },
    { c: C.inkDim, t: "" },
    { c: C.inkDim, t: "# optional: Docker one-shot" },
    { c: C.success, t: "docker-compose up" },
  ];
  lines.forEach((l, i) => {
    s.addText(l.t, { x: 0.7, y: 2.85 + i * 0.23, w: 7.0, h: 0.22, fontSize: 10, fontFace: FONT_M, color: l.c, margin: 0 });
  });
  // Right column: URLs + ports
  s.addShape(pres.shapes.RECTANGLE, { x: 8.3, y: 2.3, w: 4.5, h: 3.6, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
  s.addText("ACCESS POINTS", { x: 8.5, y: 2.4, w: 4.2, h: 0.4, fontSize: 11, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 4, margin: 0 });
  const urls = [
    { k: "Frontend",     v: "localhost:5178" },
    { k: "Backend API",  v: "localhost:8109" },
    { k: "API docs",     v: "localhost:8109/docs" },
    { k: "Dev Dashboard",v: "localhost:9999" },
  ];
  urls.forEach((u, i) => {
    const y = 2.85 + i * 0.45;
    s.addText(u.k, { x: 8.5, y, w: 1.8, h: 0.35, fontSize: 11, fontFace: FONT_H, color: C.ice, bold: true, margin: 0 });
    s.addText(u.v, { x: 10.3, y, w: 2.4, h: 0.35, fontSize: 11, fontFace: FONT_M, color: C.ink, margin: 0 });
  });
  s.addShape(pres.shapes.LINE, { x: 8.5, y: 4.75, w: 4.2, h: 0, line: { color: C.line, width: 0.5 } });
  s.addText("DEV DASHBOARD FEATURES", { x: 8.5, y: 4.85, w: 4.2, h: 0.3, fontSize: 9, fontFace: FONT_H, color: C.amber, bold: true, charSpacing: 3, margin: 0 });
  s.addText([
    { text: "One-click start / stop for all services", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "Live logs from frontend + backend", options: { bullet: { code: "25A0" }, color: C.inkSoft, breakLine: true } },
    { text: "PID file cleanup on shutdown", options: { bullet: { code: "25A0" }, color: C.inkSoft } },
  ], { x: 8.5, y: 5.15, w: 4.2, h: 0.7, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, paraSpaceAfter: 2, margin: 0 });
  // Bottom strip: 3 launch modes
  const modes = [
    { t: "Dev (npm run dev)", d: "Hot reload, both servers, full debug" },
    { t: "Manual (startup.py)", d: "Subprocess-based, same as dev with verbose" },
    { t: "Production (Docker)", d: "Compose stack, nginx reverse proxy" },
  ];
  modes.forEach((m, i) => {
    const x = 0.5 + i * 4.2, y = 6.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 0.85, fill: { color: C.bgPanel }, line: { color: C.line, width: 0.5 } });
    s.addText(m.t, { x: x + 0.2, y: y + 0.08, w: 3.7, h: 0.3, fontSize: 12, fontFace: FONT_H, color: C.amber, bold: true, margin: 0 });
    s.addText(m.d, { x: x + 0.2, y: y + 0.4, w: 3.7, h: 0.4, fontSize: 10, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
}

// =============================================================
// SLIDE 17: Closing CTA
// =============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.bgDeep };
  // Big background panel
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.3, h: 7.5, fill: { color: C.bgDeep }, line: { width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 2.5, w: 13.3, h: 2.5, fill: { color: C.bgPanel }, line: { width: 0 } });
  // Top brand
  s.addShape(pres.shapes.RECTANGLE, { x: 5.65, y: 1.5, w: 2, h: 0.1, fill: { color: C.amber }, line: { width: 0 } });
  s.addText("GatherInfo", { x: 0, y: 1.7, w: 13.3, h: 1.0, fontSize: 56, fontFace: FONT_H, color: C.ink, bold: true, align: "center", margin: 0 });
  s.addText("From keyword to analyst-grade report - in one closed loop.", { x: 0, y: 2.8, w: 13.3, h: 0.6, fontSize: 22, fontFace: FONT_H, color: C.ice, align: "center", margin: 0 });
  s.addText("9 collection channels . 92 pre-built sources . smart reports . full observability", { x: 0, y: 3.4, w: 13.3, h: 0.4, fontSize: 13, fontFace: FONT_B, color: C.inkSoft, align: "center", italic: true, charSpacing: 2, margin: 0 });
  // Three CTA cards
  const ctas = [
    { t: "TRY IT",     d: "Clone the repo and run npm run dev - 5 minutes to your first report.", c: C.amber },
    { t: "EXTEND IT",  d: "Add a custom source in ~30 lines via the BaseCollector contract.", c: C.primary },
    { t: "DEPLOY IT",  d: "docker-compose up - production stack with nginx in one command.", c: C.success },
  ];
  ctas.forEach((c, i) => {
    const x = 0.5 + i * 4.2, y = 5.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 1.5, fill: { color: C.bgCard }, line: { color: C.line, width: 0.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.05, h: 0.08, fill: { color: c.c }, line: { width: 0 } });
    s.addText(c.t, { x: x + 0.2, y: y + 0.2, w: 3.7, h: 0.5, fontSize: 20, fontFace: FONT_H, color: c.c, bold: true, charSpacing: 4, margin: 0 });
    s.addText(c.d, { x: x + 0.2, y: y + 0.75, w: 3.7, h: 0.7, fontSize: 11, fontFace: FONT_B, color: C.inkSoft, margin: 0 });
  });
  // Footer
  s.addText("GatherInfo  .  v1.0  .  2026  .  MIT License", { x: 0, y: 7.0, w: 13.3, h: 0.3, fontSize: 10, fontFace: FONT_B, color: C.inkDim, align: "center", charSpacing: 4, margin: 0 });
}

pres.writeFile({ fileName: "GatherInfo-Product-Briefing.pptx" }).then(fn => {
  console.log("Wrote: " + fn);
});
