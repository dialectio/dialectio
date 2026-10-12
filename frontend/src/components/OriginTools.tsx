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
        subtitle: byOrigin
          ? families.map((f) => f.words[0]).join(" · ")
          : t("snapshotSubtitle"),
        footer: `${new URL(SITE_URL).host}/${locale}/word/${concept.slug}`,
      });
      if (blob) download(blob, `dialectio-${concept.slug}.png`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {families.length > 1 && (
          <label className="inline-flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={byOrigin}
              onChange={(e) => onByOrigin(e.target.checked)}
            />
            {t("toggle")}
          </label>
        )}
        <button
          type="button"
          onClick={save}
          disabled={saving || !snapshot}
          className="text-blue-700 hover:underline disabled:opacity-50 dark:text-blue-300"
        >
          ⬇ {saving ? t("saving") : t("save")}
        </button>
      </div>
      {byOrigin && (
        <div>
          <ul className="space-y-0.5">
            {families.map((family) => (
              <li key={family.color} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block h-3 w-3 shrink-0 rounded-sm"
                  style={{ background: family.color }}
                />
                <span>{family.words.join(", ")}</span>
                <span className="text-xs opacity-60">
                  {t("languages", { count: family.languages })}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs opacity-60">{t("note")}</p>
        </div>
      )}
    </div>
  );
}
