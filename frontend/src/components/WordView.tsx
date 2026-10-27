"use client";

import { useLocale } from "next-intl";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "next/navigation";

import ConceptPanel from "@/components/ConceptPanel";
import { useConceptOnMap } from "@/components/MapShell";
import OriginTools, {
  familyColors,
  wordFamilies,
} from "@/components/OriginTools";
import type { SelectedRegion } from "@/components/WorldMap";
import { type ConceptDetail, getConcept, localized } from "@/lib/api";
import { DIALECT_BOUNDS } from "@/lib/visitor";

/** Query parameter that keeps the selected region in the URL (`?region=UA-26`). */
export const REGION_PARAM = "region";
/** Query parameter that opens the map on a language's dialect areas (`?area=ukr`) or a box (`?area=-8,50,2,56`), for shared links. */
export const AREA_PARAM = "area";

/** Region name and parent from the concept's map labels; null if the word has no label there. */
function regionFromLabels(
  concept: ConceptDetail,
  code: string,
  locale: string,
): SelectedRegion | null {
  const label = concept.labels.features.find((f) => f.properties.code === code);
  if (!label) return null;
  const { name_en, name_uk, names, parent_code } = label.properties;
  return {
    code,
    name: localized(locale, name_en, name_uk, names),
    parentCode: parent_code,
  };
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

/** Applies ?area= once when the page opens: zooms to that language's dialect areas. */
function AreaFromUrl({ onArea }: { onArea: (bounds: number[]) => void }) {
  const area = useSearchParams().get(AREA_PARAM);
  useEffect(() => {
    if (!area) return;
    // A language code (`ukr`) or a box `west,south,east,north`
    const box = area.split(",").map(Number);
    const bounds =
      DIALECT_BOUNDS[area] ??
      (box.length === 4 && box.every(Number.isFinite) ? box : undefined);
    if (bounds) onArea(bounds);
  }, [area, onArea]);
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
export default function WordView({
  initialConcept,
}: {
  initialConcept: ConceptDetail;
}) {
  const locale = useLocale();
  const [concept, setConcept] = useState(initialConcept);
  const [region, setRegion] = useState<SelectedRegion | null>(null);
  const [bounds, setBounds] = useState<number[] | null>(null);
  // Colour by origin from the start when the word has several families: it's the map's story
  const [byOrigin, setByOrigin] = useState(
    () => wordFamilies(initialConcept).length > 1,
  );
  const colors = useMemo(
    () => (byOrigin ? familyColors(concept) : null),
    [byOrigin, concept],
  );

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

  useConceptOnMap(concept, region?.code ?? null, selectRegion, colors, bounds);

  return (
    <>
      <Suspense fallback={null}>
        <RegionFromUrl onRegion={regionFromUrl} />
        <AreaFromUrl onArea={setBounds} />
      </Suspense>
      <ConceptPanel
        concept={concept}
        region={region}
        onClearRegion={() => selectRegion(null)}
        tools={
          <OriginTools
            concept={concept}
            byOrigin={byOrigin}
            onByOrigin={setByOrigin}
          />
        }
      />
    </>
  );
}
