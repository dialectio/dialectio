import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["uk", "en", "pl", "de", "es", "fr"],
  defaultLocale: "uk",
});
