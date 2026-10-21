"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import ChangeLog from "@/components/ChangeLog";
import { API_URL, localized } from "@/lib/api";
import {
  addForm,
  decideExpert,
  type ExpertApplication,
  listChanges,
  listExperts,
  approveForm,
  changeSpelling,
  deleteForm,
  type EditorConcept,
  EditorError,
  type EditorForm,
  dismissMissing,
  type FeedbackItem,
  listConcepts,
  listFeedback,
  listMissing,
  type MissingSearch,
  listSubmissions,
  listVarieties,
  resolveReport,
  setPrimaryForm,
  type EditorVariety,
  type Submission,
} from "@/lib/editor";
import type { WordChange } from "@/lib/expert";
import { listVoterRegions } from "@/lib/feedback";
import { sortVarieties } from "@/lib/varieties";

const DEFAULT_VARIETY = "ukr";
// Rows rendered at once; thousands of rows with inputs make the page sluggish.
const MAX_ROWS = 200;
const TOKEN_KEY = "dialectio.editorToken";

const isApproved = (form: EditorForm) => form.status === "approved";

function readToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage unavailable (private mode): token just isn't remembered
  }
}

function ConceptRow({
  concept,
  token,
  variety,
  onChange,
}: {
  concept: EditorConcept;
  token: string;
  variety: string;
  onChange: (forms: EditorForm[]) => void;
}) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [spelling, setSpelling] = useState("");
  const [ipa, setIpa] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The word whose spelling is being fixed, and the new spelling
  const [editing, setEditing] = useState<{ id: number; spelling: string } | null>(null);

  const saveSpelling = async (e: FormEvent, form: EditorForm) => {
    e.preventDefault();
    if (!editing || !editing.spelling.trim()) return;
    setError(null);
    try {
      const updated = await changeSpelling(token, form.id, editing.spelling, form.ipa);
      onChange(concept.forms.map((f) => (f.id === form.id ? updated : f)));
      setEditing(null);
    } catch (err) {
      setError(err instanceof EditorError && err.status === 409 ? t("duplicate") : t("saveError"));
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!spelling.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const form = await addForm(token, {
        concept_id: concept.id,
        variety,
        spelling,
        ipa: ipa.trim() || null,
      });
      onChange([...concept.forms, form]);
      setSpelling("");
      setIpa("");
    } catch (err) {
      setError(err instanceof EditorError && err.status === 409 ? t("duplicate") : t("saveError"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (form: EditorForm) => {
    setError(null);
    try {
      await deleteForm(token, form.id);
      // the server may promote another approved word to primary; mirror the simple case
      const rest = concept.forms.filter((f) => f.id !== form.id);
      const next = rest.find(isApproved);
      if (form.is_primary && next && !rest.some((f) => f.is_primary)) {
        onChange(rest.map((f) => (f === next ? { ...f, is_primary: true } : f)));
      } else {
        onChange(rest);
      }
    } catch {
      setError(t("saveError"));
    }
  };

  const makePrimary = async (form: EditorForm) => {
    setError(null);
    try {
      const updated = await setPrimaryForm(token, form.id);
      onChange(
        concept.forms.map((f) => (f.id === form.id ? updated : { ...f, is_primary: false })),
      );
    } catch {
      setError(t("saveError"));
    }
  };

  const approve = async (form: EditorForm) => {
    setError(null);
    try {
      const updated = await approveForm(token, form.id);
      onChange(concept.forms.map((f) => (f.id === form.id ? updated : f)));
    } catch {
      setError(t("saveError"));
    }
  };

  const description = localized(locale, concept.description_en, concept.description_uk);

  return (
    <li className="grid gap-2 border-b border-black/10 py-3 md:grid-cols-[1fr_1fr] dark:border-white/10">
      <div>
        <div className="font-medium">
          {localized(locale, concept.gloss_en, concept.gloss_uk)}
          {concept.wikidata_id && (
            <a
              href={`https://www.wikidata.org/wiki/${concept.wikidata_id}`}
              target="_blank"
              rel="noreferrer"
              className="ml-2 text-xs font-normal opacity-50 underline"
            >
              {concept.wikidata_id}
            </a>
          )}
        </div>
        {description && <div className="text-sm opacity-70">{description}</div>}
        <div className="mt-1 text-xs opacity-60">
          {Object.entries(concept.hints)
            .map(([lang, word]) => `${lang}: ${word}`)
            .join(" · ")}
        </div>
      </div>
      <div>
        <div className="mb-1 flex flex-wrap gap-1">
          {concept.forms.map((form) => (
            <span
              key={form.id}
              title={isApproved(form) ? (form.source ?? undefined) : t("draftHint")}
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-sm ${
                !isApproved(form)
                  ? "border border-dashed border-amber-500 bg-amber-500/10"
                  : form.is_primary
                    ? "bg-blue-500/15 font-semibold"
                    : "bg-black/5 dark:bg-white/10"
              }`}
            >
              {editing?.id === form.id ? (
                <form onSubmit={(e) => saveSpelling(e, form)} className="inline-flex gap-1">
                  <input
                    autoFocus
                    value={editing.spelling}
                    onChange={(e) => setEditing({ id: form.id, spelling: e.target.value })}
                    onKeyDown={(e) => e.key === "Escape" && setEditing(null)}
                    aria-label={t("edit", { word: form.spelling })}
                    className="w-32 rounded border border-black/20 bg-white px-1 text-black"
                  />
                  <button type="submit" title={t("saveSpelling")} className="text-green-700">
                    ✓
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    title={t("cancelEdit")}
                    className="opacity-60"
                  >
                    ↺
                  </button>
                </form>
              ) : (
                form.spelling
              )}
              {form.ipa && <span className="font-mono text-xs opacity-70">{form.ipa}</span>}
              {form.editable && editing?.id !== form.id && (
                <button
                  type="button"
                  onClick={() => setEditing({ id: form.id, spelling: form.spelling })}
                  title={t("edit", { word: form.spelling })}
                  aria-label={t("edit", { word: form.spelling })}
                  className="opacity-50 hover:opacity-100"
                >
                  ✎
                </button>
              )}
              {form.editable && !form.is_primary && form.status !== "submitted" && (
                <button
                  type="button"
                  onClick={() => makePrimary(form)}
                  title={t("makePrimary")}
                  aria-label={t("makePrimaryWord", { word: form.spelling })}
                  className="text-amber-600 opacity-70 hover:opacity-100"
                >
                  ★
                </button>
              )}
              {!isApproved(form) && (
                <button
                  type="button"
                  onClick={() => approve(form)}
                  aria-label={t("approve", { word: form.spelling })}
                  className="font-semibold text-green-700 hover:text-green-500 dark:text-green-400"
                >
                  ✓
                </button>
              )}
              {form.editable && (
                <button
                  type="button"
                  onClick={() => remove(form)}
                  aria-label={t("delete", { word: form.spelling })}
                  className="opacity-60 hover:opacity-100"
                >
                  ✕
                </button>
              )}
            </span>
          ))}
        </div>
        <form onSubmit={submit} className="flex gap-2">
          <input
            value={spelling}
            onChange={(e) => setSpelling(e.target.value)}
            placeholder={t("wordPlaceholder")}
            aria-label={t("wordPlaceholder")}
            className="min-w-0 flex-1 rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          />
          <input
            value={ipa}
            onChange={(e) => setIpa(e.target.value)}
            placeholder={t("ipaPlaceholder")}
            aria-label={t("ipaPlaceholder")}
            className="w-28 rounded border border-black/15 bg-transparent px-2 py-1 font-mono dark:border-white/20"
          />
          <button
            type="submit"
            disabled={busy || !spelling.trim()}
            className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-40"
          >
            {t("add")}
          </button>
        </form>
        {error && <div className="mt-1 text-sm text-red-600">{error}</div>}
      </div>
    </li>
  );
}

function Feedback({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [regionNames, setRegionNames] = useState<Record<string, string>>({});
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listFeedback(token)
      .then((result) => !cancelled && setItems(result))
      .catch(() => !cancelled && setError(true));
    listVoterRegions()
      .then(
        (regions) =>
          !cancelled &&
          setRegionNames(
            Object.fromEntries(regions.map((r) => [r.code, localized(locale, r.name_en, r.name_uk)])),
          ),
      )
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, locale]);

  const act = async (item: FeedbackItem, approve: boolean) => {
    setError(false);
    try {
      if (approve) {
        const form = await approveForm(token, item.form.id);
        setItems((all) => all.map((i) => (i.form.id === form.id ? { ...i, form } : i)));
      } else {
        await deleteForm(token, item.form.id);
        setItems((all) => all.filter((i) => i.form.id !== item.form.id));
      }
    } catch {
      setError(true);
    }
  };

  const resolve = async (item: FeedbackItem, reportId: number) => {
    setError(false);
    try {
      await resolveReport(token, reportId);
      setItems((all) =>
        all.map((i) =>
          i === item ? { ...i, reports: i.reports.filter((r) => r.id !== reportId) } : i,
        ),
      );
    } catch {
      setError(true);
    }
  };

  if (items.length === 0 && !error) return null;
  return (
    <section className="mb-6 rounded-lg border border-sky-500/40 bg-sky-500/5 p-3">
      <h2 className="mb-2 font-semibold">{t("feedback", { count: items.length })}</h2>
      {error && <p className="text-sm text-red-600">{t("saveError")}</p>}
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.form.id} className="text-sm">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="opacity-70">
                {localized(locale, item.concept_gloss_en, item.concept_gloss_uk)} ·{" "}
                {localized(locale, item.variety_name_en, item.variety_name_uk)}
              </span>
              <span className="text-base font-semibold">{item.form.spelling}</span>
              <span>
                👍 {item.yes} · 👎 {item.no}
              </span>
              {item.community === "confirmed" && <span>{t("confirmedLabel")}</span>}
              {item.community === "disputed" && (
                <span className="font-semibold text-red-700 dark:text-red-400">
                  {t("disputedLabel")}
                </span>
              )}
              {item.concept_slug && (
                <a
                  href={`/${locale}/word/${item.concept_slug}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs underline opacity-60"
                >
                  {t("openWord")}
                </a>
              )}
              {item.form.status !== "approved" && (
                <button
                  type="button"
                  onClick={() => act(item, true)}
                  aria-label={t("approve", { word: item.form.spelling })}
                  className="font-semibold text-green-700 dark:text-green-400"
                >
                  ✓
                </button>
              )}
              {item.form.editable && (
                <button
                  type="button"
                  onClick={() => act(item, false)}
                  aria-label={t("delete", { word: item.form.spelling })}
                  className="opacity-60 hover:opacity-100"
                >
                  ✕
                </button>
              )}
            </div>
            {Object.keys(item.regions).length > 0 && (
              <div className="text-xs opacity-70">
                {Object.entries(item.regions)
                  .map(([code, [yes, no]]) => `${regionNames[code] ?? code}: 👍${yes} 👎${no}`)
                  .join(" · ")}
              </div>
            )}
            {item.reports.map((report) => (
              <div key={report.id} className="mt-1 flex items-start gap-2 text-xs">
                <span className="rounded bg-amber-500/15 px-2 py-0.5">
                  {report.message}
                  {report.region_code && (
                    <span className="opacity-60">
                      {" "}
                      — {regionNames[report.region_code] ?? report.region_code}
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => resolve(item, report.id)}
                  className="underline opacity-60 hover:opacity-100"
                >
                  {t("resolve")}
                </button>
              </div>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Missing({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const [items, setItems] = useState<MissingSearch[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listMissing(token)
      .then((result) => !cancelled && setItems(result))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [token]);

  const dismiss = async (query: string) => {
    setError(false);
    try {
      await dismissMissing(token, query);
      setItems((all) => all.filter((i) => i.query !== query));
    } catch {
      setError(true);
    }
  };

  if (items.length === 0 && !error) return null;
  return (
    <section className="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
      <h2 className="font-semibold">{t("missing", { count: items.length })}</h2>
      <p className="mb-2 text-xs opacity-70">{t("missingHint")}</p>
      {error && <p className="text-sm text-red-600">{t("saveError")}</p>}
      <ul className="flex flex-wrap gap-2">
        {items.map((item) => (
          <li
            key={item.query}
            className="inline-flex items-center gap-1 rounded bg-black/5 px-2 py-0.5 text-sm dark:bg-white/10"
          >
            <a
              href={`https://en.wiktionary.org/wiki/Special:Search?search=${encodeURIComponent(item.query)}`}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              {item.query}
            </a>
            <span className="text-xs opacity-60">×{item.count}</span>
            <button
              type="button"
              onClick={() => dismiss(item.query)}
              aria-label={t("dismiss", { word: item.query })}
              className="opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Submissions({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [items, setItems] = useState<Submission[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listSubmissions(token)
      .then((result) => !cancelled && setItems(result))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [token]);

  const act = async (item: Submission, approve: boolean) => {
    setError(false);
    try {
      await (approve ? approveForm(token, item.form.id) : deleteForm(token, item.form.id));
      setItems((all) => all.filter((i) => i.form.id !== item.form.id));
    } catch {
      setError(true);
    }
  };

  if (items.length === 0 && !error) return null;
  return (
    <section className="mb-6 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3">
      <h2 className="mb-2 font-semibold">{t("submissions", { count: items.length })}</h2>
      {error && <p className="text-sm text-red-600">{t("saveError")}</p>}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.form.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="opacity-70">
              {localized(locale, item.concept_gloss_en, item.concept_gloss_uk)} ·{" "}
              {localized(locale, item.variety_name_en, item.variety_name_uk)}
            </span>
            <span className="text-base font-semibold">{item.form.spelling}</span>
            {item.form.place && <span className="opacity-70">📍 {item.form.place}</span>}
            {item.form.contributor && <span className="opacity-70">— {item.form.contributor}</span>}
            {item.form.audio_urls.map((url) => (
              <audio key={url} src={`${API_URL}${url}`} controls className="h-8" />
            ))}
            <button
              type="button"
              onClick={() => act(item, true)}
              aria-label={t("approve", { word: item.form.spelling })}
              className="font-semibold text-green-700 dark:text-green-400"
            >
              ✓
            </button>
            <button
              type="button"
              onClick={() => act(item, false)}
              aria-label={t("delete", { word: item.form.spelling })}
              className="opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Applications to be an expert of a language or dialect, and the experts. */
function Experts({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [items, setItems] = useState<ExpertApplication[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listExperts(token)
      .then((result) => !cancelled && setItems(result))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [token]);

  const decide = async (item: ExpertApplication, status: "expert" | "declined") => {
    setError(false);
    try {
      await decideExpert(token, item.user_id, item.variety_code, status);
      setItems((all) =>
        all.map((i) =>
          i.user_id === item.user_id && i.variety_code === item.variety_code ? { ...i, status } : i,
        ),
      );
    } catch {
      setError(true);
    }
  };

  if (items.length === 0 && !error) return null;
  const waiting = items.filter((i) => i.status === "applied").length;
  return (
    <section className="mb-6 rounded-lg border border-violet-500/40 bg-violet-500/5 p-3">
      <h2 className="mb-2 font-semibold">{t("experts", { count: waiting })}</h2>
      {error && <p className="text-sm text-red-600">{t("saveError")}</p>}
      <ul className="space-y-2 text-sm">
        {items.map((item) => (
          <li key={`${item.user_id}-${item.variety_code}`} className="space-y-1">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-semibold">{item.name}</span>
              <span className="opacity-70">{item.email}</span>
              <span>{localized(locale, item.variety_name_en, item.variety_name_uk)}</span>
              <span className="rounded bg-black/5 px-2 py-0.5 text-xs dark:bg-white/10">
                {t(`expertStatus.${item.status}`)}
              </span>
              {item.status !== "expert" && (
                <button
                  type="button"
                  onClick={() => decide(item, "expert")}
                  className="font-semibold text-green-700 dark:text-green-400"
                >
                  {t("makeExpert")}
                </button>
              )}
              {item.status !== "declined" && (
                <button
                  type="button"
                  onClick={() => decide(item, "declined")}
                  className="opacity-70 hover:opacity-100"
                >
                  {item.status === "expert" ? t("revokeExpert") : t("declineExpert")}
                </button>
              )}
            </p>
            {item.note && <p className="opacity-80">„{item.note}“</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** What editors and experts did to words, newest first. */
function Changes({ token }: { token: string }) {
  const t = useTranslations("Editor");
  const [changes, setChanges] = useState<WordChange[] | null>(null);
  return (
    <details
      className="mb-6 rounded-lg border border-black/10 p-3 dark:border-white/15"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && changes === null)
          listChanges(token)
            .then(setChanges)
            .catch(() => setChanges([]));
      }}
    >
      <summary className="cursor-pointer font-semibold">{t("changes")}</summary>
      <div className="mt-2">{changes ? <ChangeLog changes={changes} /> : "…"}</div>
    </details>
  );
}

export default function WordEditor() {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [concepts, setConcepts] = useState<EditorConcept[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(true);
  const [filter, setFilter] = useState("");
  const [varieties, setVarieties] = useState<EditorVariety[]>([]);
  const [variety, setVariety] = useState(DEFAULT_VARIETY);

  useEffect(() => {
    // localStorage is only available in the browser, after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(readToken());
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    listVarieties(token)
      .then((result) => !cancelled && setVarieties(result))
      .catch(() => {});
    listConcepts(token, variety)
      .then((result) => {
        if (cancelled) return;
        setConcepts(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setConcepts(null);
        setError(
          err instanceof EditorError && err.status === 401
            ? t("badToken")
            : err instanceof EditorError && err.status === 503
              ? t("disabled")
              : t("loadError"),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token, variety, t]);

  const login = (e: FormEvent) => {
    e.preventDefault();
    saveToken(tokenInput.trim());
    setToken(tokenInput.trim());
  };

  const done = concepts?.filter((c) => c.forms.some(isApproved)).length ?? 0;
  const drafts = concepts?.filter((c) => c.forms.some((f) => !isApproved(f))).length ?? 0;
  const needle = filter.trim().toLowerCase();
  const visible = (concepts ?? []).filter(
    (c) =>
      (!onlyMissing || !c.forms.some(isApproved)) &&
      (!needle ||
        localized(locale, c.gloss_en, c.gloss_uk).toLowerCase().includes(needle) ||
        Object.values(c.hints).some((w) => w.toLowerCase().includes(needle))),
  );

  return (
    <main className="mx-auto min-h-0 w-full max-w-5xl flex-1 overflow-y-auto p-4">
      <h1 className="text-2xl font-semibold">
        {t("title", {
          variety: localized(
            locale,
            varieties.find((v) => v.code === variety)?.name_en ?? variety,
            varieties.find((v) => v.code === variety)?.name_uk ?? null,
          ),
        })}
      </h1>
      <p className="mb-4 text-sm opacity-70">{t("intro")}</p>

      {(!token || error) && (
        <form onSubmit={login} className="mb-4 flex gap-2">
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder={t("tokenPlaceholder")}
            aria-label={t("tokenPlaceholder")}
            className="w-80 rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          />
          <button type="submit" className="rounded bg-blue-600 px-3 py-1 text-white">
            {t("login")}
          </button>
        </form>
      )}
      {error && <p className="mb-4 text-red-600">{error}</p>}

      {token && !error && <Submissions token={token} />}
      {token && !error && <Feedback token={token} />}
      {token && !error && <Missing token={token} />}
      {token && !error && <Experts token={token} />}
      {token && !error && <Changes token={token} />}

      {concepts && (
        <>
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-4 bg-[var(--background)] py-2">
            <select
              value={variety}
              onChange={(e) => {
                setConcepts(null);
                setVariety(e.target.value);
              }}
              aria-label={t("variety")}
              className="rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
            >
              {sortVarieties(varieties, locale).map((v) => (
                <option key={v.code} value={v.code}>
                  {v.kind === "dialect" ? "— " : ""}
                  {localized(locale, v.name_en, v.name_uk)}
                </option>
              ))}
            </select>
            <span className="font-medium">
              {t("progress", { done, total: concepts.length })}
            </span>
            {drafts > 0 && (
              <span className="rounded bg-amber-500/15 px-2 py-0.5 text-sm">
                {t("drafts", { count: drafts })}
              </span>
            )}
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={onlyMissing}
                onChange={(e) => setOnlyMissing(e.target.checked)}
              />
              {t("onlyMissing")}
            </label>
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={t("filterPlaceholder")}
              aria-label={t("filterPlaceholder")}
              className="rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/20"
            />
          </div>
          <ul>
            {visible.slice(0, MAX_ROWS).map((concept) => (
              <ConceptRow
                key={concept.id}
                concept={concept}
                token={token}
                variety={variety}
                onChange={(forms) =>
                  setConcepts((all) =>
                    all ? all.map((c) => (c.id === concept.id ? { ...c, forms } : c)) : all,
                  )
                }
              />
            ))}
          </ul>
          {visible.length > MAX_ROWS && (
            <p className="py-4 text-sm opacity-70">
              {t("moreRows", { shown: MAX_ROWS, total: visible.length })}
            </p>
          )}
          {visible.length === 0 && <p className="py-4 opacity-70">{t("allDone")}</p>}
        </>
      )}
    </main>
  );
}
