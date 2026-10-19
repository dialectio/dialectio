"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { INFO_PAGES } from "@/lib/pages";
import { Link, usePathname } from "@/i18n/navigation";

/** ☰ menu with the project pages; by default only on screens too narrow for header links. */
export default function MobileMenu({
  className = "xl:hidden",
}: {
  className?: string;
}) {
  const t = useTranslations("Nav");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close after navigating, and on a click outside the menu.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [open]);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={t("menu")}
        className="rounded-md border border-black/15 px-2.5 py-1 text-lg leading-none dark:border-white/20"
      >
        ☰
      </button>
      {open && (
        <nav className="absolute right-0 z-20 mt-2 w-56 rounded-lg border border-black/10 bg-white p-2 shadow-lg dark:border-white/15 dark:bg-neutral-900">
          {INFO_PAGES.map((page) => (
            <Link
              key={page}
              href={`/${page}`}
              className={`block rounded-md px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10 ${
                page === "check"
                  ? "font-semibold text-violet-700 dark:text-violet-300"
                  : ""
              }`}
            >
              {t(page)}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
