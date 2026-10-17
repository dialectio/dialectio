"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { useAccount } from "@/components/Account";
import { useRouter } from "@/i18n/navigation";
import { AccountError, register, signIn } from "@/lib/account";

const FIELD =
  "w-full rounded-md border border-black/15 bg-transparent px-3 py-2 dark:border-white/20";

/** Sign in, or create an account (email, password, the name shown under contributions). */
export default function AuthForm({ next }: { next: string }) {
  const t = useTranslations("Account");
  const router = useRouter();
  const { setMember } = useAccount();
  const [mode, setMode] = useState<"signIn" | "register">("signIn");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "");
    setBusy(true);
    setError(null);
    try {
      const member =
        mode === "signIn"
          ? await signIn(field("email"), field("password"))
          : await register({
              email: field("email"),
              password: field("password"),
              name: field("name"),
              website: field("website"),
            });
      setMember(member);
      // Back where the visitor came from (only paths of this site)
      router.push(next.startsWith("/") && !next.startsWith("//") ? next : "/");
      router.refresh();
    } catch (err) {
      const code = err instanceof AccountError ? err.message : "";
      setError(
        t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.other"),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-sm space-y-4">
      <div className="flex gap-1 rounded-lg bg-black/5 p-1 text-sm dark:bg-white/10">
        {(["signIn", "register"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              setError(null);
            }}
            aria-pressed={mode === m}
            className={`flex-1 rounded-md py-1.5 ${
              mode === m
                ? "bg-white font-medium shadow-sm dark:bg-neutral-800"
                : "opacity-70"
            }`}
          >
            {t(m === "signIn" ? "signInTab" : "registerTab")}
          </button>
        ))}
      </div>
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
          {t(mode === "signIn" ? "signInButton" : "registerButton")}
        </button>
      </form>
      <p className="text-xs opacity-60">{t("soon")}</p>
    </div>
  );
}
