"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { useMapSnapshot } from "@/components/MapShell";
import { type ConceptDetail, localized, SITE_URL } from "@/lib/api";
import { download } from "@/lib/snapshot";

/** Colours of word families, largest family first; smaller ones stay grey. */
export const FAMILY_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
];
const EXAMPLES = 3;
// Languages whose words make the best-known examples of a family, in this order
const EXAMPLE_ORDER = ["eng", "deu", "fra", "spa", "ita", "pol", "ukr", "rus", "tur", "jpn"];

export type Family = { color: string; words: string[]; languages: number };

/** The concept's word families with their colours and example words. */
export function wordFamilies(concept: ConceptDetail): Family[] {
  const rank = (code: string) => {
    const i = EXAMPLE_ORDER.indexOf(code);
    return i === -1 ? EXAMPLE_ORDER.length : i;
  };
  const families: Family[] = [];
  for (const lang of [...concept.languages].sort((a, b) => rank(a.code) - rank(b.code))) {
    if (lang.family == null || lang.family >= FAMILY_COLORS.length) continue;
    const family = (families[lang.family] ??= {
      color: FAMILY_COLORS[lang.family],
      words: [],
      languages: 0,
    });
    family.languages += 1;
    const word = lang.forms[0].spelling;
    if (family.words.length < EXAMPLES && !family.words.includes(word)) family.words.push(word);
  }
  return families.filter(Boolean);
}

/** {country/region code: colour} for the map, from the languages' word families. */
export function familyColors(concept: ConceptDetail): Record<string, string> {
  const colors: Record<string, string> = {};
  for (const lang of concept.languages) {
    if (lang.family == null || lang.family >= FAMILY_COLORS.length) continue;
    for (const code of lang.region_codes) colors[code] ??= FAMILY_COLORS[lang.family];
  }
  return colors;
}

/** "Colour by origin" switch with its legend, and "Save as image". */
export default function OriginTools({
  concept,
  byOrigin,
  onByOrigin,
}: {
  concept: ConceptDetail;
  byOrigin: boolean;
  onByOrigin: (on: boolean) => void;
}) {
  const t = useTranslations("Origin");
  const locale = useLocale();
  const snapshot = useMapSnapshot();
  const [saving, setSaving] = useState(false);
  const families = wordFamilies(concept);

  const save = async () => {
    if (!snapshot) return;
    setSaving(true);
    try {
      const title = localized(locale, concept.gloss_en, concept.gloss_uk, concept.glosses);
      const blob = await snapshot({
        title,
        subtitle: t("snapshotSubtitle"),
        legend: byOrigin
          ? families.map((f) => ({ color: f.color, label: f.words.join(", ") }))
          : undefined,
        footer: `${new URL(SITE_URL).host}/${locale}/word/${concept.slug}`,
      });
      if (blob) download(blob, `dialectio-${concept.slug}.png`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        {families.length > 1 && (
          <button
            type="button"
            onClick={() => onByOrigin(!byOrigin)}
            aria-pressed={byOrigin}
            className={`rounded-full border px-2.5 py-1 ${
              byOrigin
                ? "border-blue-500 bg-blue-500/10 text-blue-700 dark:text-blue-300"
                : "border-black/15 hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
            }`}
          >
            🎨 {t("toggle")}
          </button>
        )}
        <button
          type="button"
          onClick={save}
          disabled={saving || !snapshot}
          className="rounded-full border border-black/15 px-2.5 py-1 hover:bg-black/5 disabled:opacity-50 dark:border-white/20 dark:hover:bg-white/10"
        >
          ⬇ {saving ? t("saving") : t("save")}
        </button>
      </div>
      {byOrigin && (
        // Compact legend: the families wrap side by side
        <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {families.map((family) => (
            <li key={family.color} className="flex items-center gap-1">
              <span
                aria-hidden="true"
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: family.color }}
              />
              <span>{family.words.join(", ")}</span>
              <span className="opacity-60">
                {t("languages", { count: family.languages })}
              </span>
            </li>
          ))}
          <li className="w-full opacity-60">{t("note")}</li>
        </ul>
      )}
    </div>
  );
}
