import { apiCall as call } from "@/lib/account";
import type { Names } from "@/lib/api";

/** A language or dialect with a speaker test, and the member's state in it. */
export type TestableVariety = {
  code: string;
  kind: "language" | "dialect";
  name_en: string;
  name_uk: string | null;
  names: Names;
  words: number;
  speaks: boolean;
  tested: boolean;
  retry_after: number | null;
};

export type SpeakerCard = {
  index: number;
  spelling: string;
  meaning: string;
  /** The meaning is a description (the test's language is the interface language) */
  described: boolean;
  token: string;
};

export type SpeakerTest = {
  id: number | null;
  cards: SpeakerCard[];
  pass_mark: number;
  retry_after: number | null;
};

export type CardResult = {
  correct: boolean;
  answered: number;
  score: number;
  finished: boolean;
  passed: boolean | null;
};

export type Profile = {
  varieties: {
    code: string;
    kind: "language" | "dialect";
    name_en: string;
    name_uk: string | null;
    names: Names;
    tested: boolean;
  }[];
  contributions: {
    spelling: string;
    status: "submitted" | "approved" | "pending";
    slug: string | null;
    gloss_en: string;
    gloss_uk: string | null;
    glosses: Names;
    variety_code: string;
    variety_name_en: string;
    variety_name_uk: string | null;
    variety_names: Names;
    recorded: boolean;
  }[];
  contribution_count: number;
  votes: number;
};

export const testableVarieties = () =>
  call<TestableVariety[]>("/api/speaker/varieties");

export const startTest = (variety: string, locale: string) =>
  call<SpeakerTest>("/api/speaker/tests", "POST", { variety, locale });

export const answerCard = (testId: number, token: string, value: -1 | 0 | 1) =>
  call<CardResult>(`/api/speaker/tests/${testId}/answers`, "POST", {
    token,
    value,
  });

/** Say one speaks a language or dialect (a hint in the profile), or take it back. */
export const setSpeaks = (variety: string, speaks: boolean) =>
  call<null>("/api/speaker/speaks", "PUT", { variety, speaks });

export const fetchProfile = () => call<Profile>("/api/profile");

export const renameMember = (name: string) =>
  call<null>("/api/profile/name", "PUT", { name });
