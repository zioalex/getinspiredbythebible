import { existsSync, readFileSync, statSync } from "fs";
import { join } from "path";
import { execSync } from "child_process";

// Docs directory is one level above the Next.js project root (frontend/)
const docsDir = join(process.cwd(), "..", "docs");

/**
 * Returns the content of a legal markdown document.
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

  return readFileSync(filePath, "utf-8");
}

/**
 * Returns the last git commit date for a legal markdown document.
 * Falls back to the file's mtime if git is unavailable.
 */
export function getLegalDocDate(basename: string): Date {
  const filePath = join(docsDir, `${basename}.md`);

  try {
    const output = execSync(`git log -1 --format=%cI -- "${filePath}"`, {
      encoding: "utf-8",
      cwd: join(process.cwd(), ".."),
    }).trim();
    if (output) return new Date(output);
  } catch {
    // ignore — fall through to mtime
  }

  if (existsSync(filePath)) {
    return statSync(filePath).mtime;
  }

  return new Date();
}
