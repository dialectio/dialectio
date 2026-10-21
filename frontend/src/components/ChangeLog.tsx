"use client";

import { useLocale, useTranslations } from "next-intl";

import type { WordChange } from "@/lib/expert";

/** The change log: who did what to which word, newest first. */
export default function ChangeLog({ changes }: { changes: WordChange[] }) {
  const t = useTranslations("Expert");
  const locale = useLocale();
  if (changes.length === 0)
    return <p className="text-sm opacity-60">{t("noChanges")}</p>;
  return (
    <ul className="space-y-1 text-sm">
      {changes.map((c, i) => (
        <li key={i} className="flex flex-wrap gap-x-2">
          <time className="tabular-nums opacity-60" dateTime={c.created_at}>
            {new Date(c.created_at).toLocaleString(locale, {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </time>
          <span className="font-medium">
            {c.actor === "editors" ? t("editors") : c.actor}
          </span>
          <span>{t(`action.${c.action}`)}</span>
          <span className="font-semibold">
            {c.action === "spelling" && c.before.spelling !== c.after.spelling
              ? `${c.before.spelling} → ${c.after.spelling}`
              : c.spelling}
          </span>
          <span className="opacity-60">{c.variety_code}</span>
        </li>
      ))}
    </ul>
  );
}
