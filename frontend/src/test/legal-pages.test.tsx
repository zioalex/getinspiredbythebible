import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import enMessages from "../../messages/en.json";

// Mock next-intl server functions used in server components
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn().mockImplementation(({ namespace }) => {
    const ns = enMessages[namespace as keyof typeof enMessages] as Record<
      string,
      string
    >;
    return Promise.resolve((key: string, params?: Record<string, string>) => {
      let value = ns?.[key] ?? key;
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          value = value.replace(`{${k}}`, v);
        });
      }
      return value;
    });
  }),
  setRequestLocale: vi.fn(),
}));

// Mock legalDocs to avoid fs/git calls in tests
vi.mock("@/lib/legalDocs", () => ({
  getLegalDocContent: vi.fn(
    (basename: string) =>
      `# ${basename === "privacy-policy" ? "Privacy Policy" : "Terms of Service"}\n\nTest content.`,
  ),
  getLegalDocDate: vi.fn(() => new Date("2026-04-20")),
}));

// Mock remark-gfm
vi.mock("remark-gfm", () => ({ default: () => {} }));

// Mock react-markdown to render children as plain text
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

// Mock next-intl navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

// Minimal wrapper to provide intl context
function IntlWrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Privacy page", () => {
  it("renders the Privacy Policy heading from i18n", async () => {
    const { default: PrivacyPage } =
      await import("@/app/[locale]/privacy/page");
    const jsx = await PrivacyPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(<IntlWrapper>{jsx}</IntlWrapper>);
    expect(
      screen.getByRole("heading", { name: /privacy policy/i }),
    ).toBeTruthy();
  });
});

describe("Terms page", () => {
  it("renders the Terms of Service heading from i18n", async () => {
    const { default: TermsPage } = await import("@/app/[locale]/terms/page");
    const jsx = await TermsPage({ params: Promise.resolve({ locale: "en" }) });
    render(<IntlWrapper>{jsx}</IntlWrapper>);
    expect(
      screen.getByRole("heading", { name: /terms of service/i }),
    ).toBeTruthy();
  });
});

// Verify that a localized file exists for every non-English locale so the
// legal pages never silently fall back to English for a translated locale.
const legalDir = join(process.cwd(), "public", "legal");
const nonEnglishLocales = [
  "ar",
  "de",
  "es",
  "fr",
  "hi",
  "it",
  "ko",
  "pt",
  "ru",
  "zh",
];

describe("Localized legal documents", () => {
  for (const locale of nonEnglishLocales) {
    it(`privacy-policy.${locale}.md exists`, () => {
      expect(existsSync(join(legalDir, `privacy-policy.${locale}.md`))).toBe(
        true,
      );
    });

    it(`terms-of-service.${locale}.md exists`, () => {
      expect(existsSync(join(legalDir, `terms-of-service.${locale}.md`))).toBe(
        true,
      );
    });
  }
});

// BITB-309: the policy must name OpenAI (moderation fallback) and state its
// 30-day abuse-monitoring retention honestly, in every language.
describe("privacy policy discloses OpenAI moderation (BITB-309)", () => {
  const allLocales = ["en", ...nonEnglishLocales];
  const OPENAI_URL = "https://openai.com/enterprise-privacy/";

  for (const locale of allLocales) {
    const file =
      locale === "en" ? "privacy-policy.md" : `privacy-policy.${locale}.md`;
    const raw = readFileSync(join(legalDir, file), "utf8");

    describe(locale, () => {
      it("has lastUpdated >= 2026-11-11", () => {
        const m = raw.match(/^lastUpdated:\s*(\d{4}-\d{2}-\d{2})\s*$/m);
        expect(m).not.toBeNull();
        expect(m![1] >= "2026-11-11").toBe(true);
      });

      it("links OpenAI privacy page in prose and table", () => {
        expect(raw.split(OPENAI_URL).length - 1).toBeGreaterThanOrEqual(2);
      });

      it("still links OpenRouter and Microsoft", () => {
        expect(raw).toContain("https://openrouter.ai/privacy");
        expect(raw).toContain("https://privacy.microsoft.com");
      });

      it("states the 30-day retention in the paragraph with the OpenAI link", () => {
        const paragraph = raw
          .split(/\n\s*\n/)
          .find((p) => p.includes(OPENAI_URL) && !p.startsWith("|"));
        expect(paragraph).toBeDefined();
        expect(paragraph).toContain("30");
      });

      it("has an OpenAI row in the third-party table", () => {
        expect(raw).toMatch(/^\|\s*OpenAI\s*\|/m);
      });
    });
  }

  it("en: the old blanket no-retention claim is gone", () => {
    const raw = readFileSync(join(legalDir, "privacy-policy.md"), "utf8");
    expect(raw).not.toContain("not retained by the provider beyond");
  });
});

