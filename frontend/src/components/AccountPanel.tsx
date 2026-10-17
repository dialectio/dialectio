"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { useAccount } from "@/components/Account";
import { Link, useRouter } from "@/i18n/navigation";
import { deleteAccount, signOut } from "@/lib/account";

/** The member's profile: name and email, signing out, deleting the account. */
export default function AccountPanel() {
  const t = useTranslations("Account");
  const { member, setMember } = useAccount();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);

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

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="opacity-60">{t("name")}</dt>
        <dd className="font-medium">{member.name}</dd>
        <dt className="opacity-60">{t("email")}</dt>
        <dd>{member.email}</dd>
      </dl>
      <p className="text-sm opacity-80">{t("levelsSoon")}</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => leave(false)}
          className="rounded-md border border-black/15 px-3 py-1.5 text-sm dark:border-white/20"
        >
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
