"use client";

import { useLocale } from "next-intl";
import { useEffect, useRef } from "react";

/** Cloudflare Turnstile's public site key; without it there is no check (development). */
export const CAPTCHA_SITE_KEY =
  process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

const SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type Turnstile = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string;
  remove: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

let loading: Promise<Turnstile> | null = null;

function loadTurnstile(): Promise<Turnstile> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () =>
      window.turnstile
        ? resolve(window.turnstile)
        : reject(new Error("turnstile"));
    script.onerror = () => {
      loading = null;
      reject(new Error("turnstile"));
    };
    document.head.appendChild(script);
  });
  return loading;
}

/**
 * Turnstile's "are you human?" check: mostly invisible, it asks for a click only when unsure.
 * Gives the token (or "" when it expires); a token works once, so change `resetKey` after
 * each submission for a fresh one.
 */
export default function Captcha({
  onToken,
  resetKey = 0,
}: {
  onToken: (token: string) => void;
  resetKey?: number;
}) {
  const locale = useLocale();
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onToken);
  useEffect(() => {
    callback.current = onToken;
  }, [onToken]);

  useEffect(() => {
    if (!CAPTCHA_SITE_KEY || !box.current) return;
    let id: string | null = null;
    let gone = false;
    callback.current("");
    loadTurnstile()
      .then((turnstile) => {
        if (gone || !box.current) return;
        id = turnstile.render(box.current, {
          sitekey: CAPTCHA_SITE_KEY,
          language: locale,
          appearance: "interaction-only",
          size: "flexible",
          callback: (token: string) => callback.current(token),
          "expired-callback": () => callback.current(""),
          "error-callback": () => callback.current(""),
        });
      })
      .catch(() => callback.current(""));
    return () => {
      gone = true;
      if (id) window.turnstile?.remove(id);
    };
  }, [locale, resetKey]);

  if (!CAPTCHA_SITE_KEY) return null;
  return <div ref={box} />;
}
