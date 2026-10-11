import type { Metadata } from "next";
import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";

import CheckGame from "@/components/CheckGame";
import { listCheckDecks } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/check">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Game" });
  return pageMetadata(locale, "/check", t("title"), t("metaDescription"));
}

export default async function CheckPage({ params }: PageProps<"/[locale]/check">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await connection(); // needs the API: render per request, not at build time
  const decks = await listCheckDecks().catch(() => []);
  return <CheckGame decks={decks} />;
}
