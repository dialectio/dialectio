/** The project's own pages, in the order the menus list them. */
export const INFO_PAGES = [
  "dialects",
  "check",
  "community",
  "false-friends",
  "about",
  "sources",
  "privacy",
  "terms",
  // "imprint" comes back with the German version, once the site has its address
] as const;

/** The header has room only for these; the legal pages are linked from footers and panels. */
export const HEADER_PAGES = INFO_PAGES.slice(0, 5);
