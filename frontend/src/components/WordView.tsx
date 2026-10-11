"use client";

import { useLocale } from "next-intl";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import ConceptPanel from "@/components/ConceptPanel";
import { useMapView } from "@/components/MapShell";
import type { SelectedRegion } from "@/components/WorldMap";
import { type ConceptDetail, getConcept, localized } from "@/lib/api";

/** Query parameter that keeps the selected region in the URL (`?region=UA-26`). */
export const REGION_PARAM = "region";

/** Region name and parent from the concept's map labels; null if the word has no label there. */
function regionFromLabels(
  concept: ConceptDetail,
  code: string,
  locale: string,
): SelectedRegion | null {
  const label = concept.labels.features.find((f) => f.properties.code === code);
  if (!label) return null;
  const { name_en, name_uk, parent_code } = label.properties;
  return { code, name: localized(locale, name_en, name_uk), parentCode: parent_code };
}

/**
 * Applies ?region= once when the page opens (later clicks update the URL themselves).
 * Kept separate so the panel itself still renders on the server.
 */
function RegionFromUrl({ onRegion }: { onRegion: (code: string) => void }) {
  const code = useSearchParams().get(REGION_PARAM);
  const applied = useRef(false);
  useEffect(() => {
    if (applied.current) return;
    applied.current = true;
    if (code) onRegion(code);
  }, [code, onRegion]);
  return null;
}

function setRegionInUrl(code: string | null) {
  const url = new URL(window.location.href);
  if (code) url.searchParams.set(REGION_PARAM, code);
  else url.searchParams.delete(REGION_PARAM);
  // Filtering by region is not a new page: replace, don't push.
  window.history.replaceState(null, "", url);
}

/** A word page: the panel, and the word on the shared map. */
export default function WordView({ initialConcept }: { initialConcept: ConceptDetail }) {
  const locale = useLocale();
  const [concept, setConcept] = useState(initialConcept);
  const [region, setRegion] = useState<SelectedRegion | null>(null);

  // The server-rendered page may be a few minutes old (cache); load the current data so
  // edits and newly approved words show up immediately.
  useEffect(() => {
    const controller = new AbortController();
    getConcept(initialConcept.id, controller.signal)
      .then(setConcept)
      .catch(() => {}); // keep the server-rendered data
    return () => controller.abort();
  }, [initialConcept.id]);

  const selectRegion = (selected: SelectedRegion | null) => {
    setRegion(selected);
    setRegionInUrl(selected?.code ?? null);
  };

  const regionFromUrl = useCallback(
    (code: string) => setRegion(regionFromLabels(initialConcept, code, locale)),
    [initialConcept, locale],
  );

  useMapView({
    concept,
    selectedCode: region?.code ?? null,
    onSelectRegion: selectRegion,
  });

  return (
    <>
      <Suspense fallback={null}>
        <RegionFromUrl onRegion={regionFromUrl} />
      </Suspense>
      <ConceptPanel concept={concept} region={region} onClearRegion={() => selectRegion(null)} />
    </>
  );
}
