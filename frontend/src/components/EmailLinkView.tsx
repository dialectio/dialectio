"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { useAccount } from "@/components/Account";
import { Link, useRouter } from "@/i18n/navigation";
import {
  AccountError,
  resetPassword,
  signInWithLink,
  takeNext,
  verifyEmail,
} from "@/lib/account";

export type LinkPurpose = "verify" | "reset" | "login";

/** Where a link from an email lands: one button (or the new password) uses it up. A button
 * rather than doing it on page load, so mail scanners that open links don't spend them. */
export default function EmailLinkView({
  purpose,
  token,
}: {
  purpose: LinkPurpose;
  token: string;
}) {
  const t = useTranslations("EmailLink");
  const { setMember } = useAccount();
  const router = useRouter();
  const [state, setState] = useState<
    "ready" | "busy" | "done" | "invalid" | "short"
  >(token ? "ready" : "invalid");

  const use = async (e?: FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    const password = e
      ? String(new FormData(e.currentTarget).get("password") ?? "")
      : "";
    setState("busy");
    try {
      const member =
        purpose === "verify"
          ? await verifyEmail(token)
          : purpose === "login"
            ? await signInWithLink(token)
            : await resetPassword(token, password);
      setMember(member);
      if (purpose === "login") {
        router.push(takeNext());
        router.refresh();
      } else setState("done");
    } catch (err) {
      const reason = err instanceof AccountError ? err.message : "";
      setState(reason === "short_password" ? "short" : "invalid");
    }
  };

  if (state === "invalid") {
    return (
      <div className="space-y-3">
        <p>{t("invalid")}</p>
        <p>
          <Link href="/login">{t("toSignIn")}</Link>
        </p>
      </div>
    );
  }
  if (state === "done") {
    return (
      <div className="space-y-3">
        <p>{t(purpose === "verify" ? "verified" : "passwordSet")}</p>
        <p>
          <Link href="/account">{t("toProfile")}</Link>
        </p>
      </div>
    );
  }
  if (purpose === "reset") {
    return (
      <form onSubmit={use} className="max-w-sm space-y-3">
        <label className="block text-sm">
          {t("newPassword")}
          <input
            name="password"
            type="password"
            required
            minLength={8}
            maxLength={200}
            autoComplete="new-password"
            className="w-full rounded-md border border-black/15 bg-transparent px-3 py-2 dark:border-white/20"
          />
          <span className="mt-0.5 block text-xs opacity-60">
            {t("passwordHint")}
          </span>
        </label>
        {state === "short" && (
          <p className="text-sm text-red-700 dark:text-red-300">
            {t("passwordHint")}
          </p>
        )}
        <button
          type="submit"
          disabled={state === "busy"}
          className="w-full rounded-lg bg-violet-600 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {t("savePassword")}
        </button>
      </form>
    );
  }
  return (
    <button
      type="button"
      onClick={() => use()}
      disabled={state === "busy"}
      className="rounded-lg bg-violet-600 px-5 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
    >
      {t(purpose === "verify" ? "confirm" : "signIn")}
    </button>
  );
}
