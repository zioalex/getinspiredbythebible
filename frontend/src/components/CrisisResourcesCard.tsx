"use client";

import { useId, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Phone, MessageSquare, ExternalLink, LifeBuoy } from "lucide-react";
import type { CrisisResources } from "@/lib/api";
import { setCrisisRegionOverride } from "@/lib/crisisRegion";

/**
 * BITB-251: deterministic emergency / crisis contacts, rendered ABOVE the
 * assistant reply on self-harm and threat-to-others turns. The server picks
 * the contacts by the caller's country; a "Not in {country}?" picker lets a
 * VPN user or traveller correct it (stored on this device only, sent as
 * `region_override` on the next request).
 */

const RTL_LOCALES = new Set(["ar"]);

/** Strip spaces, dashes, dots and parentheses; keep digits and a leading +. */
export function dialableNumber(raw: string): string {
  return raw.replace(/[\s\-.()]/g, "");
}

function countryName(code: string, locale: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

interface CrisisResourcesCardProps {
  resources: CrisisResources;
  /**
   * Called after the user picks a different country (override saved). May return
   * a promise resolving to `true` when the card was re-rendered with the new
   * country's numbers; any other result (false / void / rejection) shows the
   * "from your next message" note instead.
   */
  onRegionChange?: (region: string) => Promise<boolean> | boolean | void;
}

export default function CrisisResourcesCard({
  resources,
  onRegionChange,
}: CrisisResourcesCardProps) {
  const t = useTranslations("Crisis");
  const locale = useLocale();
  const pickerId = useId();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [chosen, setChosen] = useState<string | null>(null);

  const dir = RTL_LOCALES.has(locale) ? "rtl" : "ltr";
  const shownCountry = chosen ?? resources.country;
  const linkClass =
    "inline-flex min-h-[44px] items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-red-900 underline underline-offset-2 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-700 dark:text-red-100 dark:hover:bg-red-900";

  const handlePick = async (code: string) => {
    if (!code) return;
    setCrisisRegionOverride(code);
    setPickerOpen(false);
    let updated = false;
    try {
      updated = (await onRegionChange?.(code)) === true;
    } catch {
      updated = false;
    }
    // On success the parent swapped `resources`, so the card already shows the
    // new numbers; otherwise keep the old card and say when the pick takes effect.
    if (!updated) setChosen(code);
  };

  return (
    <section
      role="alert"
      dir={dir}
      lang={locale}
      data-testid="crisis-resources-card"
      className="mb-3 rounded-xl border border-red-300 bg-red-50 p-4 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100"
    >
      <h2 className="flex items-start gap-2 text-base font-semibold">
        <LifeBuoy className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <span>{t("heading")}</span>
      </h2>

      {!resources.emergency && (
        <p
          className="mt-3 text-sm font-medium"
          data-testid="crisis-local-emergency"
        >
          {t.rich("localEmergencyHint", {
            dial: (chunks) => (
              <a
                href="tel:112"
                className="inline-flex min-h-[44px] items-center px-1 font-bold underline underline-offset-2"
              >
                <bdi>{chunks}</bdi>
              </a>
            ),
          })}
        </p>
      )}

      {resources.emergency && (
        <a
          href={`tel:${dialableNumber(resources.emergency.number)}`}
          aria-label={`${t("emergencyLabel")}: ${resources.emergency.number}`}
          className="mt-3 flex min-h-[48px] items-center justify-center gap-2 rounded-lg bg-red-700 px-4 py-3 text-lg font-bold text-white hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-900 focus-visible:ring-offset-2"
        >
          <Phone className="h-5 w-5" aria-hidden="true" />
          <span>
            {t("emergencyLabel")}: <bdi>{resources.emergency.number}</bdi>
          </span>
        </a>
      )}

      {resources.lines.length > 0 && (
        <ul className="mt-3 space-y-3">
          {resources.lines.map((line, i) => (
            <li
              key={`${line.name}-${i}`}
              className="rounded-lg border border-red-200 bg-white p-3 text-gray-900 dark:border-red-800 dark:bg-gray-900 dark:text-gray-100"
            >
              <p className="font-medium">{line.name}</p>
              {line.hours && (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  {line.hours}
                </p>
              )}
              <div className="mt-1 flex flex-wrap gap-1">
                {line.phone && (
                  <a
                    href={`tel:${dialableNumber(line.phone)}`}
                    aria-label={t("callLineAria", { name: line.name })}
                    className={linkClass}
                  >
                    <Phone className="h-4 w-4" aria-hidden="true" />
                    <span>
                      {t("call")} <bdi>{line.phone}</bdi>
                    </span>
                  </a>
                )}
                {line.sms && (
                  <a
                    href={`sms:${dialableNumber(line.sms)}`}
                    aria-label={t("textLineAria", { name: line.name })}
                    className={linkClass}
                  >
                    <MessageSquare className="h-4 w-4" aria-hidden="true" />
                    <span>
                      {t("text")} <bdi>{line.sms}</bdi>
                    </span>
                  </a>
                )}
                {line.url && (
                  <a
                    href={line.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={linkClass}
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    <span>
                      <bdi>{line.url.replace(/^https?:\/\//, "")}</bdi>
                    </span>
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1">
        <a
          href={resources.international_url}
          target="_blank"
          rel="noopener noreferrer"
          className={linkClass}
        >
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
          <span>{t("international")}</span>
        </a>
        {resources.available_countries.length > 0 && (
          <button
            type="button"
            onClick={() => setPickerOpen((open) => !open)}
            aria-expanded={pickerOpen}
            aria-controls={pickerId}
            className={linkClass}
          >
            {shownCountry
              ? t("notInCountry", {
                  country: countryName(shownCountry, locale),
                })
              : t("chooseCountry")}
          </button>
        )}
      </div>

      {pickerOpen && (
        <div id={pickerId} className="mt-2">
          <label
            htmlFor={`${pickerId}-select`}
            className="mb-1 block text-sm font-medium"
          >
            {t("chooseCountry")}
          </label>
          <select
            id={`${pickerId}-select`}
            defaultValue=""
            onChange={(e) => handlePick(e.target.value)}
            className="min-h-[44px] w-full rounded-lg border border-red-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-red-700 dark:bg-gray-900 dark:text-gray-100"
          >
            <option value="" disabled>
              {t("chooseCountry")}
            </option>
            {resources.available_countries
              .map((code) => ({ code, name: countryName(code, locale) }))
              .sort((a, b) => a.name.localeCompare(b.name, locale))
              .map(({ code, name }) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
          </select>
        </div>
      )}

      {chosen && (
        <p className="mt-2 text-sm" role="status">
          {t("regionSaved", { country: countryName(chosen, locale) })}
        </p>
      )}
    </section>
  );
}
