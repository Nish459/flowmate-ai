import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

export default function Markdown({ text }) {
  const html = useMemo(() => {
    if (!text) return "";
    return DOMPurify.sanitize(marked.parse(text));
  }, [text]);

  // eslint-disable-next-line react/no-danger
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}
