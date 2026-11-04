"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { localized } from "@/lib/api";
import type { Variety } from "@/lib/varieties";

/** Lowercase without accents, so "katalanski" finds "Kataloński" */
const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();

const ownNames = (v: Variety) =>
  [v.code, v.name_en, v.name_uk ?? "", ...Object.values(v.names ?? {})].map(fold);

/**
 * How well a variety matches the search words, lower is better: its own name starts with
 * them (German for "germ"), then contains them (Alemannic (Swiss German)), then only its
 * language does (Bavarian for "german"); null when it does not match.
 */
function rank(v: Variety, parent: Variety | undefined, words: string[]): number | null {
  const own = ownNames(v);
  const all = own.join(" ") + " " + (parent ? ownNames(parent).join(" ") : "");
  if (!words.every((w) => all.includes(w))) return null;
  if (own.some((name) => name.startsWith(words[0]))) return 0;
  return words.every((w) => own.some((name) => name.includes(w))) ? 1 : 2;
}

/**
 * A language/dialect drop-down with a search field above it: the list has ~100 entries.
 * Typing narrows the list (a language finds its dialects too); a native <select> stays
 * because it works best on phones.
 */
export function VarietySelect({
  varieties,
  value,
  onChange,
  placeholder,
  className = "",
  ariaLabel,
}: {
  varieties: Variety[];
  value: string;
  onChange: (code: string) => void;
  /** First empty option ("…"), for pickers that add a variety rather than hold one */
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const t = useTranslations("VarietySelect");
  const locale = useLocale();
  const [query, setQuery] = useState("");
  const byCode = new Map(varieties.map((v) => [v.code, v]));
  const terms = (text: string) => fold(text).split(/\s+/).filter(Boolean);
  /** Matching varieties, best first; the given order (Ukrainian first, by name) breaks ties */
  const search = (words: string[]) =>
    varieties
      .map((v) => ({ v, r: rank(v, v.parent_code ? byCode.get(v.parent_code) : undefined, words) }))
      .filter((x): x is { v: Variety; r: number } => x.r !== null)
      .sort((a, b) => a.r - b.r)
      .map((x) => x.v);
  const words = terms(query);
  const shown = words.length ? search(words) : varieties;
  // Keep the chosen variety visible while the filter hides it, so the select shows the truth
  const selected = byCode.get(value);
  const options = selected && !shown.includes(selected) ? [selected, ...shown] : shown;

  const field =
    "w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20";
  return (
    <div className={`space-y-1.5 ${className}`}>
      <input
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          const next = terms(e.target.value);
          // Pick the first match, so typing "hutsul" is enough in a form that holds a value
          if (placeholder === undefined && next.length) {
            const match = search(next)[0];
            if (match && match.code !== value) onChange(match.code);
          }
        }}
        placeholder={t("search")}
        aria-label={t("search")}
        className={field}
      />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
        className={field}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((v) => (
          <option key={v.code} value={v.code}>
            {v.kind === "dialect" ? "— " : ""}
            {localized(locale, v.name_en, v.name_uk, v.names)}
          </option>
        ))}
      </select>
      {words.length > 0 && shown.length === 0 && (
        <p className="text-xs opacity-60">{t("nothing")}</p>
      )}
    </div>
  );
}
