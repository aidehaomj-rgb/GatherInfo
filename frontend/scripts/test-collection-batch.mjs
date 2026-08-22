// 无头验证：新批次闭环摘要可渲染，旧响应不产生占位内容。
import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.dirname(scriptDir);
const sourceFile = path.join(projectDir, "src/components/CollectionBatchProgress.tsx");
const outputFile = path.join(projectDir, "src/components", `.collection-batch-test-${process.pid}.mjs`);

const source = await readFile(sourceFile, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    jsx: ts.JsxEmit.ReactJSX,
  },
});
await writeFile(outputFile, compiled.outputText, "utf8");

try {
  const { CollectionBatchProgress } = await import(`${pathToFileURL(outputFile).href}?v=${Date.now()}`);
  const summary = {
    batch_id: "batch-1",
    topic_id: "topic-1",
    status: "completed",
    current_round: 2,
    max_rounds: 2,
    target: { weekly_target: 20, min_domains: 8, min_regions: 4 },
    metrics: {
      items_discovered: 128,
      items_date_rejected: 18,
      items_topic_rejected: 31,
      items_quality_rejected: 22,
      items_new: 17,
      items_reused: 4,
      items_duplicate: 9,
      domains: 11,
      regions: 5,
      evidence_ratio: 0.72,
    },
    acceptance: { accepted: false, checks: { items: false, domains: true } },
    gaps: [{ type: "quantity", missing: 3 }, "来源集中度偏高"],
    stop_reason: "max_rounds_reached",
  };

  const html = renderToStaticMarkup(CollectionBatchProgress({ summary }));
  assert.match(html, /第 2 \/ 2 轮/);
  assert.match(html, /动态目标/);
  assert.match(html, /20/);
  assert.match(html, /发现候选/);
  assert.match(html, /128/);
  assert.match(html, /未达标/);
  assert.match(html, /数量还差 3 条/);
  assert.match(html, /已完成两轮采集/);
  assert.doesNotMatch(html, /候选正文/);

  const legacyHtml = renderToStaticMarkup(CollectionBatchProgress({ summary: null }));
  assert.equal(legacyHtml, "");
  const initializingHtml = renderToStaticMarkup(CollectionBatchProgress({
    summary: { ...summary, target: null, metrics: null, acceptance: null, gaps: [] },
  }));
  assert.match(initializingHtml, /动态目标/);
  assert.match(initializingHtml, /待计算/);
  console.log("collection batch progress render: PASS");
} finally {
  await rm(outputFile, { force: true });
}
