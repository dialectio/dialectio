"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { InfoNav } from "@/components/InfoPage";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import SearchBox from "@/components/SearchBox";
import WorldMap, { type SelectedRegion } from "@/components/WorldMap";
import { Link, useRouter } from "@/i18n/navigation";
import type { ConceptDetail, SearchHit } from "@/lib/api";

/** What the current page wants the shared map to show. */
export type MapView = {
  concept: ConceptDetail | null;
  selectedCode: string | null;
  onSelectRegion: (region: SelectedRegion) => void;
};

const EMPTY_VIEW: MapView = { concept: null, selectedCode: null, onSelectRegion: () => {} };

const MapViewContext = createContext<(view: MapView) => void>(() => {});

/** Pages call this to put their word on the map (the map itself lives in the layout). */
export function useMapView(view: MapView) {
  const setView = useContext(MapViewContext);
  const { concept, selectedCode, onSelectRegion } = view;
  const onSelectRef = useRef(onSelectRegion);
  useEffect(() => {
    onSelectRef.current = onSelectRegion;
  });
  useEffect(() => {
    setView({ concept, selectedCode, onSelectRegion: (r) => onSelectRef.current(r) });
  }, [setView, concept, selectedCode]);
  useEffect(() => () => setView(EMPTY_VIEW), [setView]);
}

/**
 * Header and map shared by the home page and the word pages. The map stays mounted while the
 * visitor moves between words: every word is its own page (URL, title, page view), only the
 * panel is re-rendered.
 */
export default function MapShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [view, setView] = useState<MapView>(EMPTY_VIEW);
  const panelRef = useRef<HTMLDivElement>(null);

  const highlightCodes = useMemo(
    () => (view.concept ? view.concept.languages.flatMap((lang) => lang.region_codes) : []),
    [view.concept],
  );

  const selectRegion = (region: SelectedRegion) => {
    view.onSelectRegion(region);
    // On phones the panel is below the map: bring the filtered list into view.
    if (window.matchMedia("(max-width: 767px)").matches) {
      panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const openHit = (hit: SearchHit) => {
    if (hit.concept.slug) router.push(`/word/${hit.concept.slug}`);
  };

  return (
    <MapViewContext.Provider value={setView}>
      <main className="flex h-full flex-col">
        <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-black/10 px-4 py-3 dark:border-white/15">
          <Link href="/" className="text-xl font-semibold">
            Dialectio
          </Link>
          <SearchBox onSelect={openHit} />
          <InfoNav className="hidden shrink-0 lg:flex" />
          <LocaleSwitcher />
        </header>
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <section className="relative min-h-[50vh] flex-1">
            <WorldMap
              highlightCodes={highlightCodes}
              labels={view.concept?.labels ?? null}
              selectedCode={view.selectedCode}
              onSelectRegion={selectRegion}
            />
          </section>
          <div
            ref={panelRef}
            className="border-black/10 md:w-96 md:overflow-y-auto md:border-l dark:border-white/15"
          >
            {children}
          </div>
        </div>
      </main>
    </MapViewContext.Provider>
  );
}
