"use client";

import { useLocale, useTranslations } from "next-intl";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAccount } from "@/components/Account";
import { Link, useRouter } from "@/i18n/navigation";
import { deleteAccount, resendVerification, signOut } from "@/lib/account";
import { localized } from "@/lib/api";
import {
  fetchProfile,
  type Profile,
  renameMember,
  setSpeaks,
  type TestableVariety,
  testableVarieties,
} from "@/lib/speaker";
import {
  listPublicVarieties,
  sortVarieties,
  type Variety,
} from "@/lib/varieties";

const BUTTON =
  "rounded-md border border-black/15 px-3 py-1.5 text-sm dark:border-white/20";

/** The member's profile: name, languages and speaker tests, contributions, the account. */
export default function AccountPanel() {
  const t = useTranslations("Account");
  const locale = useLocale();
  const { member, setMember } = useAccount();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [testable, setTestable] = useState<TestableVariety[]>([]);
  const [all, setAll] = useState<Variety[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [resent, setResent] = useState(false);

  const reload = useCallback(() => {
    fetchProfile()
      .then(setProfile)
      .catch(() => setProfile(null));
    testableVarieties()
      .then(setTestable)
      .catch(() => setTestable([]));
  }, []);
  useEffect(() => {
    if (!member) return;
    reload();
    listPublicVarieties()
      .then((varieties) => setAll(sortVarieties(varieties, locale)))
      .catch(() => setAll([]));
  }, [member, locale, reload]);

  const tests = useMemo(
    () => new Map(testable.map((v) => [v.code, v])),
    [testable],
  );

  if (member === undefined) return <p className="opacity-60">…</p>;
  if (member === null) {
    return (
      <p>
        <Link href="/login?next=/account">{t("signIn")}</Link>
      </p>
    );
  }

  const leave = async (remove: boolean) => {
    await (remove ? deleteAccount() : signOut()).catch(() => {});
    setMember(null);
    router.push("/");
  };
  const rename = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const name = String(new FormData(e.currentTarget).get("name") ?? "").trim();
    if (!name) return;
    await renameMember(name).catch(() => {});
    setMember({ ...member, name });
    setEditing(false);
  };
  const speaks = async (code: string, yes: boolean) => {
    await setSpeaks(code, yes).catch(() => {});
    reload();
  };

  const mine = new Set(profile?.varieties.map((v) => v.code));
  return (
    <div className="space-y-8">
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1">
        <dt className="opacity-60">{t("name")}</dt>
        <dd>
          {editing ? (
            <form onSubmit={rename} className="flex gap-2">
              <input
                name="name"
                defaultValue={member.name}
                required
                maxLength={60}
                className="min-w-0 rounded-md border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
              />
              <button type="submit" className={BUTTON}>
                {t("save")}
              </button>
            </form>
          ) : (
            <span className="font-medium">
              {member.name}{" "}
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="ml-1 text-sm font-normal underline opacity-70"
              >
                {t("rename")}
              </button>
            </span>
          )}
        </dd>
        <dt className="opacity-60">{t("email")}</dt>
        <dd>{member.email}</dd>
      </dl>
      {!member.email_verified && (
        <p className="rounded-md bg-amber-500/10 p-3 text-sm">
          {t("unverified")}{" "}
          {resent ? (
            <span className="font-medium">{t("verificationSent")}</span>
          ) : (
            <button
              type="button"
              onClick={() =>
                resendVerification(locale)
                  .then(() => setResent(true))
                  .catch(() => {})
              }
              className="underline"
            >
              {t("resendVerification")}
            </button>
          )}
        </p>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{t("languagesTitle")}</h2>
        <p className="text-sm opacity-80">{t("languagesIntro")}</p>
        {profile?.varieties.length ? (
          <ul className="divide-y divide-black/10 rounded-lg border border-black/10 dark:divide-white/10 dark:border-white/15">
            {profile.varieties.map((v) => {
              const test = tests.get(v.code);
              return (
                <li
                  key={v.code}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2"
                >
                  <span className="font-medium">
                    {localized(locale, v.name_en, v.name_uk, v.names)}
                  </span>
                  {v.tested ? (
                    <span className="rounded-full bg-green-600/10 px-2 py-0.5 text-xs text-green-800 dark:text-green-300">
                      ✓ {t("speaker")}
                    </span>
                  ) : test?.retry_after ? (
                    <span className="text-xs opacity-70">
                      {t("retryIn", {
                        hours: Math.ceil(test.retry_after / 3600),
                      })}
                    </span>
                  ) : test ? (
                    <Link
                      href={`/account/test/${v.code}`}
                      className="rounded-md bg-violet-600 px-2.5 py-1 text-xs font-medium text-white no-underline! hover:bg-violet-700"
                    >
                      {t("takeTest")}
                    </Link>
                  ) : (
                    <span className="text-xs opacity-60">{t("noTestYet")}</span>
                  )}
                  <button
                    type="button"
                    onClick={() => speaks(v.code, false)}
                    aria-label={t("remove")}
                    title={t("remove")}
                    className="ml-auto opacity-50 hover:opacity-100"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm opacity-60">{t("noLanguages")}</p>
        )}
        <label className="flex flex-wrap items-center gap-2 text-sm">
          {t("addLanguage")}
          <select
            value=""
            onChange={(e) => e.target.value && speaks(e.target.value, true)}
            className="max-w-full rounded-md border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          >
            <option value="">…</option>
            {all
              .filter((v) => !mine.has(v.code))
              .map((v) => (
                <option key={v.code} value={v.code}>
                  {v.kind === "dialect" ? "— " : ""}
                  {localized(locale, v.name_en, v.name_uk, v.names)}
                </option>
              ))}
          </select>
        </label>
        <p className="text-xs opacity-60">{t("levels")}</p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{t("contributionsTitle")}</h2>
        <p className="text-sm">
          {t("stats", {
            words: profile?.contribution_count ?? 0,
            votes: profile?.votes ?? 0,
          })}
        </p>
        {profile?.contributions.length ? (
          <ul className="space-y-1 text-sm">
            {profile.contributions.map((c, i) => (
              <li key={i}>
                <span className="font-medium">{c.spelling}</span>
                {c.recorded && " 🎙"}
                <span className="opacity-70">
                  {" — "}
                  {c.slug ? (
                    <Link href={`/word/${c.slug}`}>
                      {localized(locale, c.gloss_en, c.gloss_uk, c.glosses)}
                    </Link>
                  ) : (
                    localized(locale, c.gloss_en, c.gloss_uk, c.glosses)
                  )}
                  {", "}
                  {localized(
                    locale,
                    c.variety_name_en,
                    c.variety_name_uk,
                    c.variety_names,
                  )}
                  {" · "}
                  {t(`status.${c.status}`)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm opacity-60">{t("noContributions")}</p>
        )}
      </section>

      <div className="flex flex-wrap gap-2 border-t border-black/10 pt-6 dark:border-white/15">
        <button type="button" onClick={() => leave(false)} className={BUTTON}>
          {t("signOut")}
        </button>
        {!confirming ? (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-md border border-red-500/40 px-3 py-1.5 text-sm text-red-700 dark:text-red-300"
          >
            {t("delete")}
          </button>
        ) : (
          <span className="flex flex-wrap items-center gap-2 text-sm">
            {t("deleteConfirm")}
            <button
              type="button"
              onClick={() => leave(true)}
              className="rounded-md bg-red-600 px-3 py-1.5 text-white"
            >
              {t("deleteYes")}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="underline"
            >
              {t("deleteNo")}
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
