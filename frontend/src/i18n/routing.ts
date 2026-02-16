import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "it", "de"],
  defaultLocale: "en",
  localePrefix: "always",
});
