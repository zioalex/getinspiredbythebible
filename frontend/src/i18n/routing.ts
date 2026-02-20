import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "it", "de", "es", "fr", "pt", "ar"],
  defaultLocale: "en",
  localePrefix: "always",
});
