import { defineRouting } from "next-intl/routing";

// German ("de", messages/de.json) is switched off until the site has an Impressum (§5 DDG
// requires a postal address); /de/... redirects to English meanwhile (src/proxy.ts).
export const routing = defineRouting({
  locales: ["uk", "en", "pl", "es", "fr"],
  defaultLocale: "uk",
});
