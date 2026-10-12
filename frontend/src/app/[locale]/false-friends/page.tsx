import type { Metadata } from "next";
import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage from "@/components/InfoPage";
import { Link } from "@/i18n/navigation";
import { capitalize, listFalseFriendLanguages, localized } from "@/lib/api";
import { LANGUAGE_FLAGS } from "@/lib/flags";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/false-friends">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "FalseFriends" });
  return pageMetadata(locale, "/false-friends", t("title"), t("metaDescription"));
}

export default async function FalseFriendsPage({ params }: PageProps<"/[locale]/false-friends">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await connection(); // needs the API: render per request, not at build time
  const t = await getTranslations("FalseFriends");
  const languages = await listFalseFriendLanguages().catch(() => []);

  return (
    <InfoPage title={t("title")}>
      <p>{t("intro")}</p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {languages.map((language) => (
          <li key={language.code}>
            <Link
              href={`/false-friends/${language.code}`}
              className="flex items-center gap-2 rounded-md border border-black/10 px-3 py-2 !no-underline hover:bg-black/5 dark:border-white/15 dark:hover:bg-white/10"
            >
              {LANGUAGE_FLAGS[language.code] && (
                <span aria-hidden="true" className={`fi fi-${LANGUAGE_FLAGS[language.code]}`} />
              )}
              <span className="font-medium">
                {capitalize(localized(locale, language.name_en, language.name_uk, language.names))}
              </span>
              <span className="ml-auto text-sm opacity-60">
                {t("pairs", { count: language.count })}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </InfoPage>
  );
}
