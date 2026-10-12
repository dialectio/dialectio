import type { Metadata } from "next";
import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage from "@/components/InfoPage";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/imprint">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Imprint" });
  return pageMetadata(locale, "/imprint", t("title"), t("metaDescription"));
}

/** Legal notice (Impressum). The operator's details come from the server's environment
 * (IMPRINT_NAME, IMPRINT_ADDRESS, IMPRINT_EMAIL), so personal data stays out of the code. */
export default async function ImprintPage({ params }: PageProps<"/[locale]/imprint">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await connection(); // read the environment at request time, not at build time
  const t = await getTranslations("Imprint");
  const name = process.env.IMPRINT_NAME;
  const address = process.env.IMPRINT_ADDRESS;
  const email = process.env.IMPRINT_EMAIL;

  return (
    <InfoPage title={t("title")}>
      <p>{t("intro")}</p>
      {name || address || email ? (
        <dl className="space-y-2">
          {name && (
            <div>
              <dt className="text-sm opacity-70">{t("name")}</dt>
              <dd>{name}</dd>
            </div>
          )}
          {address && (
            <div>
              <dt className="text-sm opacity-70">{t("address")}</dt>
              <dd className="whitespace-pre-line">{address.replaceAll("\n", "\n")}</dd>
            </div>
          )}
          {email && (
            <div>
              <dt className="text-sm opacity-70">{t("email")}</dt>
              <dd>
                <a href={`mailto:${email}`}>{email}</a>
              </dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="opacity-70">{t("notConfigured")}</p>
      )}
      <p className="text-sm opacity-70">{t("contentNote")}</p>
    </InfoPage>
  );
}
