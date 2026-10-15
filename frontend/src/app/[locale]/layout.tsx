import type { Metadata } from "next";
import { Inter, Noto_Serif } from "next/font/google";
import { notFound } from "next/navigation";
import Script from "next/script";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { routing } from "@/i18n/routing";

import "flag-icons/css/flag-icons.min.css";
import "../globals.css";

// Interface text; the words themselves (and the name) in a serif. Both cover Latin with
// accents, Cyrillic and Greek; other scripts fall back to the system fonts.
const sans = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext", "cyrillic", "cyrillic-ext", "greek"],
});

const serif = Noto_Serif({
  variable: "--font-noto-serif",
  subsets: ["latin", "latin-ext", "cyrillic", "cyrillic-ext", "greek"],
});

// Visit statistics (Umami, self-hosted, no cookies); off unless both are configured.
const UMAMI_SRC = process.env.NEXT_PUBLIC_UMAMI_SRC;
const UMAMI_WEBSITE_ID = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID;

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Metadata" });
  return { title: "Dialectio", description: t("description") };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);

  return (
    <html
      lang={locale}
      className={`${sans.variable} ${serif.variable} h-full antialiased`}
    >
      <body className="h-full flex flex-col">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
        {UMAMI_SRC && UMAMI_WEBSITE_ID && (
          // Every word is its own page, tracked on navigation; ?region= is a filter on the same
          // page, so the query string is left out.
          <Script
            src={UMAMI_SRC}
            data-website-id={UMAMI_WEBSITE_ID}
            data-exclude-search="true"
            strategy="afterInteractive"
          />
        )}
      </body>
    </html>
  );
}
