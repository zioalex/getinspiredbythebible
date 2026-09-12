import { describe, it, expect } from "vitest";
import { buildOfflineHtml } from "./generate-offline-page.mjs";

const LOCALES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"];

function messagesFor(locales) {
  const out = {};
  for (const locale of locales) {
    out[locale] = {
      title: `title-${locale}`,
      description: `description-${locale}`,
      retry: `retry-${locale}`,
    };
  }
  return out;
}

describe("buildOfflineHtml", () => {
  it("embeds all 11 locale codes and their title/description/retry strings", () => {
    const html = buildOfflineHtml(messagesFor(LOCALES), LOCALES, "en");
    for (const locale of LOCALES) {
      expect(html).toContain(`"${locale}"`);
      expect(html).toContain(`title-${locale}`);
      expect(html).toContain(`description-${locale}`);
      expect(html).toContain(`retry-${locale}`);
    }
  });

  it("escapes a </script> sequence in a translated string so it can't break out of the script block", () => {
    const messages = messagesFor(LOCALES);
    messages.en.description = "</script><script>alert(1)</script>";
    const html = buildOfflineHtml(messages, LOCALES, "en");

    // The literal, unescaped sequence must not appear anywhere in the output.
    expect(html).not.toContain("</script><script>alert(1)</script>");

    // But the (escaped) payload should still be present inside the script block,
    // proving it wasn't silently dropped — just neutralized.
    expect(html).toContain("<\\/script>");
  });

  it("is fully self-contained: no external src=/href= URLs, no <link rel=\"stylesheet\">", () => {
    const html = buildOfflineHtml(messagesFor(LOCALES), LOCALES, "en");
    expect(html).not.toMatch(/\ssrc=["']https?:/i);
    expect(html).not.toMatch(/\shref=["']https?:/i);
    expect(html).not.toMatch(/<link[^>]*rel=["']stylesheet["']/i);
  });

  it("marks itself noindex", () => {
    const html = buildOfflineHtml(messagesFor(LOCALES), LOCALES, "en");
    expect(html).toContain('<meta name="robots" content="noindex">');
  });

  it("references ar in an RTL-handling branch", () => {
    const html = buildOfflineHtml(messagesFor(LOCALES), LOCALES, "en");
    expect(html).toMatch(/"ar"/);
    expect(html).toMatch(/rtl/i);
  });
});
