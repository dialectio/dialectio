import { API_URL, type Names } from "@/lib/api";

const VOTER_KEY = "dialectio.voter";
const VOTES_KEY = "dialectio.votes";
const REGION_KEY = "dialectio.region";

/** "Not in Ukraine" answer to "where do you live?" */
export const ABROAD = "abroad";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage blocked (private mode etc.)
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // voting still works, it just isn't remembered
  }
}

/** A random id for this browser: one vote per word, no account. */
export function voterId(): string {
  let id = read(VOTER_KEY);
  if (!id) {
    id = crypto.randomUUID();
    write(VOTER_KEY, id);
  }
  return id;
}

/** This browser's votes: form id -> 1 / -1. */
export function myVotes(): Record<string, number> {
  try {
    return JSON.parse(read(VOTES_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function rememberVote(formId: number, value: number) {
  const votes = myVotes();
  if (value) votes[formId] = value;
  else delete votes[formId];
  write(VOTES_KEY, JSON.stringify(votes));
}

/** Where the visitor said they live: a region code, ABROAD, or null (not asked yet). */
export const myRegion = () => read(REGION_KEY);
export const setMyRegion = (code: string) => write(REGION_KEY, code);

export type VoteCounts = {
  form_id: number;
  yes: number;
  no: number;
  community: "confirmed" | "disputed" | null;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

/** value: 1 "yes", -1 "no", 0 take the vote back. */
export async function sendVote(formId: number, value: number): Promise<VoteCounts> {
  const region = myRegion();
  const counts = await post<VoteCounts>("/api/votes", {
    form_id: formId,
    value,
    voter: voterId(),
    region_code: region && region !== ABROAD ? region : null,
  });
  rememberVote(formId, value);
  return counts;
}

export function sendReport(formId: number, message: string, website: string) {
  const region = myRegion();
  return post<{ status: string }>("/api/reports", {
    form_id: formId,
    message,
    voter: voterId(),
    region_code: region && region !== ABROAD ? region : null,
    website,
  });
}

export type RegionOption = {
  code: string;
  name_en: string;
  name_uk: string | null;
  names?: Names;
  /** The region's country, or null when the option is a whole country */
  country: string | null;
  country_en: string | null;
  country_uk: string | null;
  country_names?: Names;
};

/** Answers to "where do you live?": oblasts, then dialect areas abroad. */
export async function listVoterRegions(): Promise<RegionOption[]> {
  const response = await fetch(`${API_URL}/api/regions/voter`);
  if (!response.ok) throw new Error(`${response.status} /api/regions/voter`);
  return response.json();
}

export type Deck = {
  code: string;
  kind: "language" | "dialect";
  name_en: string;
  name_uk: string | null;
  names?: Names;
  words: number;
};

export type Card = {
  form_id: number;
  spelling: string;
  variety_code: string;
  kind: "language" | "dialect_group" | "dialect";
  variety_name_en: string;
  variety_name_uk: string | null;
  variety_names?: Names;
  slug: string;
  gloss_en: string;
  gloss_uk: string | null;
  glosses?: Names;
  /** Standard Ukrainian and English words for the same concept */
  standard: string | null;
  english: string | null;
  region_codes: string[];
  votes: number;
};

/** Words this browser has not voted on yet, least-voted first. */
export async function loadCards(deck: string, skip: number[], limit = 15): Promise<Card[]> {
  const params = new URLSearchParams({ voter: voterId(), deck, limit: String(limit) });
  for (const id of skip) params.append("skip", String(id));
  const response = await fetch(`${API_URL}/api/check/cards?${params}`);
  if (!response.ok) throw new Error(`${response.status} /api/check/cards`);
  return response.json();
}

const CHECKED_KEY = "dialectio.checked";
const DECK_KEY = "dialectio.checkDeck";

/** How many words this browser has checked in the game. */
export const checkedCount = () => Number(read(CHECKED_KEY) ?? 0) || 0;
export const addChecked = () => write(CHECKED_KEY, String(checkedCount() + 1));
export const savedDeck = () => read(DECK_KEY);
export const saveDeck = (code: string) => write(DECK_KEY, code);

/** A search that found nothing: added to the editors' list of words to add. */
export async function recordMissing(q: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/missing`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q }),
  });
  if (!response.ok) throw new Error(`${response.status} /api/missing`);
}
