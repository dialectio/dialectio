import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import DialectView from "@/components/DialectView";
import { capitalize, getDialect, localized } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

const DESCRIPTION_EXAMPLES = 4;

// generateMetadata and the page both need the dialect; fetch it once per request.
const loadDialect = cache(getDialect);

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/dialects/[code]">): Promise<Metadata> {
  const { locale, code } = await params;
  const dialect = await loadDialect(code);
  if (!dialect) return {};
  const t = await getTranslations({ locale, namespace: "Dialects" });
  const name = capitalize(localized(locale, dialect.name_en, dialect.name_uk));
  const examples = dialect.words_list
    .filter((w) => w.standard)
    .slice(0, DESCRIPTION_EXAMPLES)
    .map((w) => `${w.spelling} — ${w.standard}`)
    .join(", ");
  return pageMetadata(
    locale,
    `/dialects/${code}`,
    t("pageTitle", { name }),
    t("pageDescription", { name, examples }),
  );
}

export default async function DialectPage({ params }: PageProps<"/[locale]/dialects/[code]">) {
  const { locale, code } = await params;
  setRequestLocale(locale);
  const dialect = await loadDialect(code);
  if (!dialect) notFound();
  return <DialectView key={code} dialect={dialect} />;
}
