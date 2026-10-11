import type { MetadataRoute } from "next";

import { INFO_PAGES } from "@/components/InfoPage";
import { routing } from "@/i18n/routing";
import { listConceptLinks, listDialects, SITE_URL } from "@/lib/api";

// Rebuild the sitemap at most once an hour.
export const revalidate = 3600;

function alternates(path: string) {
  return {
    languages: Object.fromEntries(routing.locales.map((l) => [l, `${SITE_URL}/${l}${path}`])),
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [concepts, dialects] = await Promise.all([listConceptLinks(), listDialects()]);
  const paths = [
    "",
    ...INFO_PAGES.map((page) => `/${page}`),
    ...dialects.filter((d) => d.kind === "dialect").map((d) => `/dialects/${d.code}`),
    ...concepts.map((c) => `/word/${c.slug}`),
  ];

  return paths.flatMap((path) =>
    routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      alternates: alternates(path),
    })),
  );
}
