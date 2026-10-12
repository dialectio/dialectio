import { useTranslations } from "next-intl";

import InfoPage from "@/components/InfoPage";
import { Link } from "@/i18n/navigation";

/** 404 for unknown words, dialects and pages, in the page's language. */
export default function NotFound() {
  const t = useTranslations("NotFound");
  return (
    <InfoPage title={t("title")}>
      <p>{t("text")}</p>
      <p>
        <Link href="/">{t("home")}</Link> · <Link href="/dialects">{t("dialects")}</Link> ·{" "}
        <Link href="/check">{t("check")}</Link>
      </p>
    </InfoPage>
  );
}
