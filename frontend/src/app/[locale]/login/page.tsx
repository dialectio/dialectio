import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AuthForm from "@/components/AuthForm";
import InfoPage from "@/components/InfoPage";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/login">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Account" });
  return { title: t("signInTitle"), robots: { index: false } };
}

export default async function LoginPage({
  params,
  searchParams,
}: PageProps<"/[locale]/login">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Account");
  const { next, error } = await searchParams;
  return (
    <InfoPage title={t("signInTitle")}>
      <p>{t("why")}</p>
      <AuthForm
        next={typeof next === "string" ? next : "/"}
        failed={typeof error === "string" ? error : undefined}
      />
    </InfoPage>
  );
}
