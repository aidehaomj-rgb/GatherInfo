import type { ReactNode } from "react";

interface Props {
  content: string;
}

function renderInlineText(line: string, keyPrefix: string): ReactNode[] {
  const tokens = line.split(/(\*\*.+?\*\*|\[参见条目\d+\])/g).filter(Boolean);
  return tokens.map((token, index) => {
    const key = `${keyPrefix}-${index}`;
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={key}>{token.slice(2, -2)}</strong>;
    }
    if (/^\[参见条目\d+\]$/.test(token)) {
      return <span key={key} style={{ color: "var(--accent)", fontSize: "0.8em" }}>{token}</span>;
    }
    return token;
  });
}

/**
 * Simple Markdown renderer for report content.
 * Supports: ##/### headers, **bold**, numbered lists, bullet points, code blocks.
 */
export function RenderMarkdown({ content }: Props): ReactNode {
  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let inCode = false;
  let codeBlock: string[] = [];

  const renderInline = (value: string): ReactNode[] => {
    const tokens = value.split(/(https?:\/\/[^\s]+|\*\*.+?\*\*|\[参见条目\d+\])/g).filter(Boolean);
    return tokens.map((token, index) => {
      if (token.startsWith("**") && token.endsWith("**")) return <strong key={index}>{token.slice(2, -2)}</strong>;
      if (/^https?:\/\//.test(token)) return <a key={index} href={token} target="_blank" rel="noreferrer">{token}</a>;
      if (/^\[参见条目\d+\]$/.test(token)) return <span key={index} className="md-reference">{token}</span>;
      return token;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) {
        elements.push(<pre key={i} className="md-code-block"><code>{codeBlock.join("\n")}</code></pre>);
        codeBlock = [];
        inCode = false;
      } else {
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeBlock.push(line);
      continue;
    }

    if (line.trim().startsWith("|") && lines[i + 1]?.trim().match(/^\|(?:\s*:?-+:?\s*\|)+$/)) {
      const rows: string[][] = [];
      const parseRow = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
      const headers = parseRow(line);
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(parseRow(lines[i]));
        i += 1;
      }
      i -= 1;
      elements.push(
        <div key={`table-${i}`} className="md-table-wrap">
          <table className="md-table">
            <thead><tr>{headers.map((cell, index) => <th key={index}>{renderInline(cell)}</th>)}</tr></thead>
            <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{renderInline(cell)}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (line.startsWith("## ")) {
      elements.push(<h4 key={i} style={{ margin: "16px 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--accent)" }}>{line.slice(3)}</h4>);
    } else if (line.startsWith("### ")) {
      elements.push(<h5 key={i} style={{ margin: "12px 0 6px", fontSize: "0.9rem", fontWeight: 600 }}>{line.slice(4)}</h5>);
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(<p key={i} style={{ fontWeight: 600, margin: "8px 0 4px" }}>{renderInline(line)}</p>);
    } else if (line.match(/^\d\.\s/)) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12 }}>{renderInline(line)}</p>);
    } else if (line.startsWith("- ")) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12, color: "var(--ink-muted)" }}>{renderInline(line)}</p>);
    } else if (line.trim() === "") {
      elements.push(<div key={i} style={{ height: 4 }} />);
    } else {
      elements.push(<p key={i} style={{ margin: "4px 0" }}>{renderInlineText(line, `line-${i}`)}</p>);
    }
  }

  return <>{elements}</>;
}
