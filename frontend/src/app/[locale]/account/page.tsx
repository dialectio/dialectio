import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AccountPanel from "@/components/AccountPanel";
import InfoPage from "@/components/InfoPage";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/account">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Account" });
  return { title: t("profile"), robots: { index: false } };
}

export default async function AccountPage({
  params,
}: PageProps<"/[locale]/account">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Account");
  return (
    <InfoPage title={t("profile")}>
      <AccountPanel />
    </InfoPage>
  );
}
