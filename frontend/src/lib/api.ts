import type { FeatureCollection, Point } from "geojson";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
/** API address for server-side rendering (can be an internal URL in production). */
const SERVER_API_URL = process.env.API_INTERNAL_URL || API_URL;
/** Public address of the site, used for canonical URLs and the sitemap. */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
/** How long server-rendered pages may reuse API data, in seconds (the page also refreshes
 * its data in the browser, so visitors see edits right away; this mainly bounds staleness
 * for search engines). */
const SERVER_REVALIDATE = 300;

export type ConceptSummary = {
  id: number;
  wikidata_id: string | null;
  slug: string | null;
  gloss_en: string;
  gloss_uk: string | null;
  description_en: string | null;
  description_uk: string | null;
};

export type SearchHit = {
  concept: ConceptSummary;
  matched_spelling: string;
  matched_language_en: string;
  matched_language_uk: string | null;
};

export type Audio = {
  url: string;
  license: string;
  speaker: string | null;
  is_synthetic: boolean;
};

export type Form = {
  id: number;
  spelling: string;
  ipa: string | null;
  transliteration: string | null;
  is_primary: boolean;
  external_id: string | null;
  source: string | null;
  /** Not checked by a person or a dictionary: shown as possibly inaccurate. */
  unverified: boolean;
  /** Visitors' "do people say it like this?" votes */
  votes_yes: number;
  votes_no: number;
  /** "confirmed" by speakers' votes, or "disputed" */
  community: "confirmed" | "disputed" | null;
  audio: Audio[];
};

export type LanguageForms = {
  variety_id: number;
  /** "ukr", or a dialect like "ukr-hutsul" */
  code: string;
  kind: "language" | "dialect_group" | "dialect";
  parent_code: string | null;
  iso639_3: string | null;
  name_en: string;
  name_uk: string | null;
  region_codes: string[];
  forms: Form[];
};

export type LabelProps = {
  code: string;
  /** "country", or "adm1" for first-level regions (oblasts) shown when zoomed in */
  level: "country" | "adm1";
  parent_code: string | null;
  /** The label shows dialect words */
  dialect: boolean;
  text: string;
  name_en: string;
  name_uk: string | null;
  /** Label importance, lower = more important; labels arrive sorted by it. */
  rank: number;
};

export type ConceptDetail = ConceptSummary & {
  languages: LanguageForms[];
  labels: FeatureCollection<Point, LabelProps>;
  /** Other word pages to link to */
  related?: ConceptLink[];
};

/** UI locale -> ISO 639-3 code used to break ties between identical spellings. */
export const LOCALE_LANGUAGE: Record<string, string> = { uk: "ukr", en: "eng" };

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

export function searchWords(q: string, locale: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ q, prefer: LOCALE_LANGUAGE[locale] ?? "eng" });
  return getJson<SearchHit[]>(`/api/search?${params}`, signal);
}

export function getConcept(id: number, signal?: AbortSignal) {
  return getJson<ConceptDetail>(`/api/concepts/${id}`, signal);
}

export type ConceptLink = { slug: string; gloss_en: string; gloss_uk: string | null };

async function getServerJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${SERVER_API_URL}${path}`, {
    next: { revalidate: SERVER_REVALIDATE },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

/** Server-side: concept page data, or null when the slug does not exist. */
export function getConceptBySlug(slug: string) {
  return getServerJson<ConceptDetail>(`/api/concepts/by-slug/${encodeURIComponent(slug)}`);
}

/** Server-side: every concept that has a page. */
export async function listConceptLinks() {
  return (await getServerJson<ConceptLink[]>("/api/concepts")) ?? [];
}

/** First letter in upper case: "гуцульський говір" -> "Гуцульський говір" (for headings). */
export function capitalize(text: string): string {
  return text.charAt(0).toLocaleUpperCase() + text.slice(1);
}

/** Pick the Ukrainian or English variant of a localized field pair. */
export function localized(locale: string, en: string, uk: string | null): string;
export function localized(locale: string, en: string | null, uk: string | null): string | null;
export function localized(locale: string, en: string | null, uk: string | null) {
  return locale === "uk" ? (uk ?? en) : (en ?? uk);
}

export type SourceStats = {
  name: string;
  url: string | null;
  license: string;
  words: number;
  recordings: number;
};

export type Stats = {
  concepts: number;
  languages: number;
  dialects: number;
  words: number;
  recordings: number;
  synthetic_recordings: number;
  sources: SourceStats[];
};

/** Server-side: site-wide numbers and data sources. */
export function getStats() {
  return getServerJson<Stats>("/api/stats");
}

export type FeaturedConcept = ConceptLink & { id: number; examples: string[] };

/** Server-side: concepts with the most different dialect words (home page). */
export async function listFeaturedConcepts(limit = 12) {
  return (await getServerJson<FeaturedConcept[]>(`/api/concepts/featured?limit=${limit}`)) ?? [];
}

export type DialectSummary = {
  code: string;
  kind: "dialect_group" | "dialect";
  name_en: string;
  name_uk: string | null;
  parent_code: string | null;
  words: number;
  region_codes: string[];
};

export type DialectWord = {
  slug: string;
  gloss_en: string;
  gloss_uk: string | null;
  spelling: string;
  /** The standard Ukrainian word for the same concept */
  standard: string | null;
  unverified: boolean;
  has_audio: boolean;
};

export type DialectDetail = DialectSummary & {
  parent_name_en: string | null;
  parent_name_uk: string | null;
  regions: { code: string; name_en: string; name_uk: string | null; lon: number; lat: number }[];
  /** [west, south, east, north] */
  bounds: number[] | null;
  words_list: DialectWord[];
};

/** Server-side: all dialect groups and dialects. */
export async function listDialects() {
  return (await getServerJson<DialectSummary[]>("/api/dialects")) ?? [];
}

/** Server-side: a dialect page, or null when the code does not exist. */
export function getDialect(code: string) {
  return getServerJson<DialectDetail>(`/api/dialects/${encodeURIComponent(code)}`);
}

export type DialectRef = { code: string; name_en: string; name_uk: string | null };

export type DialectWordMeaning = {
  slug: string;
  gloss_en: string;
  gloss_uk: string | null;
  standard: string | null;
  dialects: DialectRef[];
  unverified: boolean;
  audio: Audio[];
  /** Other dialect words for the same concept */
  others: { word: string; dialects: DialectRef[] }[];
};

export type DialectWordDetail = {
  word: string;
  meanings: DialectWordMeaning[];
  regions: DialectDetail["regions"];
  bounds: number[] | null;
};

/** What a dialect word means for the reader: the standard Ukrainian word, or English. */
export function meaningOf(meaning: DialectWordMeaning, locale: string): string {
  return locale === "uk"
    ? (meaning.standard ?? meaning.gloss_uk ?? meaning.gloss_en)
    : meaning.gloss_en;
}

/** Server-side: every dialect word that has a page. */
export async function listDialectWords() {
  return (await getServerJson<string[]>("/api/dialect-words")) ?? [];
}

/** Server-side: a dialect word page, or null when the word is unknown. */
export function getDialectWord(word: string) {
  return getServerJson<DialectWordDetail>(`/api/dialect-words/${encodeURIComponent(word)}`);
}
