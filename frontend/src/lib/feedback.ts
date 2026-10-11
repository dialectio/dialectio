import { API_URL } from "@/lib/api";

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

export type RegionOption = { code: string; name_en: string; name_uk: string | null };

export async function listUkraineRegions(): Promise<RegionOption[]> {
  const response = await fetch(`${API_URL}/api/regions/ukraine`);
  if (!response.ok) throw new Error(`${response.status} /api/regions/ukraine`);
  return response.json();
}