// BITB-326: blocked messages ARE stored (up to 30 days) once capture is on, so the two
// "chat messages are not stored" bullets must carve them out in every language -- a
// blanket "not stored" next to a "blocked messages are kept" bullet is a contradiction.
describe("privacy policy carves blocked messages out of 'not stored' (BITB-326)", () => {
  const chatLabel: Record<string, string> = {
    en: "Chat messages",
    it: "Messaggi della chat",
    de: "Chat-Nachrichten",
    es: "Mensajes del chat",
    fr: "Messages de chat",
    pt: "Mensagens do chat",
    ru: "Сообщения в чате",
    zh: "聊天消息",
    ko: "채팅 메시지",
    ar: "رسائل الدردشة",
    hi: "चैट संदेश",
  };
  const blockedPhrase: Record<string, string> = {
    en: "blocked by our safety system",
    it: "bloccati dal nostro sistema di sicurezza",
    de: "Sicherheitssystem",
    es: "bloqueados por nuestro sistema de seguridad",
    fr: "bloqués par notre système de sécurité",
    pt: "bloqueadas pelo nosso sistema de segurança",
    ru: "заблокированных нашей системой безопасности",
    zh: "被我们的安全系统拦截",
    ko: "안전 시스템에 의해 차단된",
    ar: "يحجبها نظام السلامة لدينا",
    hi: "सुरक्षा प्रणाली",
  };

  for (const locale of Object.keys(chatLabel)) {
    const file =
      locale === "en" ? "privacy-policy.md" : `privacy-policy.${locale}.md`;
    const raw = readFileSync(join(legalDir, file), "utf8");
    // A bullet runs from "- **Label**" to the next bullet or blank line.
    const bullets = raw
      .split(/\n(?=- |\s*\n)/)
      .filter((b) => b.trimStart().startsWith(`- **${chatLabel[locale]}**`));

    it(`${locale}: both chat-message bullets name the blocked-message exception`, () => {
      expect(bullets).toHaveLength(2);
      for (const b of bullets) expect(b).toContain(blockedPhrase[locale]);
    });

    it(`${locale}: the GDPR rights section covers blocked-message records`, () => {
      // Once capture is on, "we collect no personally identifiable information, so clearing
      // local history fulfils most requests" is no longer the whole story.
      const rights = raw
        .split(/^## /m)
        .find(
          (sec) =>
            sec.includes("GDPR") ||
            sec.includes("RGPD") ||
            sec.includes("DSGVO") ||
            sec.includes("<privacy@voxquieta.org>"),
        );
      expect(rights).toBeDefined();
      expect(rights).toContain(blockedPhrase[locale]);
      expect(rights).toContain("30");
    });

    it(`${locale}: has lastUpdated >= 2026-11-16`, () => {
      const m = raw.match(/^lastUpdated:\s*(\d{4}-\d{2}-\d{2})\s*$/m);
      expect(m![1] >= "2026-11-16").toBe(true);
    });
  }
});

// BITB-329: feedback text, contact-form data and the SMTP2GO notification e-mails are stored /
// sent, so the policy must disclose them with the retention numbers (30 / 90 / 90 days) in every
// language. The backend test api/tests/test_feedback_retention.py ties the same numbers to the
// settings defaults.
describe("privacy policy discloses feedback, contact form and SMTP2GO (BITB-329)", () => {
  const feedbackLabel: Record<string, string> = {
    en: "Feedback",
    it: "Feedback",
    de: "Feedback",
    es: "Valoraciones y comentarios",
    fr: "Retours et évaluations",
    pt: "Feedback",
    ru: "Отзывы",
    zh: "反馈",
    ko: "피드백",
    ar: "الملاحظات",
    hi: "फ़ीडबैक",
  };
  const contactLabel: Record<string, string> = {
    en: "Contact form",
    it: "Modulo di contatto",
    de: "Kontaktformular",
    es: "Formulario de contacto",
    fr: "Formulaire de contact",
    pt: "Formulário de contato",
    ru: "обратной связи",
    zh: "联系表单",
    ko: "문의 양식",
    ar: "نموذج التواصل",
    hi: "संपर्क फ़ॉर्म",
  };
  const messageIdPhrase: Record<string, string> = {
    en: "message identifier",
    it: "identificativo del messaggio",
    de: "Nachrichten-ID",
    es: "identificador del mensaje",
    fr: "identifiant du message",
    pt: "identificador da mensagem",
    ru: "идентификатор сообщения",
    zh: "消息标识符",
    ko: "메시지 식별자",
    ar: "معرّف الرسالة",
    hi: "संदेश आईडी",
  };
  const identityPhrase: Record<string, string> = {
    en: "not linked to your identity",
    it: "alla tua identità",
    de: "deiner Identität",
    es: "a tu identidad",
    fr: "votre identité",
    pt: "à sua identidade",
    ru: "вашей личностью",
    zh: "您的身份",
    ko: "귀하의 신원",
    ar: "بهويتك",
    hi: "आपकी पहचान",
  };
  // The 30 / 90 day numbers as the policy quotes them, per language (digits + unit).
  const SMTP2GO_URL = "https://www.smtp2go.com/privacy/";

  for (const locale of Object.keys(feedbackLabel)) {
    const file =
      locale === "en" ? "privacy-policy.md" : `privacy-policy.${locale}.md`;
    const raw = readFileSync(join(legalDir, file), "utf8");
    const bullets = (label: string) =>
      raw
        .split(/\n(?=- |\s*\n)/)
        .filter((b) => b.trimStart().startsWith(`- **${label}**`));

    describe(locale, () => {
      it("feedback bullets (collected + retention) state 30 and 90 days", () => {
        const found = bullets(feedbackLabel[locale]);
        expect(found).toHaveLength(2);
        for (const b of found) {
          expect(b).toMatch(/(?<!\d)30(?!\d)/);
          expect(b).toMatch(/(?<!\d)90(?!\d)/);
          expect(b).toContain(messageIdPhrase[locale]);
        }
      });

      it("contact-form bullets (collected + retention) state 90 days", () => {
        // Collected bullet ("Contact form") and retention bullet ("Contact form messages").
        const found = raw.split(/\n(?=- |\s*\n)/).filter((b) => {
          const m = b.trimStart().match(/^- \*\*([^*]+)\*\*/);
          return (
            m !== null &&
            m[1].toLowerCase().includes(contactLabel[locale].toLowerCase())
          );
        });
        expect(found).toHaveLength(2);
        for (const b of found) expect(b).toMatch(/(?<!\d)90(?!\d)/);
      });

      it("carves the contact-form email out of 'we do not collect email'", () => {
        // The "we do not collect your email" bullet is a plain (non-bold) bullet; it must now
        // name the contact form as the exception.
        const stem = contactLabel[locale].toLowerCase();
        const lines = raw.split("\n").filter((l) => l.startsWith("- "));
        const carveOut = lines.filter(
          (l) => !l.startsWith("- **") && l.toLowerCase().includes(stem),
        );
        expect(carveOut.length).toBeGreaterThanOrEqual(1);
      });

      it("has an SMTP2GO row in the third-party table linking its privacy page", () => {
        const row = raw.split("\n").find((l) => /^\|\s*SMTP2GO\s*\|/.test(l));
        expect(row).toBeDefined();
        expect(row).toContain(SMTP2GO_URL);
      });

      it("GDPR section: feedback/contact data are findable and deletable; blocked records are 'not linked to your identity'", () => {
        const rights = raw
          .split(/^## /m)
          .find(
            (sec) =>
              sec.includes("GDPR") ||
              sec.includes("RGPD") ||
              sec.includes("DSGVO"),
          );
        expect(rights).toBeDefined();
        expect(rights).toContain(messageIdPhrase[locale]);
        expect(rights).toContain(identityPhrase[locale]);
      });

      it("has lastUpdated >= 2026-11-16", () => {
        const m = raw.match(/^lastUpdated:\s*(\d{4}-\d{2}-\d{2})\s*$/m);
        expect(m![1] >= "2026-11-16").toBe(true);
      });
    });
  }
});
