import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage from "@/components/InfoPage";
import SpeakerTestView from "@/components/SpeakerTestView";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/account/test/[variety]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Speaker" });
  return { title: t("title"), robots: { index: false } };
}

export default async function SpeakerTestPage({
  params,
}: PageProps<"/[locale]/account/test/[variety]">) {
  const { locale, variety } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Speaker");
  return (
    <InfoPage title={t("title")}>
      <SpeakerTestView code={decodeURIComponent(variety)} />
    </InfoPage>
  );
}
