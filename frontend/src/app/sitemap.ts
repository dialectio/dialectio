import type { MetadataRoute } from "next";
import { connection } from "next/server";

import { INFO_PAGES } from "@/components/InfoPage";
import { routing } from "@/i18n/routing";
import { listConceptLinks, listDialects, listDialectWords, SITE_URL } from "@/lib/api";

function alternates(path: string) {
  return {
    languages: Object.fromEntries(routing.locales.map((l) => [l, `${SITE_URL}/${l}${path}`])),
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  await connection(); // needs the API: render per request, not at build time
  const [concepts, dialects, dialectWords] = await Promise.all([
    listConceptLinks(),
    listDialects(),
    listDialectWords(),
  ]);
  const paths = [
    "",
    ...INFO_PAGES.map((page) => `/${page}`),
    ...dialects.filter((d) => d.kind === "dialect").map((d) => `/dialects/${d.code}`),
    ...concepts.map((c) => `/word/${c.slug}`),
    ...dialectWords.map((word) => `/slovo/${encodeURIComponent(word)}`),
  ];

  return paths.flatMap((path) =>
    routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      alternates: alternates(path),
    })),
  );
}
