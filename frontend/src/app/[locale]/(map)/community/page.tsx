import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";

import CommunityView from "@/components/CommunityView";
import { getCommunity } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/community">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Community" });
  return pageMetadata(locale, "/community", t("title"), t("metaDescription"));
}

export default async function CommunityPage({
  params,
}: PageProps<"/[locale]/community">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await connection(); // needs the API: render per request, not at build time
  const community = await getCommunity().catch(() => null);
  if (!community) notFound();
  return <CommunityView community={community} />;
}
