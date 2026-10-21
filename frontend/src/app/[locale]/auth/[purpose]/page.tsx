import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import EmailLinkView, { type LinkPurpose } from "@/components/EmailLinkView";
import InfoPage from "@/components/InfoPage";

const PURPOSES: LinkPurpose[] = ["verify", "reset", "login"];

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/auth/[purpose]">): Promise<Metadata> {
  const { locale, purpose } = await params;
  const t = await getTranslations({ locale, namespace: "EmailLink" });
  const key = PURPOSES.includes(purpose as LinkPurpose) ? purpose : "verify";
  return { title: t(`title.${key}`), robots: { index: false } };
}

/** The page links in our emails open: confirm the email, set a new password, sign in. */
export default async function EmailLinkPage({
  params,
  searchParams,
}: PageProps<"/[locale]/auth/[purpose]">) {
  const { locale, purpose } = await params;
  if (!PURPOSES.includes(purpose as LinkPurpose)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("EmailLink");
  const { token } = await searchParams;
  return (
    <InfoPage title={t(`title.${purpose}`)}>
      <EmailLinkView
        purpose={purpose as LinkPurpose}
        token={typeof token === "string" ? token : ""}
      />
    </InfoPage>
  );
}
