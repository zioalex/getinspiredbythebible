import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import enMessages from "../../../../messages/en.json";
import deMessages from "../../../../messages/de.json";
import arMessages from "../../../../messages/ar.json";

const catalogs: Record<string, typeof enMessages> = {
  en: enMessages,
  de: deMessages,
  ar: arMessages,
};

vi.mock("next-intl/server", () => ({
  setRequestLocale: vi.fn(),
  getTranslations: vi.fn(
    async ({
      locale,
      namespace,
    }: {
      locale: string;
      namespace: keyof typeof enMessages;
    }) => {
      const ns = catalogs[locale][namespace] as Record<string, string>;
      return (key: string) => ns[key];
    },
  ),
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
}));

import AboutPage from "./page";

describe("About page", () => {
  it("renders the title and hero lead from i18n", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    expect(
      screen.getByRole("heading", { name: enMessages.About.title, level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(enMessages.About.heroLead)).toBeInTheDocument();
  });

  it("links out to the ai4you.sh origin post", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const link = screen.getByText(enMessages.About.fullStoryLinkLabel);
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "https://ai4you.sh/posts/Building-Something-That-Matters-How-Claude-Code-Helped-Me-Create-a-Bible-Inspiration-Chatbot/",
    );
  });

  it("links to the GitHub repo", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const link = screen.getByText(enMessages.About.builtLinkLabel);
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "https://github.com/zioalex/getinspiredbythebible",
    );
  });

  it("offers a mailto contact link", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const link = screen.getByText(enMessages.About.contactLinkLabel);
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "mailto:contact@voxquieta.org",
    );
  });

  it("states plainly what the app is not", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    expect(screen.getByText(enMessages.About.notBody)).toBeInTheDocument();
  });

  it("renders the opening hook as its own beat", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    expect(screen.getByText(enMessages.About.whyHook)).toBeInTheDocument();
  });

  it("renders the origin-era screenshot with a labeled caption", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const img = screen.getByAltText(enMessages.About.originScreenshotAlt);
    expect(img).toHaveAttribute("src", "/about/origin-welcome-screen.png");
    expect(
      screen.getByText(enMessages.About.originScreenshotCaption),
    ).toBeInTheDocument();
  });

  it("renders the closing personal beat before the contact section", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    expect(screen.getByText(enMessages.About.closingBody)).toBeInTheDocument();
  });

  it("signs the closing beat with the author's name", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    expect(
      screen.getByText(enMessages.About.closingSignature),
    ).toBeInTheDocument();
  });

  it.each(["en", "de", "ar"])(
    "renders the localized title for /%s",
    async (locale) => {
      const jsx = await AboutPage({ params: Promise.resolve({ locale }) });
      render(jsx);

      expect(
        screen.getByRole("heading", {
          name: catalogs[locale].About.title,
          level: 1,
        }),
      ).toBeInTheDocument();
    },
  );
});

describe("About page support section", () => {
  it.each(["en", "de", "ar"])(
    "renders the localized support heading and body for /%s",
    async (locale) => {
      const jsx = await AboutPage({ params: Promise.resolve({ locale }) });
      render(jsx);

      expect(
        screen.getByRole("heading", {
          name: catalogs[locale].About.supportTitle,
          level: 2,
        }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(catalogs[locale].About.supportBody),
      ).toBeInTheDocument();
    },
  );

  it("links out to the donate page with the web-about ref", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const link = screen
      .getByText(enMessages.About.supportLinkLabel)
      .closest("a");
    expect(link).toHaveAttribute(
      "href",
      "https://ko-fi.com/voxquieta?ref=web-about",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("places the support section before the Contact section", async () => {
    const jsx = await AboutPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const support = screen.getByRole("heading", {
      name: enMessages.About.supportTitle,
    });
    const contact = screen.getByRole("heading", {
      name: enMessages.About.contactTitle,
    });
    expect(
      support.compareDocumentPosition(contact) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
