import type { Narrative } from "@/lib/api";

const BLOCKS: { key: keyof Narrative; heading: string }[] = [
  { key: "finding", heading: "High-value finding:" },
  { key: "detected", heading: "Detected signals:" },
  { key: "weak", heading: "Weak signals:" },
  { key: "red", heading: "Red Team recommendation:" },
  { key: "blue", heading: "Blue Team recommendation:" },
];

function sliceBlock(report: string, heading: string): string {
  const start = report.indexOf(heading);
  if (start < 0) return "";
  const from = start + heading.length;
  let end = report.length;
  for (const block of BLOCKS) {
    if (block.heading === heading) continue;
    const idx = report.indexOf(block.heading, from);
    if (idx >= 0 && idx < end) end = idx;
  }
  const banner = report.indexOf("====", from);
  if (banner >= 0 && banner < end) end = banner;
  return report.slice(from, end).trim();
}

function bullets(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
}

export function parseNarrative(report: string, fallback?: Narrative): Narrative {
  if (fallback?.finding) return fallback;
  return {
    finding: sliceBlock(report, "High-value finding:"),
    detected: bullets(sliceBlock(report, "Detected signals:")),
    weak: bullets(sliceBlock(report, "Weak signals:")),
    red: sliceBlock(report, "Red Team recommendation:"),
    blue: sliceBlock(report, "Blue Team recommendation:"),
  };
}

export function pct(n?: number) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}
