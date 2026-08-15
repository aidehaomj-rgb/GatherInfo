const FILE_MARKER_PATTERN =
  /(?:^[\s\-_:：|]*|[\s\-_:：|]+)(?:[\[【(（]\s*)?(?:PDF|DOCX?|XLSX?|PPTX?|HTML?|XML|CSV)(?:\s*[\]】)）])?(?=$|[\s\-_:：|])/gi;

export function cleanItemTitle(title: string | null | undefined) {
  return (title || "")
    .replace(FILE_MARKER_PATTERN, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/^[\s\-_:：|]+|[\s\-_:：|]+$/g, "")
    .trim();
}

export function getDisplayTitle(title: string | null | undefined, fallback = "无标题") {
  return cleanItemTitle(title) || fallback;
}
