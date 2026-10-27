/**
 * What a visitor sees first, by the interface language and the browser's region: the regional
 * words of their own language on the home page and in the check game, their country first in
 * "where do you live?". Nothing is looked up from the IP address.
 */

/** Whose regional words a visitor of each interface language sees first. Polish visitors
 * get Ukrainian dialects (no Polish regional words yet). */
export const LOCALE_DIALECTS: Record<string, string> = {
  uk: "ukr",
  pl: "ukr",
  en: "eng",
  de: "deu",
  es: "spa",
  fr: "fra",
};

/** Where those regional words are spoken: [west, south, east, north]. */
export const DIALECT_BOUNDS: Record<string, number[]> = {
  ukr: [19, 44, 41, 53], // Ukraine and its neighbours
  deu: [5, 45.5, 17.5, 55.2], // Germany, Austria, Switzerland
  eng: [-125, 24, 2, 59], // the United States and Britain
  spa: [-118, -56, 4, 44], // Spain and Latin America
  fra: [-80, 41, 11, 52], // France, Belgium, Switzerland and Quebec
  ita: [6, 36, 19, 47.5], // Italy
  pol: [14, 49, 24.2, 55], // Poland
  por: [-74, -34, -6, 43], // Portugal and Brazil
};

/** The dialect language of the interface language, Ukrainian by default. */
export function dialectLanguage(locale: string): string {
  return LOCALE_DIALECTS[locale] ?? "ukr";
}

// The browser language's region ("de-AT") -> our country code ("AUT")
const REGION_COUNTRIES: Record<string, string> = {
  UA: "UKR",
  PL: "POL",
  DE: "DEU",
  AT: "AUT",
  CH: "CHE",
  FR: "FRA",
  BE: "BEL",
  CA: "CAN",
  ES: "ESP",
  MX: "MEX",
  AR: "ARG",
  CL: "CHL",
  CO: "COL",
  PE: "PER",
  VE: "VEN",
  US: "USA",
  GB: "GBR",
  IE: "IRL",
  IT: "ITA",
  NL: "NLD",
  SK: "SVK",
  RO: "ROU",
  CZ: "CZE",
  PT: "PRT",
  BR: "BRA",
  AU: "AUS",
  NZ: "NZL",
  UY: "URY",
  PY: "PRY",
  BO: "BOL",
  EC: "ECU",
  CU: "CUB",
  DO: "DOM",
  PR: "PRI",
  GT: "GTM",
  HN: "HND",
  SV: "SLV",
  NI: "NIC",
  CR: "CRI",
  PA: "PAN",
};
// Without a region in the browser language, the country most visitors of a locale live in
const LOCALE_COUNTRIES: Record<string, string> = {
  uk: "UKR",
  pl: "POL",
  de: "DEU",
  fr: "FRA",
  es: "ESP",
  en: "GBR",
};

/** The visitor's likely country (browser only): "de-AT" -> "AUT", else by the locale. */
export function visitorCountry(locale: string): string | null {
  if (typeof navigator !== "undefined") {
    for (const language of navigator.languages ?? [navigator.language]) {
      const region = language.split("-")[1]?.toUpperCase();
      if (region && REGION_COUNTRIES[region]) return REGION_COUNTRIES[region];
    }
  }
  return LOCALE_COUNTRIES[locale] ?? null;
}
