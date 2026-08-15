import React, { useState, useCallback } from "react";
import { Rss, Check, Copy } from "lucide-react";

interface RssFeedButtonProps {
  baseUrl?: string;
  filters?: {
    topicId?: string;
    sourceId?: string;
    tag?: string;
    language?: string;
    q?: string;
  };
  className?: string;
}

function buildRssUrl(baseUrl: string, filters: RssFeedButtonProps["filters"]): string {
  const url = new URL("/api/v1/rss", baseUrl);
  if (filters?.topicId) url.searchParams.set("topic_id", filters.topicId);
  if (filters?.sourceId) url.searchParams.set("source_id", filters.sourceId);
  if (filters?.tag) url.searchParams.set("tag", filters.tag);
  if (filters?.language) url.searchParams.set("language", filters.language);
  if (filters?.q) url.searchParams.set("q", filters.q);
  return url.toString();
}

export const RssFeedButton: React.FC<RssFeedButtonProps> = ({
  baseUrl = window.location.origin,
  filters = {},
  className = "",
}) => {
  const [copied, setCopied] = useState<boolean>(false);

  const rssUrl = buildRssUrl(baseUrl, filters);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(rssUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for environments without clipboard API
      const ta = document.createElement("textarea");
      ta.value = rssUrl;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [rssUrl]);

  return (
    <div className={["rss-feed-btn-wrap", className].join(" ")}>
      <button
        type="button"
        className="rss-feed-btn"
        onClick={copy}
        title="复制 RSS 订阅链接"
      >
        {copied ? <Check size={16} /> : <Rss size={16} />}
        <span>{copied ? "已复制" : "RSS 订阅"}</span>
      </button>
    </div>
  );
};
