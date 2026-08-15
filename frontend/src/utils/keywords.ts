const KEYWORD_TOKENS = /"[^"]*"|'[^']*'|“[^”]*”|‘[^’]*’|[^,，;；、\s]+/g;

function unquoteKeyword(value: string): string {
  const trimmed = value.trim();
  const pairs: Record<string, string> = { '"': '"', "'": "'", "“": "”", "‘": "’" };
  const last = trimmed[trimmed.length - 1];
  if (trimmed.length >= 2 && pairs[trimmed[0]] === last) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

/** Parse the editable keyword field while allowing quoted multi-word phrases. */
export function parseKeywordInput(value: string): string[] {
  const seen = new Set<string>();
  return (value.match(KEYWORD_TOKENS) ?? []).reduce<string[]>((keywords, token) => {
    const keyword = unquoteKeyword(token);
    if (!keyword || seen.has(keyword)) return keywords;
    seen.add(keyword);
    return [...keywords, keyword];
  }, []);
}

/** Keep existing multi-word keywords intact when opening the editor. */
export function formatKeywordInput(keywords: string[]): string {
  return keywords
    .map((keyword) => {
      const value = keyword.trim();
      if (!value) return "";
      return /[,，;；、\s]/.test(value) ? `"${value.replace(/"/g, "'")}"` : value;
    })
    .filter(Boolean)
    .join(", ");
}
