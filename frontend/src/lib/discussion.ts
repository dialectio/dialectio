import { apiCall } from "@/lib/account";
import type { Names } from "@/lib/api";
import { voterId } from "@/lib/feedback";

/** Where members say the word: a settlement, or only a region (`name` null). */
export type DiscussionPlace = {
  names: Names;
  name: string | null;
  region_en: string;
  region_uk: string | null;
  region_names: Names;
  count: number;
};

/** The word's card that opens its discussion, built from the data. */
export type WordCard = {
  form_id: number;
  spelling: string;
  ipa: string | null;
  variety_code: string;
  variety_en: string;
  variety_uk: string | null;
  variety_names: Names;
  concept_slug: string | null;
  gloss_en: string;
  gloss_uk: string | null;
  glosses: Names;
  description_en: string | null;
  description_uk: string | null;
  descriptions: Names;
  source: string | null;
  source_url: string | null;
  license: string | null;
  contributor: string | null;
  unverified: boolean;
  votes_yes: number;
  votes_no: number;
  community: "confirmed" | "disputed" | null;
  places: DiscussionPlace[];
};

export type WordComment = {
  id: number;
  author: string;
  badge: "expert" | "editor" | null;
  body: string;
  created_at: string;
  edited_at: string | null;
  reply_to: { id: number; author: string; text: string } | null;
  mine: boolean;
  /** For moderators only */
  hidden: boolean;
  reports: number;
};

export type Discussion = {
  card: WordCard;
  comments: WordComment[];
  can_moderate: boolean;
};

/** The longest comment the API takes */
export const MAX_COMMENT = 2000;

export const getDiscussion = (formId: number) =>
  apiCall<Discussion>(`/api/forms/${formId}/discussion`);

export const addComment = (
  formId: number,
  body: string,
  replyTo: number | null,
  captcha: string,
) =>
  apiCall<Discussion>(`/api/forms/${formId}/comments`, "POST", {
    body,
    reply_to: replyTo,
    captcha,
  });

export const editComment = (id: number, body: string) =>
  apiCall<Discussion>(`/api/comments/${id}`, "PATCH", { body });

export const deleteComment = (id: number) =>
  apiCall<null>(`/api/comments/${id}`, "DELETE");

/** Members report as themselves (the cookie), guests with their browser's id. */
export const reportComment = (id: number, reason: string) =>
  apiCall<null>(`/api/comments/${id}/report`, "POST", {
    reason,
    voter: voterId(),
  });

export const hideComment = (id: number) =>
  apiCall<Discussion>(`/api/comments/${id}/hide`, "POST");

export const restoreComment = (id: number) =>
  apiCall<Discussion>(`/api/comments/${id}/restore`, "POST");
