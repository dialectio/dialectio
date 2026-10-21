"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAccount } from "@/components/Account";
import ChangeLog from "@/components/ChangeLog";
import { Link } from "@/i18n/navigation";
import { API_URL, localized } from "@/lib/api";
import {
  type ExpertRole,
  expertApprove,
  expertPrimary,
  expertReject,
  expertResolve,
  expertSpelling,
  fetchChanges,
  fetchQueue,
  fetchRoles,
  type QueueItem,
  type WordChange,
} from "@/lib/expert";

const BUTTON =
  "rounded-md border border-black/15 px-2.5 py-1 text-sm hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10";

/** An expert's work: the variety's submitted words, drafts and reports, and its change log. */
export default function ExpertView() {
  const t = useTranslations("Expert");
  const locale = useLocale();
  const { member } = useAccount();
  const [roles, setRoles] = useState<ExpertRole[] | null>(null);
  const [variety, setVariety] = useState("");
  const [queue, setQueue] = useState<QueueItem[] | null>(null);
  const [changes, setChanges] = useState<WordChange[]>([]);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });

  useEffect(() => {
    if (!member) return;
    fetchRoles()
      .then((all) => {
        const mine = all.filter((r) => r.status === "expert");
        setRoles(mine);
        setVariety((current) => current || mine[0]?.variety_code || "");
      })
      .catch(() => setRoles([]));
  }, [member]);

  const reload = useCallback(() => {
    if (!variety) return;
    fetchQueue(variety)
      .then(setQueue)
      .catch(() => setError(true));
    fetchChanges(variety)
      .then(setChanges)
      .catch(() => setChanges([]));
  }, [variety]);
  useEffect(reload, [reload]);

  if (member === undefined || (member && roles === null))
    return <p className="opacity-60">…</p>;
  if (member === null) {
    return (
      <p>
        <Link href="/login?next=/expert">{t("signIn")}</Link>
      </p>
    );
  }
  if (!roles?.length) {
    return (
      <p>
        {t("notExpert")} <Link href="/account">{t("toProfile")}</Link>
      </p>
    );
  }

  const act = async (action: () => Promise<unknown>) => {
    setError(false);
    try {
      await action();
      setEditing(null);
      reload();
    } catch {
      setError(true);
    }
  };
  const saveSpelling = (e: FormEvent<HTMLFormElement>, id: number) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const spelling = String(form.get("spelling") ?? "").trim();
    const ipa = String(form.get("ipa") ?? "").trim() || null;
    if (spelling) act(() => expertSpelling(id, spelling, ipa));
  };

  return (
    <div className="space-y-6">
      <p>{t("intro")}</p>
      {roles.length > 1 && (
        <select
          value={variety}
          onChange={(e) => setVariety(e.target.value)}
          aria-label={t("variety")}
          className="rounded-md border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
        >
          {roles.map((r) => (
            <option key={r.variety_code} value={r.variety_code}>
              {localized(
                locale,
                r.variety_name_en,
                r.variety_name_uk,
                r.variety_names,
              )}
            </option>
          ))}
        </select>
      )}
      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">{t("error")}</p>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">
          {t("queueTitle", { count: queue?.length ?? 0 })}
        </h2>
        {queue?.length === 0 && (
          <p className="text-sm opacity-60">{t("queueEmpty")}</p>
        )}
        <ul className="divide-y divide-black/10 rounded-lg border border-black/10 dark:divide-white/10 dark:border-white/15">
          {queue?.map((item) => {
            const { form } = item;
            const open = form.status !== "approved";
            return (
              <li key={form.id} className="space-y-2 px-3 py-3">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-lg font-semibold">{form.spelling}</span>
                  {form.ipa && <span className="opacity-70">[{form.ipa}]</span>}
                  <span className="text-sm opacity-80">
                    {item.concept_slug ? (
                      <Link href={`/word/${item.concept_slug}`}>
                        {localized(
                          locale,
                          item.concept_gloss_en,
                          item.concept_gloss_uk,
                          item.concept_glosses,
                        )}
                      </Link>
                    ) : (
                      localized(
                        locale,
                        item.concept_gloss_en,
                        item.concept_gloss_uk,
                        item.concept_glosses,
                      )
                    )}
                    {" · "}
                    {localized(
                      locale,
                      item.variety_name_en,
                      item.variety_name_uk,
                      item.variety_names,
                    )}
                  </span>
                  <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs dark:bg-white/10">
                    {t(`status.${form.status}`)}
                  </span>
                </div>
                {(form.contributor || form.place) && (
                  <p className="text-sm opacity-70">
                    {form.contributor && `— ${form.contributor}`}
                    {form.place && ` 📍 ${form.place}`}
                  </p>
                )}
                {form.audio_urls.map((url) => (
                  <audio
                    key={url}
                    src={`${API_URL}${url}`}
                    controls
                    className="h-8"
                  />
                ))}
                {(item.yes > 0 || item.no > 0) && (
                  <p className="text-xs opacity-70">
                    {t("votes", {
                      yes: number.format(item.yes),
                      no: number.format(item.no),
                    })}
                  </p>
                )}
                {item.reports.map((report) => (
                  <p
                    key={report.id}
                    className="flex flex-wrap items-center gap-2 rounded-md bg-amber-500/10 px-2 py-1 text-sm"
                  >
                    ⚠ {report.message}
                    <button
                      type="button"
                      onClick={() => act(() => expertResolve(report.id))}
                      className="underline"
                    >
                      {t("resolve")}
                    </button>
                  </p>
                ))}
                {editing === form.id ? (
                  <form
                    onSubmit={(e) => saveSpelling(e, form.id)}
                    className="flex flex-wrap gap-2"
                  >
                    <input
                      name="spelling"
                      defaultValue={form.spelling}
                      required
                      maxLength={200}
                      aria-label={t("spelling")}
                      className="rounded-md border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
                    />
                    <input
                      name="ipa"
                      defaultValue={form.ipa ?? ""}
                      maxLength={200}
                      placeholder="IPA"
                      aria-label="IPA"
                      className="w-32 rounded-md border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
                    />
                    <button type="submit" className={BUTTON}>
                      {t("save")}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(null)}
                      className="text-sm underline"
                    >
                      {t("cancel")}
                    </button>
                  </form>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {open && (
                      <button
                        type="button"
                        onClick={() => act(() => expertApprove(form.id))}
                        className="rounded-md bg-green-700 px-2.5 py-1 text-sm text-white hover:bg-green-800"
                      >
                        ✓ {t("approve")}
                      </button>
                    )}
                    {open && (
                      <button
                        type="button"
                        onClick={() => act(() => expertReject(form.id))}
                        className="rounded-md border border-red-500/40 px-2.5 py-1 text-sm text-red-700 dark:text-red-300"
                      >
                        {t("reject")}
                      </button>
                    )}
                    {form.editable && (
                      <button
                        type="button"
                        onClick={() => setEditing(form.id)}
                        className={BUTTON}
                      >
                        {t("edit")}
                      </button>
                    )}
                    {!open && !form.is_primary && form.editable && (
                      <button
                        type="button"
                        onClick={() => act(() => expertPrimary(form.id))}
                        className={BUTTON}
                      >
                        {t("makePrimary")}
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{t("changesTitle")}</h2>
        <ChangeLog changes={changes} />
      </section>
    </div>
  );
}
