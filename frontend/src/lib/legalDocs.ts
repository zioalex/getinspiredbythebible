import { existsSync, readFileSync } from "fs";
import { join } from "path";

// Legal docs live inside the frontend build context so they are available
// at Next.js build time inside the Docker container.
const docsDir = join(process.cwd(), "public", "legal");

/**
 * Parses a simple YAML frontmatter block (--- ... ---) from markdown content.
 * Returns the parsed key/value pairs and the remaining body.
 */
function parseFrontmatter(content: string): {
  data: Record<string, string>;
  body: string;
} {
  const fmRegex = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;
  const match = fmRegex.exec(content);
  if (!match) {
    return { data: {}, body: content };
  }

  const data: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim();
    const value = line.slice(colonIdx + 1).trim();
    if (key) data[key] = value;
  }

  return { data, body: content.slice(match[0].length) };
}

/**
 * Returns the content of a legal markdown document, with frontmatter stripped.
 * Looks for a locale-specific file first (e.g. privacy-policy.it.md),
 * then falls back to the base file (privacy-policy.md).
 */
export function getLegalDocContent(basename: string, locale: string): string {
  const localePath = join(docsDir, `${basename}.${locale}.md`);
  const defaultPath = join(docsDir, `${basename}.md`);

  const filePath = existsSync(localePath) ? localePath : defaultPath;

  if (!existsSync(filePath)) {
    return `# Document not found\n\nThe requested document (${basename}) could not be found.`;
  }

  const raw = readFileSync(filePath, "utf-8");
  const { body } = parseFrontmatter(raw);
  return body;
}

/**
 * Returns the last-updated date for a legal markdown document.
 * Reads the `lastUpdated` YAML frontmatter field (YYYY-MM-DD).
 * Falls back to today's date if the field is absent or unparseable.
 */
export function getLegalDocDate(basename: string): Date {
  const filePath = join(docsDir, `${basename}.md`);

  if (existsSync(filePath)) {
    try {
      const raw = readFileSync(filePath, "utf-8");
      const { data } = parseFrontmatter(raw);
      if (data.lastUpdated) {
        const d = new Date(data.lastUpdated);
        if (!isNaN(d.getTime())) return d;
      }
    } catch {
      // fall through
    }
  }

  return new Date();
}
