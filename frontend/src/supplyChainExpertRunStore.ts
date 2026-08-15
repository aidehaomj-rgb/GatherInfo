import { discoverSupplyChains } from "./api";
import type { SupplyChainDiscoveryResult } from "./types";

export interface SupplyChainExpertRunInput {
  countries: string[];
  minimum_score: number;
  max_candidates: number;
  mcp_tools: string[];
  model_id?: string;
  research_rounds?: number;
  import_record_window_days?: 90 | 180 | 365;
}

interface RunSnapshot {
  running: boolean;
  startedAt: number | null;
  finishedAt: number | null;
  result: SupplyChainDiscoveryResult | null;
  error: string;
}

let snapshot: RunSnapshot = {
  running: false,
  startedAt: null,
  finishedAt: null,
  result: null,
  error: "",
};

const listeners = new Set<() => void>();

function update(next: RunSnapshot) {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

export const getSupplyChainExpertRun = () => snapshot;

export function subscribeSupplyChainExpertRun(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function startSupplyChainExpertRun(input: SupplyChainExpertRunInput) {
  if (snapshot.running) return;
  const startedAt = Date.now();
  update({ running: true, startedAt, finishedAt: null, result: null, error: "" });
  try {
    const result = await discoverSupplyChains(input);
    update({ running: false, startedAt, finishedAt: Date.now(), result, error: "" });
  } catch (reason) {
    update({
      running: false,
      startedAt,
      finishedAt: Date.now(),
      result: null,
      error: reason instanceof Error ? reason.message : "专家任务执行失败",
    });
  }
}
