"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { regionGroups } from "@/components/WordCheck";
import { localized } from "@/lib/api";
import { listVoterRegions, myRegion, type RegionOption } from "@/lib/feedback";
import {
  nearestSettlement,
  searchSettlements,
  type Settlement,
  settlementArea,
  settlementName,
} from "@/lib/settlements";

/** Where a word is said: a settlement, or only an oblast or country. */
export type Where =
  | { kind: "settlement"; settlement: Settlement }
  | { kind: "region"; region: RegionOption };

/** The region codes of a place, most specific first (oblast, then its country). */
export const regionCodesOf = (where: Where | null): (string | null)[] =>
  where === null
    ? []
    : where.kind === "settlement"
      ? [where.settlement.region_code, where.settlement.country_code]
      : [where.region.code, where.region.country];

// "My location" is rounded to ~1 km before it leaves the browser
const round = (x: number) => Math.round(x * 100) / 100;

type Locating = "idle" | "busy" | "denied" | "none" | "error";

/**
 * "Where do they say it?": search a settlement by name, "I am there now" (the nearest
 * settlement to the browser's location), or pick an oblast or country. Starts from the
 * oblast selected on the map, else where the visitor said they live.
 */
export default function PlacePicker({
  regionCode,
  value,
  onChange,
}: {
  regionCode: string | null;
  value: Where | null;
  onChange: (where: Where | null) => void;
}) {
  const t = useTranslations("Contribute");
  const locale = useLocale();
  const [regions, setRegions] = useState<RegionOption[]>([]);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<Settlement[] | null>(null);
  const [locating, setLocating] = useState<Locating>("idle");
  const started = useRef(false);

  useEffect(() => {
    listVoterRegions()
      .then((result) => {
        setRegions(result);
        if (started.current) return;
        started.current = true;
        const start = regionCode ?? myRegion();
        const region = result.find((r) => r.code === start);
        if (region && !value) onChange({ kind: "region", region });
      })
      .catch(() => {});
    // Only once: later changes are the visitor's own
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchSettlements(q, controller.signal)
        .then(setFound)
        .catch(() => {});
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const choose = (settlement: Settlement) => {
    onChange({ kind: "settlement", settlement });
    setQuery("");
    setFound(null);
  };

  const locate = () => {
    if (!navigator.geolocation) {
      setLocating("error");
      return;
    }
    setLocating("busy");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const settlement = await nearestSettlement(
            round(coords.latitude),
            round(coords.longitude),
          );
          if (settlement) {
            choose(settlement);
            setLocating("idle");
          } else setLocating("none");
        } catch {
          setLocating("error");
        }
      },
      (error) => setLocating(error.code === error.PERMISSION_DENIED ? "denied" : "error"),
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 600_000 },
    );
  };

  if (value?.kind === "settlement") {
    const s = value.settlement;
    return (
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span>📍</span>
        <span className="font-semibold">{settlementName(s, locale)}</span>
        <span className="text-xs opacity-70">{settlementArea(s, locale)}</span>
        <button type="button" onClick={() => onChange(null)} className="text-xs opacity-60 hover:underline">
          {t("change")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("settlementHint")}
          aria-label={t("settlement")}
          autoComplete="off"
          className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
        />
        {found && query.trim().length >= 2 && (
          <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded border border-black/15 bg-[var(--background)] shadow-lg dark:border-white/20">
            {found.length === 0 && <li className="px-2 py-1.5 opacity-60">{t("noSettlements")}</li>}
            {found.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => choose(s)}
                  className="block w-full px-2 py-1.5 text-left hover:bg-black/5 dark:hover:bg-white/10"
                >
                  <span className="font-medium">{settlementName(s, locale)}</span>{" "}
                  <span className="text-xs opacity-70">{settlementArea(s, locale)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button
          type="button"
          onClick={locate}
          disabled={locating === "busy"}
          className="rounded border border-current/30 px-2 py-1 disabled:opacity-50"
        >
          📍 {locating === "busy" ? t("locating") : t("myLocation")}
        </button>
        {locating === "denied" && <span className="text-xs text-red-600">{t("locationDenied")}</span>}
        {locating === "none" && <span className="text-xs text-red-600">{t("noNearby")}</span>}
        {locating === "error" && <span className="text-xs text-red-600">{t("locationError")}</span>}
      </div>
      <label className="block">
        <span className="mb-1 block text-xs opacity-70">{t("orRegion")}</span>
        <select
          value={value?.kind === "region" ? value.region.code : ""}
          onChange={(e) => {
            const region = regions.find((r) => r.code === e.target.value);
            onChange(region ? { kind: "region", region } : null);
          }}
          className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
        >
          <option value="">…</option>
          {regionGroups(regions, locale).map(({ label, options }) => (
            <optgroup key={label ?? ""} label={label ?? t("otherCountries")}>
              {options.map((r) => (
                <option key={r.code} value={r.code}>
                  {localized(locale, r.name_en, r.name_uk, r.names)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <p className="text-xs opacity-60">{t("privacy")}</p>
    </div>
  );
}
