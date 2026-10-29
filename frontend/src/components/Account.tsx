"use client";

import { useTranslations } from "next-intl";
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { fetchMe, type Member, signOut } from "@/lib/account";

type AccountState = {
  /** undefined while loading, null for a guest */
  member: Member | null | undefined;
  setMember: (member: Member | null) => void;
};

const AccountContext = createContext<AccountState>({
  member: null,
  setMember: () => {},
});

/** The signed-in member (or null) for the whole page. */
export const useAccount = () => useContext(AccountContext);

export function AccountProvider({ children }: { children: ReactNode }) {
  const [member, setMember] = useState<Member | null | undefined>(undefined);
  useEffect(() => {
    fetchMe()
      .then(setMember)
      .catch(() => setMember(null));
  }, []);
  return (
    <AccountContext.Provider value={{ member, setMember }}>
      {children}
    </AccountContext.Provider>
  );
}

/** Header: "Sign in" for guests, the member's name with Profile / Sign out for members. */
export function AccountButton() {
  const t = useTranslations("Account");
  const { member, setMember } = useAccount();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [open]);

  if (member === undefined) return <span className="w-16" aria-hidden="true" />;
  if (member === null) {
    return (
      <Link
        href={`/login?next=${encodeURIComponent(pathname)}`}
        rel="nofollow"
        className="shrink-0 rounded-md border border-violet-500/40 px-3 py-1 text-sm text-violet-800 hover:bg-violet-500/10 dark:text-violet-300"
      >
        {t("signIn")}
      </Link>
    );
  }
  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={member.name}
        className="flex items-center gap-1.5 rounded-md border border-black/15 px-2.5 py-1 text-sm dark:border-white/20"
      >
        <span
          aria-hidden="true"
          className="flex h-5 w-5 items-center justify-center rounded-full bg-violet-600 text-xs font-semibold text-white"
        >
          {member.name.charAt(0).toUpperCase()}
        </span>
        <span className="hidden max-w-28 truncate sm:inline">
          {member.name}
        </span>
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-48 rounded-lg border border-black/10 bg-white p-2 shadow-lg dark:border-white/15 dark:bg-neutral-900">
          <Link
            href="/account"
            className="block rounded-md px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10"
          >
            {t("profile")}
          </Link>
          <button
            type="button"
            onClick={async () => {
              await signOut().catch(() => {});
              setMember(null);
              router.refresh();
            }}
            className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-black/5 dark:hover:bg-white/10"
          >
            {t("signOut")}
          </button>
        </div>
      )}
    </div>
  );
}
