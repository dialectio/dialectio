import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import DialectList from "@/components/DialectList";
import { listDialects } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/dialects">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Dialects" });
  return pageMetadata(locale, "/dialects", t("title"), t("metaDescription"));
}

export default async function DialectsPage({ params }: PageProps<"/[locale]/dialects">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const dialects = await listDialects();
  return <DialectList dialects={dialects} />;
}
