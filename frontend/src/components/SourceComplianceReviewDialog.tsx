import { useState } from "react";
import { ShieldCheck, X } from "lucide-react";

import { reviewSourceCompliance } from "../api";
import type { Source } from "../types";

type Decision = "approve_full" | "approve_excerpt" | "block";
type RobotsEvidence = "allowed" | "api_required" | "blocked";
type TermsEvidence =
  | "allowed"
  | "public_domain"
  | "government_conditions"
  | "open_government"
  | "us_government"
  | "blocked";

type Props = {
  source: Source;
  onClose: () => void;
  onReviewed: (source: Source) => void;
};

export function SourceComplianceReviewDialog({ source, onClose, onReviewed }: Props) {
  const [decision, setDecision] = useState<Decision>("approve_excerpt");
  const [robotsEvidence, setRobotsEvidence] = useState<RobotsEvidence>("allowed");
  const [termsEvidence, setTermsEvidence] = useState<TermsEvidence>("allowed");
  const [urls, setUrls] = useState((source.discovery_urls ?? []).join("\n"));
  const [legalBasis, setLegalBasis] = useState(source.legal_basis ?? "");
  const [note, setNote] = useState(source.compliance_note ?? "");
  const [reviewedBy, setReviewedBy] = useState(
    source.compliance_reviewed_by ?? "本机运营人员",
  );
  const [confirmed, setConfirmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const discoveryUrls = urls.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
    setSaving(true);
    setError(null);
    try {
      const reviewed = await reviewSourceCompliance(source.id, {
        decision,
        robots_evidence: robotsEvidence,
        terms_evidence: termsEvidence,
        discovery_urls: discoveryUrls,
        legal_basis: legalBasis,
        compliance_note: note,
        reviewed_by: reviewedBy,
        confirmed,
      });
      onReviewed(reviewed);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "合规审核保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3><ShieldCheck size={18} /> 信息源合规审核</h3>
            <p className="text-muted small">{source.name} · 审批仅对当前地址、认证方式、频率和配额有效。</p>
          </div>
          <button type="button" className="btn-icon" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </div>

        <div className="form-grid modal-body">
          <label>
            <span className="field-label-row">处理决定 <span className="required-mark">*</span></span>
            <select value={decision} onChange={(event) => setDecision(event.target.value as Decision)} required>
              <option value="approve_excerpt">批准摘要采集，不送入 LLM</option>
              <option value="approve_full">批准全文采集与 LLM 中文精编</option>
              <option value="block">阻止自动采集</option>
            </select>
          </label>
          <label>
            <span className="field-label-row">审核人 <span className="required-mark">*</span></span>
            <input value={reviewedBy} onChange={(event) => setReviewedBy(event.target.value)} required minLength={2} />
          </label>
          <label>
            <span className="field-label-row">robots 核验 <span className="required-mark">*</span></span>
            <select value={robotsEvidence} onChange={(event) => setRobotsEvidence(event.target.value as RobotsEvidence)} required>
              <option value="allowed">允许自动采集</option>
              <option value="api_required">要求使用 API</option>
              <option value="blocked">明确禁止</option>
            </select>
          </label>
          <label>
            <span className="field-label-row">条款依据 <span className="required-mark">*</span></span>
            <select value={termsEvidence} onChange={(event) => setTermsEvidence(event.target.value as TermsEvidence)} required>
              <option value="allowed">条款明确允许</option>
              <option value="public_domain">公共领域</option>
              <option value="government_conditions">政府网站使用条件</option>
              <option value="open_government">开放政府许可</option>
              <option value="us_government">美国政府作品</option>
              <option value="blocked">条款明确禁止</option>
            </select>
          </label>
          <label className="span-2">
            <span className="field-label-row">核验页面 URL（每行一个） <span className="required-mark">*</span></span>
            <textarea value={urls} onChange={(event) => setUrls(event.target.value)} rows={4} required placeholder="https://example.org/robots.txt\nhttps://example.org/terms" />
          </label>
          <label className="span-2">
            <span className="field-label-row">法律或许可依据 <span className="required-mark">*</span></span>
            <textarea value={legalBasis} onChange={(event) => setLegalBasis(event.target.value)} rows={3} minLength={10} required />
          </label>
          <label className="span-2">
            <span className="field-label-row">审核记录 <span className="required-mark">*</span></span>
            <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={4} minLength={20} required />
          </label>
          <label className="span-2 checkbox-row">
            <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} required />
            我确认已人工核对 robots、网站条款与实际采集地址，并理解配置变化会使本次审批失效。
          </label>
          {error && <div className="error-banner span-2">{error}</div>}
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleSubmit()}
            disabled={saving || !confirmed}
          >
            {saving ? "保存中…" : "保存审核决定"}
          </button>
        </div>
      </div>
    </div>
  );
}
