import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import CrisisResourcesCard, { dialableNumber } from "./CrisisResourcesCard";
import { renderWithIntl, renderWithIntlLocale } from "@/test/i18n-helpers";
import { crisisFixture } from "@/test/crisisFixtures";
import { getCrisisRegionOverride } from "@/lib/crisisRegion";
import enMessages from "../../messages/en.json";
import { NextIntlClientProvider } from "next-intl";
import arMessages from "../../messages/ar.json";
import itMessages from "../../messages/it.json";

describe("CrisisResourcesCard (BITB-251)", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders as an alert with the heading", () => {
    renderWithIntl(<CrisisResourcesCard resources={crisisFixture} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(enMessages.Crisis.heading);
    expect(alert).toHaveAttribute("dir", "ltr");
  });

  it("renders the emergency number as a prominent tel: link", () => {
    renderWithIntl(<CrisisResourcesCard resources={crisisFixture} />);
    const link = screen.getByRole("link", { name: /Emergency number: 112/ });
    expect(link).toHaveAttribute("href", "tel:112");
  });

  it("strips spaces, dashes and parentheses from tel:/sms: hrefs", () => {
    expect(dialableNumber("+39 02 2327 2327")).toBe("+390223272327");
    expect(dialableNumber("(116) 123")).toBe("116123");
    expect(dialableNumber("1-800-273-8255")).toBe("18002738255");
    renderWithIntl(<CrisisResourcesCard resources={crisisFixture} />);
    expect(
      screen.getByRole("link", { name: "Call Telefono Amico" }),
    ).toHaveAttribute("href", "tel:+390223272327");
    expect(
      screen.getByRole("link", { name: "Text Telefono Amico" }),
    ).toHaveAttribute("href", "sms:+393240117252");
    expect(
      screen.getByRole("link", { name: "Call Samaritans" }),
    ).toHaveAttribute("href", "tel:116123");
  });

  it("omits text/call links a line does not have, and shows hours + url", () => {
    renderWithIntl(<CrisisResourcesCard resources={crisisFixture} />);
    expect(screen.queryByRole("link", { name: "Text Samaritans" })).toBeNull();
    expect(screen.getByText("10:00-24:00")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /telefonoamico\.it/ }),
    ).toHaveAttribute("href", "https://www.telefonoamico.it");
  });

  it("links to findahelpline.com", () => {
    renderWithIntl(<CrisisResourcesCard resources={crisisFixture} />);
    expect(
      screen.getByRole("link", { name: enMessages.Crisis.international }),
    ).toHaveAttribute("href", "https://findahelpline.com");
  });

  it("renders without an emergency number or lines (international only)", () => {
    renderWithIntl(
      <CrisisResourcesCard
        resources={{
          ...crisisFixture,
          country: null,
          country_source: "none",
          emergency: null,
          lines: [],
        }}
      />,
    );
    expect(screen.queryByRole("link", { name: /Emergency/ })).toBeNull();
    expect(
      screen.getByRole("button", { name: enMessages.Crisis.chooseCountry }),
    ).toBeInTheDocument();
  });

  it("is right-to-left for Arabic", () => {
    render(
      <NextIntlClientProvider locale="ar" messages={arMessages}>
        <CrisisResourcesCard resources={crisisFixture} />
      </NextIntlClientProvider>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("dir", "rtl");
    expect(alert).toHaveTextContent(arMessages.Crisis.heading);
  });

  it("uses localized strings (it)", () => {
    renderWithIntlLocale(
      <CrisisResourcesCard resources={crisisFixture} />,
      "it",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      itMessages.Crisis.heading,
    );
    expect(
      screen.getByRole("link", { name: "Chiama Telefono Amico" }),
    ).toBeInTheDocument();
  });

  it("opens a country picker, stores the override and notifies", () => {
    const onRegionChange = vi.fn();
    renderWithIntl(
      <CrisisResourcesCard
        resources={crisisFixture}
        onRegionChange={onRegionChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Not in Italy?" }));
    const select = screen.getByLabelText(enMessages.Crisis.chooseCountry);
    const options = within(select).getAllByRole("option");
    expect(options.map((o) => o.getAttribute("value"))).toEqual(
      expect.arrayContaining(["AR", "AT", "IT", "US"]),
    );
    fireEvent.change(select, { target: { value: "AT" } });
    expect(getCrisisRegionOverride()).toBe("AT");
    expect(onRegionChange).toHaveBeenCalledWith("AT");
    expect(screen.getByRole("status")).toHaveTextContent("Austria");
  });
});
