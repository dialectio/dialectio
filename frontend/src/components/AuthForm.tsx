"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { useAccount } from "@/components/Account";
import { useRouter } from "@/i18n/navigation";
import {
  AccountError,
  forgotPassword,
  googleSignInUrl,
  register,
  rememberNext,
  sendLoginLink,
  signIn,
} from "@/lib/account";

const FIELD =
  "w-full rounded-md border border-black/15 bg-transparent px-3 py-2 dark:border-white/20";

type Mode = "signIn" | "register" | "forgot" | "link";

/** Sign in with Google, with an email and a password or with a link sent by email, create an
 * account (email, password, the name shown under contributions), or ask for a new password.
 * `failed` is the reason Google sign-in came back with. */
export default function AuthForm({
  next,
  failed,
}: {
  next: string;
  failed?: string;
}) {
  const t = useTranslations("Account");
  const locale = useLocale();
  const router = useRouter();
  const { setMember } = useAccount();
  const [mode, setMode] = useState<Mode>("signIn");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const message = (code: string) =>
    t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.other");
  const [error, setError] = useState<string | null>(
    failed ? message(failed) : null,
  );
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "");
    setBusy(true);
    setError(null);
    try {
      if (mode === "forgot" || mode === "link") {
        if (mode === "link") rememberNext(next);
        await (mode === "link" ? sendLoginLink : forgotPassword)(
          field("email"),
          locale,
        );
        setSentTo(field("email"));
        return;
      }
      const member =
        mode === "signIn"
          ? await signIn(field("email"), field("password"))
          : await register({
              email: field("email"),
              password: field("password"),
              name: field("name"),
              website: field("website"),
              locale,
            });
      setMember(member);
      // Back where the visitor came from (only paths of this site)
      router.push(next.startsWith("/") && !next.startsWith("//") ? next : "/");
      router.refresh();
    } catch (err) {
      setError(message(err instanceof AccountError ? err.message : ""));
    } finally {
      setBusy(false);
    }
  };

  const switchTo = (m: Mode) => {
    setMode(m);
    setError(null);
    setSentTo(null);
  };
  const withPassword = mode === "signIn" || mode === "register";

  return (
    <div className="max-w-sm space-y-4">
      {/* A full page visit: the API sends the browser on to Google and back */}
      <a
        href={googleSignInUrl(locale, next)}
        className="flex w-full items-center justify-center gap-2 rounded-lg border border-black/15 bg-white py-2 font-medium text-neutral-800 no-underline! hover:bg-neutral-50 dark:border-white/20"
      >
        <GoogleIcon />
        {t("google")}
      </a>
      <p className="flex items-center gap-3 text-xs opacity-60 before:h-px before:flex-1 before:bg-current after:h-px after:flex-1 after:bg-current">
        {t("or")}
      </p>
      <div className="flex gap-1 rounded-lg bg-black/5 p-1 text-sm dark:bg-white/10">
        {(["signIn", "register"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => switchTo(m)}
            aria-pressed={mode === m || (m === "signIn" && !withPassword)}
            className={`flex-1 rounded-md py-1.5 ${
              mode === m || (m === "signIn" && !withPassword)
                ? "bg-white font-medium shadow-sm dark:bg-neutral-800"
                : "opacity-70"
            }`}
          >
            {t(m === "signIn" ? "signInTab" : "registerTab")}
          </button>
        ))}
      </div>
      {!withPassword && (
        <p className="text-sm">
          {t(mode === "forgot" ? "forgotIntro" : "linkIntro")}
        </p>
      )}
      {sentTo ? (
        <p className="rounded-md bg-green-600/10 p-3 text-sm text-green-900 dark:text-green-200">
          {t(mode === "forgot" ? "resetSent" : "linkSent", { email: sentTo })}
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <label className="block text-sm">
              {t("name")}
              <input
                name="name"
                required
                maxLength={60}
                autoComplete="nickname"
                className={FIELD}
              />
              <span className="mt-0.5 block text-xs opacity-60">
                {t("nameHint")}
              </span>
            </label>
          )}
          <label className="block text-sm">
            {t("email")}
            <input
              name="email"
              type="email"
              required
              maxLength={254}
              autoComplete="email"
              className={FIELD}
            />
          </label>
          {withPassword && (
            <label className="block text-sm">
              {t("password")}
              <input
                name="password"
                type="password"
                required
                minLength={mode === "register" ? 8 : undefined}
                maxLength={200}
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                className={FIELD}
              />
              {mode === "register" && (
                <span className="mt-0.5 block text-xs opacity-60">
                  {t("passwordHint")}
                </span>
              )}
            </label>
          )}
          {/* Honeypot: hidden from people, bots fill it in */}
          <input
            name="website"
            tabIndex={-1}
            autoComplete="off"
            className="hidden"
            aria-hidden
          />
          {error && (
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          )}
          {mode === "register" && (
            <p className="text-xs opacity-60">{t("privacyNote")}</p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-violet-600 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {t(
              {
                signIn: "signInButton",
                register: "registerButton",
                forgot: "sendReset",
                link: "sendLink",
              }[mode],
            )}
          </button>
        </form>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {mode === "signIn" ? (
          <>
            <button
              type="button"
              onClick={() => switchTo("link")}
              className="underline"
            >
              {t("withLink")}
            </button>
            <button
              type="button"
              onClick={() => switchTo("forgot")}
              className="underline opacity-70"
            >
              {t("forgot")}
            </button>
          </>
        ) : (
          !withPassword && (
            <button
              type="button"
              onClick={() => switchTo("signIn")}
              className="underline"
            >
              {t("withPassword")}
            </button>
          )
        )}
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.8c4.3-4 6.9-9.9 6.9-17.2z"
      />
      <path
        fill="#FBBC05"
        d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.8-6.1z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.2-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"
      />
    </svg>
  );
}
