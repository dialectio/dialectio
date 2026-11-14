import { API_URL, localized, type Names } from "@/lib/api";
import type { Variety } from "@/lib/varieties";

/** A city, town or village (GeoNames) with the oblast or country it lies in. */
export type Settlement = {
  id: number;
  name: string;
  names: Names;
  region_code: string;
  region_en: string;
  region_uk: string | null;
  region_names: Names;
  country_code: string | null;
  country_en: string | null;
  country_uk: string | null;
  country_names: Names | null;
};

export async function searchSettlements(q: string, signal?: AbortSignal): Promise<Settlement[]> {
  const response = await fetch(`${API_URL}/api/settlements?q=${encodeURIComponent(q)}`, {
    signal,
  });
  if (!response.ok) throw new Error(`${response.status} /api/settlements`);
  return response.json();
}

/** The settlement nearest to a point, or null when none is near. The point goes in the
 * request body and is not stored. */
export async function nearestSettlement(lat: number, lon: number): Promise<Settlement | null> {
  const response = await fetch(`${API_URL}/api/settlements/nearest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon }),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${response.status} /api/settlements/nearest`);
  return response.json();
}

export const settlementName = (s: Settlement, locale: string) => s.names[locale] ?? s.name;

/** "Ivano-Frankivsk Oblast, Ukraine", or only the country */
export function settlementArea(s: Settlement, locale: string) {
  const region = localized(locale, s.region_en, s.region_uk, s.region_names);
  const country = localized(locale, s.country_en, s.country_uk, s.country_names);
  return country ? `${region}, ${country}` : region;
}

/**
 * Languages and dialects spoken in a place, most specific first: the oblast's dialects, the
 * regional languages of the oblast, then the country's languages.
 */
export function varietiesOf(varieties: Variety[], regionCodes: (string | null)[]): Variety[] {
  const found: Variety[] = [];
  for (const code of regionCodes) {
    if (!code) continue;
    const here = varieties.filter((v) => v.region_codes.includes(code));
    for (const v of [...here.filter((v) => v.kind === "dialect"), ...here])
      if (!found.includes(v)) found.push(v);
  }
  return found;
}
