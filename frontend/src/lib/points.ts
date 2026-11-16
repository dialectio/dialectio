import type { FeatureCollection, Point } from "geojson";

import { API_URL, type Names } from "@/lib/api";

/** A word where members say it (see backend app/api/points.py). */
export type PointProps = {
  form_id: number;
  spelling: string;
  variety_code: string;
  variety_en: string;
  variety_uk: string | null;
  variety_names: Names;
  place: string;
  place_names: Names;
  /** Members who say it here (within ~10 km) */
  people: number;
  weight: number;
  /** 0: shown at village zoom, 1: district zoom, 2: oblast zoom */
  level: 0 | 1 | 2;
  unverified: boolean;
  votes_yes: number;
  votes_no: number;
  community: "confirmed" | "disputed" | null;
  comments: number;
};

export type WordPoints = FeatureCollection<Point, PointProps>;

/** The zoom from which each level's points show. */
export const POINT_ZOOMS = [9.5, 7.5, 5] as const;

export async function getPoints(
  conceptId: number,
  signal?: AbortSignal,
): Promise<WordPoints> {
  const response = await fetch(`${API_URL}/api/concepts/${conceptId}/points`, {
    signal,
  });
  if (!response.ok) throw new Error(`Points: ${response.status}`);
  return response.json();
}
