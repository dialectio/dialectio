/** The project's own pages, in the order the menus list them. */
export const INFO_PAGES = [
  "dialects",
  "check",
  "community",
  "false-friends",
  "about",
  "sources",
  "support",
  "privacy",
  "terms",
  "imprint",
] as const;

export type InfoPage = (typeof INFO_PAGES)[number];

/** The header has room only for these; the legal pages are linked from footers and panels. */
export const HEADER_PAGES = INFO_PAGES.slice(0, 5);

/** Pages only Ukrainian-interface visitors get in the menus (false friends are with
 * Ukrainian); the pages themselves stay open to everyone. */
const UKRAINIAN_ONLY: readonly InfoPage[] = ["false-friends"];

/** The menu pages for an interface language; `limit` keeps the header short. */
export function menuPages(locale: string, pages: readonly InfoPage[] = INFO_PAGES) {
  const shown = INFO_PAGES.filter(
    (page) => locale === "uk" || !UKRAINIAN_ONLY.includes(page),
  );
  return pages === HEADER_PAGES
    ? shown.slice(0, HEADER_PAGES.length)
    : shown.filter((page) => pages.includes(page));
}
