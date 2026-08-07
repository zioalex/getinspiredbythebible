import { act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";
import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import AppInstallCta from "./AppInstallCta";

const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";

const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36";

const props = {
  iconAlt: "Vox Quieta app icon",
  ctaSub: "Free on Android",
  ctaButton: "Get it on Google Play",
  iosCtaTitle: "Add Vox Quieta to your Home Screen",
  iosCtaBody: 'Tap the Share button, then choose "Add to Home Screen."',
  iosCtaSub: "Free, no account needed",
  playStoreUrl: "https://play.google.com/store/apps/details?id=test",
};

function setUserAgent(userAgent: string) {
  Object.defineProperty(window.navigator, "userAgent", {
    value: userAgent,
    configurable: true,
  });
}

describe("AppInstallCta", () => {
  afterEach(() => {
    setUserAgent("");
  });

  it("renders the Play Store CTA on first render for an Android user agent, and it stays put after effects flush", async () => {
    setUserAgent(ANDROID_UA);

    render(<AppInstallCta {...props} />);

    expect(screen.getByText(props.ctaButton)).toBeInTheDocument();
    expect(screen.queryByText(props.iosCtaTitle)).not.toBeInTheDocument();

    // Give any pending effects a chance to flush, then confirm nothing
    // changed — it should never flash to the iOS text.
    await waitFor(() => {
      expect(screen.getByText(props.ctaButton)).toBeInTheDocument();
    });
    const link = screen.getByText(props.ctaButton).closest("a");
    expect(link).toHaveAttribute("href", props.playStoreUrl);
    expect(screen.queryByText(props.iosCtaTitle)).not.toBeInTheDocument();
  });

  it("swaps to the iOS Add to Home Screen instructions after mount for an iPhone user agent", async () => {
    setUserAgent(IPHONE_UA);

    render(<AppInstallCta {...props} />);

    await waitFor(() => {
      expect(screen.getByText(props.iosCtaTitle)).toBeInTheDocument();
    });
    expect(screen.getByText(props.iosCtaBody)).toBeInTheDocument();
    expect(screen.getByText(props.iosCtaSub)).toBeInTheDocument();
    expect(screen.queryByText(props.ctaButton)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /google play/i }),
    ).not.toBeInTheDocument();
  });

  // These two cases exercise the actual SSR -> hydrate handoff (rather than
  // client-only `render()`, whose act() wrapper flushes the mount effect
  // before returning and so can't observe a pre-effect DOM state). A real
  // server never sees `navigator`, so it always emits the `isIOS === false`
  // (Play Store) markup; hydrating that same markup on a client whose UA
  // *is* an iPhone is exactly the case that would warn if the default state
  // did not match the server output.
  for (const [label, userAgent] of [
    ["iPhone", IPHONE_UA],
    ["Android", ANDROID_UA],
  ] as const) {
    it(`hydrates cleanly with no mismatch warning for a ${label} user agent (SSR-safe default)`, async () => {
      setUserAgent(userAgent);

      const consoleError = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});

      // What a real server would send: no `navigator`, so `isIOS` starts
      // (and stays, server-side) `false`.
      const html = renderToString(<AppInstallCta {...props} />);
      expect(html).toContain(props.ctaButton);
      expect(html).not.toContain(props.iosCtaTitle);

      const container = document.createElement("div");
      container.innerHTML = html;
      document.body.appendChild(container);

      act(() => {
        hydrateRoot(container, <AppInstallCta {...props} />);
      });

      const hydrationWarnings = consoleError.mock.calls.filter(([msg]) =>
        typeof msg === "string" ? /hydrat/i.test(msg) : false,
      );
      expect(hydrationWarnings).toEqual([]);
      consoleError.mockRestore();

      if (label === "iPhone") {
        await waitFor(() => {
          expect(
            within(container).getByText(props.iosCtaTitle),
          ).toBeInTheDocument();
        });
      } else {
        await waitFor(() => {
          expect(
            within(container).getByText(props.ctaButton),
          ).toBeInTheDocument();
        });
        expect(
          within(container).queryByText(props.iosCtaTitle),
        ).not.toBeInTheDocument();
      }

      document.body.removeChild(container);
    });
  }
});
