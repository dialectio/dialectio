import { API_URL } from "@/lib/api";
import type { WordChange } from "@/lib/expert";

export type EditorForm = {
  id: number;
  spelling: string;
  ipa: string | null;
  is_primary: boolean;
  /** "approved" words are public; "pending" drafts wait for review. */
  status: "approved" | "pending" | "submitted";
  source: string | null;
  editable: boolean;
  /** Visitor submissions only */
  contributor: string | null;
  place: string | null;
  audio_urls: string[];
};

export type Submission = {
  form: EditorForm;
  concept_id: number;
  concept_gloss_en: string;
  concept_gloss_uk: string | null;
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
};

export const listSubmissions = (token: string) => request<Submission[]>(token, "/submissions");

export type EditorConcept = {
  id: number;
  wikidata_id: string | null;
  gloss_en: string;
  gloss_uk: string | null;
  description_en: string | null;
  description_uk: string | null;
  hints: Record<string, string>;
  forms: EditorForm[];
};

export class EditorError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}/api/editor${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Editor-Token": token, ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new EditorError(response.status, body?.detail ?? response.statusText);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export type EditorVariety = {
  code: string;
  kind: "language" | "dialect";
  name_en: string;
  name_uk: string | null;
  parent_code: string | null;
};

export const listVarieties = (token: string) => request<EditorVariety[]>(token, "/varieties");

export const listConcepts = (token: string, variety: string) =>
  request<EditorConcept[]>(token, `/concepts?variety=${encodeURIComponent(variety)}`);

export const addForm = (
  token: string,
  form: { concept_id: number; variety: string; spelling: string; ipa: string | null },
) => request<EditorForm>(token, "/forms", { method: "POST", body: JSON.stringify(form) });

export const approveForm = (token: string, id: number) =>
  request<EditorForm>(token, `/forms/${id}/approve`, { method: "POST" });

/** Make this word the main one for its concept and language. */
export const setPrimaryForm = (token: string, id: number) =>
  request<EditorForm>(token, `/forms/${id}/primary`, { method: "POST" });

/** Fix a word's spelling (and IPA); recordings stay with the word. */
export const changeSpelling = (token: string, id: number, spelling: string, ipa: string | null) =>
  request<EditorForm>(token, `/forms/${id}/spelling`, {
    method: "POST",
    body: JSON.stringify({ spelling, ipa }),
  });

export const deleteForm = (token: string, id: number) =>
  request<void>(token, `/forms/${id}`, { method: "DELETE" });

export type FeedbackItem = {
  form: EditorForm;
  concept_id: number;
  concept_slug: string | null;
  concept_gloss_en: string;
  concept_gloss_uk: string | null;
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
  yes: number;
  no: number;
  community: "confirmed" | "disputed" | null;
  /** Votes by voters' region: {"UA-26": [yes, no]} */
  regions: Record<string, [number, number]>;
  reports: { id: number; message: string; region_code: string | null; created_at: string }[];
};

/** Words visitors voted on or reported (disputed and reported first). */
export const listFeedback = (token: string) => request<FeedbackItem[]>(token, "/feedback");

export const resolveReport = (token: string, id: number) =>
  request<void>(token, `/reports/${id}/resolve`, { method: "POST" });

export type MissingSearch = { query: string; count: number; last_seen: string };

/** What visitors searched for and did not find, most wanted first. */
export const listMissing = (token: string) => request<MissingSearch[]>(token, "/missing");

export const dismissMissing = (token: string, query: string) =>
  request<void>(token, `/missing/${encodeURIComponent(query)}`, { method: "DELETE" });

export type ExpertApplication = {
  user_id: number;
  name: string;
  email: string;
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
  status: "applied" | "expert" | "declined";
  note: string;
  created_at: string;
};

/** Applications to be an expert (waiting ones first), experts and declined ones. */
export const listExperts = (token: string) => request<ExpertApplication[]>(token, "/experts");

/** Approve an application, or decline it / take expertise back. */
export const decideExpert = (
  token: string,
  userId: number,
  variety: string,
  status: "expert" | "declined",
) =>
  request<void>(token, "/experts/decision", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, variety, status }),
  });

/** The change log of all words, newest first. */
export const listChanges = (token: string) => request<WordChange[]>(token, "/changes");
