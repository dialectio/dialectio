import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import ExpertView from "@/components/ExpertView";
import InfoPage from "@/components/InfoPage";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/expert">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Expert" });
  return { title: t("title"), robots: { index: false } };
}

/** Where experts review the words of their language or dialect. */
export default async function ExpertPage({
  params,
}: PageProps<"/[locale]/expert">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Expert");
  return (
    <InfoPage title={t("title")}>
      <ExpertView />
    </InfoPage>
  );
}
