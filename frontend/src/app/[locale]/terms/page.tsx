import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage, { externalLink, CONTACT_HREF } from "@/components/InfoPage";
import { pageMetadata } from "@/lib/metadata";

const SECTIONS = ["service", "content", "contributions", "conduct", "liability", "changes"] as const;

export async function generateMetadata({ params }: PageProps<"/[locale]/terms">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Terms" });
  return pageMetadata(locale, "/terms", t("title"), t("metaDescription"));
}

export default async function TermsPage({ params }: PageProps<"/[locale]/terms">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Terms");

  return (
    <InfoPage title={t("title")}>
      <p className="text-sm opacity-70">{t("updated")}</p>
      {SECTIONS.map((section) => (
        <section key={section} className="space-y-4">
          <h2>{t(`${section}Title`)}</h2>
          <p>{t(section)}</p>
        </section>
      ))}
      <p>{t.rich("contact", { link: externalLink(CONTACT_HREF) })}</p>
    </InfoPage>
  );
}
