"use client";

import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

const LABELS: Record<(typeof routing.locales)[number], string> = {
  uk: "Українська",
  en: "English",
  pl: "Polski",
  de: "Deutsch",
  es: "Español",
  fr: "Français",
};

export default function LocaleSwitcher() {
  const t = useTranslations("Header");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  return (
    // The native <select> (transparent, on top) keeps the system picker and keyboard support;
    // under it: a globe and the language, shortened to its code on phones.
    <label className="relative ml-auto inline-flex items-center gap-1.5 rounded-md border border-black/15 px-2 py-1.5 text-sm hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10">
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="h-4 w-4 opacity-70"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
      </svg>
      <span className="sm:hidden">{locale.toUpperCase()}</span>
      <span className="hidden sm:inline">{LABELS[locale as keyof typeof LABELS]}</span>
      <svg aria-hidden="true" viewBox="0 0 20 20" className="h-3 w-3 opacity-60" fill="currentColor">
        <path d="M5 7l5 6 5-6z" />
      </svg>
      <select
        aria-label={t("language")}
        value={locale}
        onChange={(e) => router.replace(pathname, { locale: e.target.value })}
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {routing.locales.map((l) => (
          <option key={l} value={l}>
            {LABELS[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
