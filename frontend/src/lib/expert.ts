import { apiCall as call } from "@/lib/account";
import type { Names } from "@/lib/api";
import type { EditorForm } from "@/lib/editor";

/** A member's application to be an expert of a variety, or their expertise. */
export type ExpertRole = {
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
  variety_names: Names;
  status: "applied" | "expert" | "declined";
  note: string;
};

export type QueueItem = {
  form: EditorForm;
  concept_slug: string | null;
  concept_gloss_en: string;
  concept_gloss_uk: string | null;
  concept_glosses: Names;
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
  variety_names: Names;
  concept_description_en?: string | null;
  concept_description_uk?: string | null;
  /** The main word of the variety's language for the concept */
  standard?: string | null;
  /** Weighted votes */
  yes: number;
  no: number;
  community: "confirmed" | "disputed" | null;
  reports: { id: number; message: string; created_at: string }[];
};

/** One entry of the change log: what an editor or expert did to a word. */
export type WordChange = {
  form_id: number | null;
  variety_code: string;
  spelling: string;
  action: "add" | "approve" | "reject" | "delete" | "spelling" | "primary";
  before: { spelling?: string; ipa?: string | null; status?: string };
  after: { spelling?: string; ipa?: string | null; status?: string };
  /** The expert's name, or "editors" */
  actor: string;
  created_at: string;
};

export const fetchRoles = () => call<ExpertRole[]>("/api/expert/roles");

export const applyAsExpert = (variety: string, note: string) =>
  call<null>("/api/expert/applications", "POST", { variety, note });

export const fetchQueue = (variety: string) =>
  call<QueueItem[]>(`/api/expert/queue?variety=${encodeURIComponent(variety)}`);

export const fetchChanges = (variety: string) =>
  call<WordChange[]>(
    `/api/expert/changes?variety=${encodeURIComponent(variety)}`,
  );

export const expertApprove = (id: number) =>
  call<EditorForm>(`/api/expert/forms/${id}/approve`, "POST");

export const expertReject = (id: number) =>
  call<null>(`/api/expert/forms/${id}/reject`, "POST");

export const expertPrimary = (id: number) =>
  call<EditorForm>(`/api/expert/forms/${id}/primary`, "POST");

export const expertSpelling = (
  id: number,
  spelling: string,
  ipa: string | null,
) =>
  call<EditorForm>(`/api/expert/forms/${id}/spelling`, "POST", {
    spelling,
    ipa,
  });

export const expertResolve = (reportId: number) =>
  call<null>(`/api/expert/reports/${reportId}/resolve`, "POST");
