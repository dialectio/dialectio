import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage, { CONTACT_HREF, externalLink } from "@/components/InfoPage";
import { Link } from "@/i18n/navigation";
import { pageMetadata } from "@/lib/metadata";
import { DONATE } from "@/lib/support";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/support">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Support" });
  return pageMetadata(locale, "/support", t("title"), t("metaDescription"));
}

const BUTTON =
  "inline-flex items-center gap-2 rounded-lg px-4 py-2 font-medium text-white no-underline!";

/** Supporting the project: what it costs, how to give money, and other ways to help. */
export default async function SupportPage({
  params,
}: PageProps<"/[locale]/support">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Support");
  const donations = DONATE.monobank || DONATE.kofi;

  return (
    <InfoPage title={t("title")}>
      <p>{t("intro")}</p>
      <h2>{t("costsTitle")}</h2>
      <p>{t("costs")}</p>
      {donations && (
        <>
          <h2>{t("donateTitle")}</h2>
          <div className="flex flex-wrap gap-3">
            {DONATE.monobank && (
              <a
                href={DONATE.monobank}
                target="_blank"
                rel="noopener noreferrer"
                className={`${BUTTON} bg-neutral-900 hover:bg-neutral-700 dark:bg-neutral-700`}
              >
                🫙 {t("monobank")}
              </a>
            )}
            {DONATE.kofi && (
              <a
                href={DONATE.kofi}
                target="_blank"
                rel="noopener noreferrer"
                className={`${BUTTON} bg-sky-600 hover:bg-sky-700`}
              >
                ☕ {t("kofi")}
              </a>
            )}
          </div>
          <p className="text-sm opacity-70">{t("donateNote")}</p>
        </>
      )}
      <h2>{t("helpTitle")}</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>
          {t.rich("helpCheck", {
            link: (chunks) => <Link href="/check">{chunks}</Link>,
          })}
        </li>
        <li>{t("helpWords")}</li>
        <li>{t("helpShare")}</li>
        <li>{t.rich("helpPartner", { link: externalLink(CONTACT_HREF) })}</li>
      </ul>
    </InfoPage>
  );
}
