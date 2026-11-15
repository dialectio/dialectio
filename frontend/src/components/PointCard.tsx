"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import WordCheck, { type Counts, TrustMark } from "@/components/WordCheck";
import { localized } from "@/lib/api";
import type { PointProps } from "@/lib/points";

/** A member's word on the map: where it is said, by how many, and "do people say it?". */
export default function PointCard({
  point,
  onClose,
}: {
  point: PointProps;
  onClose: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("Points");
  const [counts, setCounts] = useState<Counts>();
  const form = { id: point.form_id, ...point };

  return (
    <div className="absolute bottom-8 left-3 z-10 max-h-[70%] w-[min(22rem,calc(100%-1.5rem))] overflow-y-auto rounded-lg bg-background p-3 shadow-lg ring-1 ring-black/10 dark:ring-white/15">
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs uppercase tracking-wide opacity-60">
          {localized(
            locale,
            point.variety_en,
            point.variety_uk,
            point.variety_names,
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("close")}
          className="-mt-1 px-1 opacity-60 hover:opacity-100"
        >
          ✕
        </button>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-serif text-xl font-semibold">
          {point.spelling}
        </span>
        <TrustMark form={form} counts={counts} />
      </div>
      <p className="mt-1 text-sm">
        📍 {point.place_names[locale] ?? point.place}
      </p>
      <p className="text-xs opacity-60">
        {t("people", { count: point.people })}
      </p>
      <WordCheck
        form={form}
        variety={point.variety_code}
        onCounts={setCounts}
        comments={point.comments}
        askUsage
      />
    </div>
  );
}
