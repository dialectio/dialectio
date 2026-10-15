"use client";

import type { FeatureCollection, Point } from "geojson";
import {
  createContext,
  type ReactNode,
  type RefObject,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { HEADER_PAGES, InfoNav } from "@/components/InfoPage";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import Logo from "@/components/Logo";
import SearchBox from "@/components/SearchBox";
import WorldMap, {
  type SelectedRegion,
  type SnapshotFn,
} from "@/components/WorldMap";
import { Link, useRouter } from "@/i18n/navigation";
import type { ConceptDetail, LabelProps, SearchHit } from "@/lib/api";

export type MapLabels = FeatureCollection<Point, LabelProps>;

/** What the current page wants the shared map to show. */
export type MapView = {
  highlightCodes: string[];
  labels: MapLabels | null;
  selectedCode: string | null;
  onSelectRegion: (region: SelectedRegion) => void;
  /** [west, south, east, north] to zoom to when the page opens */
  bounds?: number[] | null;
  /** On phones show the panel above the map (pages where the panel is the main thing) */
  panelFirstOnPhone?: boolean;
  /** Fill colours by country/region code instead of the plain highlight */
  colors?: Record<string, string> | null;
};

/** Ukraine and the neighbouring areas where Ukrainian dialects are spoken. */
export const UKRAINE_BOUNDS = [19, 44, 41, 53];
/** Europe, from Portugal and Ireland to Ukraine. */
export const EUROPE_BOUNDS = [-11, 35, 42, 62];

const NO_CODES: string[] = [];
const EMPTY_VIEW: MapView = {
  highlightCodes: NO_CODES,
  labels: null,
  selectedCode: null,
  onSelectRegion: () => {},
};

const MapViewContext = createContext<(view: MapView) => void>(() => {});
const SnapshotContext = createContext<RefObject<SnapshotFn | null> | null>(
  null,
);

/** Saves the shared map as an image (null until the map is ready). */
export function useMapSnapshot(): SnapshotFn | null {
  const ref = useContext(SnapshotContext);
  return ref
    ? (text) => (ref.current ? ref.current(text) : Promise.resolve(null))
    : null;
}

/** Pages call this to put their word on the map (the map itself lives in the layout). */
export function useMapView(view: MapView) {
  const setView = useContext(MapViewContext);
  const {
    highlightCodes,
    labels,
    selectedCode,
    onSelectRegion,
    bounds = null,
    panelFirstOnPhone = false,
    colors = null,
  } = view;
  const onSelectRef = useRef(onSelectRegion);
  useEffect(() => {
    onSelectRef.current = onSelectRegion;
  });
  useEffect(() => {
    setView({
      highlightCodes,
      labels,
      selectedCode,
      bounds,
      panelFirstOnPhone,
      colors,
      onSelectRegion: (r) => onSelectRef.current(r),
    });
  }, [
    setView,
    highlightCodes,
    labels,
    selectedCode,
    bounds,
    panelFirstOnPhone,
    colors,
  ]);
  useEffect(() => () => setView(EMPTY_VIEW), [setView]);
}

/** Puts a word on the map: its countries and regions highlighted, its words as labels. */
export function useConceptOnMap(
  concept: ConceptDetail | null,
  selectedCode: string | null,
  onSelectRegion: (region: SelectedRegion) => void,
  colors: Record<string, string> | null = null,
) {
  const highlightCodes = useMemo(
    () =>
      concept
        ? concept.languages.flatMap((lang) => lang.region_codes)
        : NO_CODES,
    [concept],
  );
  useMapView({
    highlightCodes,
    labels: concept?.labels ?? null,
    selectedCode,
    onSelectRegion,
    colors,
  });
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
  const snapshotRef = useRef<SnapshotFn | null>(null);

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
      <SnapshotContext.Provider value={snapshotRef}>
        <main className="flex h-full flex-col">
          <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-black/10 px-4 py-3 dark:border-white/15">
            <Link href="/" aria-label="Dialectio">
              <Logo />
            </Link>
            <SearchBox onSelect={openHit} />
            <InfoNav className="hidden shrink-0 lg:flex" pages={HEADER_PAGES} />
            <LocaleSwitcher />
          </header>
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <section className="relative min-h-[50vh] flex-1">
              <WorldMap
                highlightCodes={view.highlightCodes}
                labels={view.labels}
                selectedCode={view.selectedCode}
                bounds={view.bounds ?? null}
                colors={view.colors ?? null}
                snapshotRef={snapshotRef}
                onSelectRegion={selectRegion}
              />
            </section>
            <div
              ref={panelRef}
              className={`border-black/10 md:w-96 md:overflow-y-auto md:border-l dark:border-white/15 ${
                view.panelFirstOnPhone ? "order-first md:order-none" : ""
              }`}
            >
              {children}
            </div>
          </div>
        </main>
      </SnapshotContext.Provider>
    </MapViewContext.Provider>
  );
}
