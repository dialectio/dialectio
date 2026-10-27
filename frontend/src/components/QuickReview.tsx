"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { API_URL, localized } from "@/lib/api";
import {
  approveForm,
  deleteForm,
  listReview,
  listReviewVarieties,
  type ReviewVariety,
} from "@/lib/editor";
import type { QueueItem } from "@/lib/expert";

/**
 * The editors' quick review: one waiting word at a time, decided with a key.
 * → approve, ← reject (pressed twice: it deletes the draft), ↓ skip.
 */
export default function QuickReview({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [varieties, setVarieties] = useState<ReviewVariety[]>([]);
  const [variety, setVariety] = useState("");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [index, setIndex] = useState(0);
  const [confirmReject, setConfirmReject] = useState(false);
  const [done, setDone] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    listReviewVarieties(token)
      .then((list) => {
        setVarieties(list);
        setVariety((current) => current || list[0]?.code || "");
      })
      .catch(() => setError(true));
  }, [token]);

  useEffect(() => {
    if (!variety) return;
    listReview(token, variety)
      .then((items) => {
        setQueue(items);
        setIndex(0);
      })
      .catch(() => setError(true));
  }, [token, variety]);

  const item = queue[index];

  const decide = useCallback(
    async (action: "approve" | "reject" | "skip") => {
      if (!item || busy) return;
      if (action === "reject" && !confirmReject) {
        setConfirmReject(true);
        return;
      }
      setConfirmReject(false);
      if (action === "skip") {
        setIndex((i) => i + 1);
        return;
      }
      setBusy(true);
      setError(false);
      try {
        await (action === "approve"
          ? approveForm(token, item.form.id)
          : deleteForm(token, item.form.id));
        setDone((n) => n + 1);
        setIndex((i) => i + 1);
        setVarieties((list) =>
          list.map((v) =>
            v.code === item.variety_code ? { ...v, waiting: v.waiting - 1 } : v,
          ),
        );
      } catch {
        setError(true);
      } finally {
        setBusy(false);
      }
    },
    [item, busy, confirmReject, token],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea, select")) return;
      const action = {
        ArrowRight: "approve",
        ArrowLeft: "reject",
        ArrowDown: "skip",
      }[e.key] as "approve" | "reject" | "skip" | undefined;
      if (!action) {
        if (e.key === "Escape") setConfirmReject(false);
        return;
      }
      e.preventDefault();
      decide(action);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide]);

  const meaning = item
    ? localized(
        locale,
        item.concept_gloss_en,
        item.concept_gloss_uk,
        item.concept_glosses,
      )
    : "";
  const description = item
    ? locale === "uk"
      ? (item.concept_description_uk ?? item.concept_description_en)
      : item.concept_description_en
    : null;

  return (
    <section className="mb-6 rounded-lg border border-sky-500/40 bg-sky-500/5 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">{t("quickReview")}</h2>
        <select
          value={variety}
          onChange={(e) => setVariety(e.target.value)}
          aria-label={t("variety")}
          className="rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/20"
        >
          {varieties.map((v) => (
            <option key={v.code} value={v.code}>
              {localized(locale, v.name_en, v.name_uk)} ({v.waiting})
            </option>
          ))}
        </select>
        <span className="text-sm opacity-70">
          {t("reviewProgress", {
            done,
            left: Math.max(0, queue.length - index),
          })}
        </span>
      </div>
      {error && <p className="text-sm text-red-600">{t("saveError")}</p>}
      {!item ? (
        <p className="py-4 text-sm opacity-70">{t("reviewEmpty")}</p>
      ) : (
        <div className="rounded-lg bg-[var(--background)] p-4 shadow-sm">
          <p className="text-xs tracking-wide uppercase opacity-60">
            {localized(locale, item.variety_name_en, item.variety_name_uk)}
            {" · "}
            {t(`reviewStatus.${item.form.status}`)}
          </p>
          <p className="my-1 font-serif text-3xl font-semibold">
            {item.form.spelling}
            {item.form.ipa && (
              <span className="ml-2 text-base font-normal opacity-60">
                [{item.form.ipa}]
              </span>
            )}
          </p>
          <p>
            {t("reviewMeans")} <strong>{meaning}</strong>
            {item.standard && item.standard !== item.form.spelling && (
              <span className="opacity-70">
                {" "}
                · {t("reviewStandard", { word: item.standard })}
              </span>
            )}
          </p>
          {description && (
            <p className="mt-1 text-sm opacity-70">{description}</p>
          )}
          {(item.yes > 0 || item.no > 0) && (
            <p className="mt-2 text-sm">
              {t("reviewVotes", {
                yes: Math.round(item.yes * 100) / 100,
                no: Math.round(item.no * 100) / 100,
              })}
            </p>
          )}
          {item.reports.map((r) => (
            <p
              key={r.id}
              className="mt-1 rounded bg-amber-500/10 px-2 py-1 text-sm"
            >
              ⚠ {r.message}
            </p>
          ))}
          {item.form.contributor && (
            <p className="mt-1 text-sm opacity-70">
              — {item.form.contributor}
              {item.form.place && ` 📍 ${item.form.place}`}
            </p>
          )}
          {item.form.audio_urls.map((url) => (
            <audio
              key={url}
              src={`${API_URL}${url}`}
              controls
              className="mt-2 h-8"
            />
          ))}
          {item.concept_slug && (
            <a
              href={`/${locale}/word/${item.concept_slug}`}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-sm"
            >
              {t("openWord")} ↗
            </a>
          )}
          <div className="mt-4 grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => decide("reject")}
              disabled={busy}
              className={`rounded-lg border py-2 ${
                confirmReject
                  ? "border-red-600 bg-red-600 text-white"
                  : "border-red-500/40 text-red-700 dark:text-red-300"
              }`}
            >
              ← {confirmReject ? t("reviewRejectSure") : t("reviewReject")}
            </button>
            <button
              type="button"
              onClick={() => decide("skip")}
              disabled={busy}
              className="rounded-lg border border-black/15 py-2 dark:border-white/20"
            >
              ↓ {t("reviewSkip")}
            </button>
            <button
              type="button"
              onClick={() => decide("approve")}
              disabled={busy}
              className="rounded-lg bg-green-700 py-2 font-medium text-white hover:bg-green-800"
            >
              {t("reviewApprove")} →
            </button>
          </div>
          <p className="mt-2 text-center text-xs opacity-60">
            {t("reviewKeys")}
          </p>
        </div>
      )}
    </section>
  );
}
