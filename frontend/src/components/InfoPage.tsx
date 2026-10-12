import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import LocaleSwitcher from "@/components/LocaleSwitcher";
import { Link } from "@/i18n/navigation";

export const GITHUB_ISSUES_URL = "https://github.com/gmisha777/dialectio/issues";

export const INFO_PAGES = [
  "dialects",
  "check",
  "community",
  "false-friends",
  "about",
  "sources",
  "privacy",
  "terms",
  "imprint",
] as const;
/** The header has room only for these; the legal pages are linked from footers and panels. */
export const HEADER_PAGES = INFO_PAGES.slice(0, 5);

/** Links to the project pages (dialects, game, about, sources, legal pages). */
export function InfoNav({
  className = "",
  pages = INFO_PAGES,
}: {
  className?: string;
  pages?: readonly (typeof INFO_PAGES)[number][];
}) {
  const t = useTranslations("Nav");
  return (
    <nav className={`flex flex-wrap gap-x-4 gap-y-1 text-sm ${className}`}>
      {pages.map((page) => (
        <Link key={page} href={`/${page}`} className="opacity-70 hover:underline hover:opacity-100">
          {t(page)}
        </Link>
      ))}
    </nav>
  );
}

/** Layout of the text pages: header with the logo, the article, links to the other pages. */
export default function InfoPage({ title, children }: { title: string; children: ReactNode }) {
  const t = useTranslations("Nav");
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-center gap-4 border-b border-black/10 px-4 py-3 dark:border-white/15">
        <Link href="/" className="text-xl font-semibold">
          Dialectio
        </Link>
        <Link href="/" className="text-sm opacity-70 hover:underline hover:opacity-100">
          {t("map")}
        </Link>
        <LocaleSwitcher />
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-8">
        <h1 className="mb-6 text-3xl font-semibold">{title}</h1>
        <div className="space-y-4 leading-relaxed [&_a]:underline [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-semibold">
          {children}
        </div>
      </main>
      <footer className="border-t border-black/10 py-4 dark:border-white/15">
        <InfoNav className="mx-auto max-w-2xl px-4" />
      </footer>
    </div>
  );
}

export function externalLink(href: string) {
  function ExternalLink(chunks: ReactNode) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {chunks}
      </a>
    );
  }
  return ExternalLink;
}
