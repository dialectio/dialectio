"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import type { Form } from "@/lib/api";
import { localized } from "@/lib/api";
import {
  ABROAD,
  listVoterRegions,
  myRegion,
  myVotes,
  type RegionOption,
  sendReport,
  sendVote,
  setMyRegion,
  type VoteCounts,
} from "@/lib/feedback";

export type Counts = Pick<VoteCounts, "yes" | "no" | "community">;

/** What voting needs to know about a word. */
export type Checkable = Pick<Form, "id" | "unverified" | "votes_yes" | "votes_no" | "community">;

/** The word's trust mark: speakers confirmed it, disputed it, or nobody checked it yet (≈). */
export function TrustMark({ form, counts }: { form: Checkable; counts?: Counts }) {
  const t = useTranslations("Check");
  const tPanel = useTranslations("Panel");
  const { yes, no, community } = counts ?? {
    yes: form.votes_yes,
    no: form.votes_no,
    community: form.community,
  };
  if (!form.unverified) return null;
  const [mark, title] =
    community === "confirmed"
      ? ["👥", t("confirmed", { yes, no })]
      : community === "disputed"
        ? ["⚠", t("disputed", { yes, no })]
        : ["≈", tPanel("unverified")];
  return (
    <span title={title} aria-label={title} className="cursor-help text-sm opacity-70">
      {mark}
    </span>
  );
}

/** "Where do you live?" asked once, after the first vote. */
export function RegionQuestion({ onDone }: { onDone: () => void }) {
  const t = useTranslations("Check");
  const locale = useLocale();
  const [regions, setRegions] = useState<RegionOption[]>([]);

  useEffect(() => {
    listVoterRegions()
      .then(setRegions)
      .catch(() => {});
  }, []);

  const choose = (code: string) => {
    setMyRegion(code);
    onDone();
  };

  return (
    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
      <label htmlFor="voter-region" className="opacity-70">
        {t("whereLive")}
      </label>
      <select
        id="voter-region"
        defaultValue=""
        onChange={(e) => e.target.value && choose(e.target.value)}
        className="rounded border border-black/15 bg-transparent px-1 py-0.5 dark:border-white/20"
      >
        <option value="" disabled>
          …
        </option>
        {[true, false].map((inUkraine) => (
          <optgroup key={String(inUkraine)} label={inUkraine ? t("ukraine") : t("neighbours")}>
            {regions
              .filter((r) => r.in_ukraine === inUkraine)
              .map((r) => (
                <option key={r.code} value={r.code}>
                  {localized(locale, r.name_en, r.name_uk, r.names)}
                </option>
              ))}
          </optgroup>
        ))}
        <option value={ABROAD}>{t("abroad")}</option>
      </select>
      <button type="button" onClick={() => choose(ABROAD)} className="opacity-60 hover:underline">
        {t("skip")}
      </button>
    </div>
  );
}

function ReportForm({ form, onClose }: { form: Checkable; onClose: () => void }) {
  const t = useTranslations("Check");
  const [message, setMessage] = useState("");
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    setState("sending");
    try {
      await sendReport(form.id, message, website);
      setState("sent");
    } catch {
      setState("error");
    }
  };

  if (state === "sent") return <p className="mt-1 text-xs text-green-700">{t("reportThanks")}</p>;

  return (
    <form onSubmit={submit} className="mt-1 space-y-1">
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={t("reportPlaceholder")}
        aria-label={t("reportPlaceholder")}
        maxLength={1000}
        rows={2}
        className="w-full rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/20"
      />
      {/* Honeypot: hidden from people, bots fill it in */}
      <input
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="hidden"
        name="website"
      />
      <div className="flex gap-2 text-xs">
        <button
          type="submit"
          disabled={state === "sending" || !message.trim()}
          className="rounded bg-blue-600 px-2 py-1 text-white disabled:opacity-40"
        >
          {t("send")}
        </button>
        <button type="button" onClick={onClose} className="opacity-60 hover:underline">
          {t("cancel")}
        </button>
        {state === "error" && <span className="text-red-600">{t("error")}</span>}
      </div>
    </form>
  );
}

/**
 * Under a word: "Do people say it like this? Yes / No" for unverified words, and
 * "Mistake?" for every word. With askUsage, verified words get "Do people say it like this
 * where you live?" too: their votes don't change any mark, but the votes' regions show
 * where the word is actually used.
 */
export default function WordCheck({
  form,
  onCounts,
  askUsage = false,
}: {
  form: Checkable;
  onCounts: (counts: Counts) => void;
  askUsage?: boolean;
}) {
  const t = useTranslations("Check");
  const [myVote, setMyVote] = useState(0);
  const [counts, setCounts] = useState<Counts>({
    yes: form.votes_yes,
    no: form.votes_no,
    community: form.community,
  });
  const [askRegion, setAskRegion] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    // localStorage is only available in the browser, after hydration.
    setMyVote(myVotes()[form.id] ?? 0);
  }, [form.id]);

  const vote = async (value: number) => {
    const next = myVote === value ? 0 : value; // clicking your vote again takes it back
    setError(false);
    try {
      const result = await sendVote(form.id, next);
      setMyVote(next);
      setCounts(result);
      onCounts(result);
      if (next !== 0 && myRegion() === null) setAskRegion(true);
    } catch {
      setError(true);
    }
  };

  const regionAnswered = async () => {
    setAskRegion(false);
    // Attach the region to the vote just made.
    if (myVote !== 0) await sendVote(form.id, myVote).catch(() => {});
  };

  const button = (value: number, label: string, count: number) => (
    <button
      type="button"
      onClick={() => vote(value)}
      aria-pressed={myVote === value}
      className={`rounded-full border px-2 py-0.5 ${
        myVote === value
          ? value > 0
            ? "border-green-600 bg-green-600/10 text-green-800 dark:text-green-300"
            : "border-red-600 bg-red-600/10 text-red-800 dark:text-red-300"
          : "border-black/15 hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
      }`}
    >
      {label}
      {count > 0 && <span className="ml-1 opacity-70">{count}</span>}
    </button>
  );

  return (
    <div className="mt-1 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        {(form.unverified || askUsage) && (
          <>
            <span className="opacity-60">
              {form.unverified ? t("question") : t("usageQuestion")}
            </span>
            {button(1, t("yes"), counts.yes)}
            {button(-1, t("no"), counts.no)}
          </>
        )}
        {!reporting && (
          <button
            type="button"
            onClick={() => setReporting(true)}
            className="opacity-50 hover:underline hover:opacity-100"
          >
            {t("report")}
          </button>
        )}
        {error && <span className="text-red-600">{t("error")}</span>}
      </div>
      {askRegion && <RegionQuestion onDone={regionAnswered} />}
      {reporting && <ReportForm form={form} onClose={() => setReporting(false)} />}
    </div>
  );
}
