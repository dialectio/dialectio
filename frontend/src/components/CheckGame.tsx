"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { UKRAINE_BOUNDS, useMapView } from "@/components/MapShell";
import { RegionQuestion } from "@/components/WordCheck";
import { capitalize, localized, SITE_URL } from "@/lib/api";
import { resultCard, shareOrDownload } from "@/lib/snapshot";
import {
  addChecked,
  type Card,
  checkedCount,
  type Deck,
  loadCards,
  myRegion,
  saveDeck,
  savedDeck,
  sendVote,
} from "@/lib/feedback";

const UKRAINIAN_DECK = "ukr";
// Fetch more cards when fewer than this many are left.
const REFILL_AT = 3;
const NO_CODES: string[] = [];
// Offer to share the result after this many checked words
const SHARE_AFTER = 5;

/** What the word should mean, in the reader's language. */
function meaning(card: Card, locale: string): string {
  if (locale !== "uk")
    return localized(locale, card.english ?? card.gloss_en, null, card.glosses);
  return card.standard ?? card.gloss_uk ?? card.gloss_en;
}

/**
 * "Check words": one unverified word at a time, answered Yes / No / Don't know (also with
 * the arrow keys). Each answer is a vote; the map shows where the word is supposed to be said.
 */
export default function CheckGame({ decks }: { decks: Deck[] }) {
  const locale = useLocale();
  const t = useTranslations("Game");
  const [deck, setDeck] = useState(UKRAINIAN_DECK);
  const [cards, setCards] = useState<Card[]>([]);
  const [status, setStatus] = useState<"loading" | "loaded" | "error">(
    "loading",
  );
  const [checked, setChecked] = useState(0);
  const [askRegion, setAskRegion] = useState(false);
  // Words checked in this deck during this visit (for the shareable result)
  const [sessionChecked, setSessionChecked] = useState(0);
  const [sharing, setSharing] = useState(false);
  // Answered cards (votes and "don't know"): not shown again during this visit, even if
  // the vote has not reached the server yet.
  const answered = useRef<number[]>([]);
  // The deck being loaded, if any; an answer for another deck (switched meanwhile) is dropped.
  const loading = useRef<string | null>(null);

  useEffect(() => {
    // localStorage is only available in the browser, after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setChecked(checkedCount());
    // A link like /check?deck=ukr-hutsul (from a dialect page) wins over the remembered deck.
    const wanted =
      new URLSearchParams(window.location.search).get("deck") ?? savedDeck();
    if (wanted && decks.some((d) => d.code === wanted)) setDeck(wanted);
  }, [decks]);

  const refill = useCallback(
    async (current: Card[], reset = false) => {
      if (loading.current === deck) return;
      loading.current = deck;
      try {
        const shown = current.map((c) => c.form_id);
        const more = await loadCards(deck, [...answered.current, ...shown]);
        if (loading.current !== deck) return;
        setCards((previous) => {
          const base = reset ? [] : previous;
          const known = new Set([
            ...base.map((c) => c.form_id),
            ...answered.current,
          ]);
          return [...base, ...more.filter((c) => !known.has(c.form_id))];
        });
        setStatus("loaded");
      } catch {
        if (loading.current === deck) setStatus("error");
      } finally {
        if (loading.current === deck) loading.current = null;
      }
    },
    [deck],
  );

  useEffect(() => {
    refill([], true);
  }, [refill]);

  const card = cards[0] ?? null;

  useMapView({
    highlightCodes: card?.region_codes ?? NO_CODES,
    labels: null,
    selectedCode: null,
    onSelectRegion: () => {},
    bounds: deck.startsWith(UKRAINIAN_DECK) ? UKRAINE_BOUNDS : null,
    panelFirstOnPhone: true,
  });

  const answer = useCallback(
    (value: number) => {
      if (!card) return;
      const rest = cards.slice(1);
      setCards(rest);
      answered.current.push(card.form_id);
      if (value !== 0) {
        sendVote(card.form_id, value).catch(() => {});
        addChecked();
        setChecked((n) => n + 1);
        setSessionChecked((n) => n + 1);
        if (myRegion() === null) setAskRegion(true);
      }
      if (rest.length < REFILL_AT) refill(rest);
    },
    [card, cards, refill],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLElement &&
        e.target.closest("select, input, textarea")
      )
        return;
      const keys: Record<string, number> = {
        ArrowRight: 1,
        ArrowLeft: -1,
        ArrowDown: 0,
      };
      if (e.key in keys) {
        e.preventDefault();
        answer(keys[e.key]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer]);

  const chooseDeck = (code: string) => {
    saveDeck(code);
    answered.current = [];
    setSessionChecked(0);
    setCards([]);
    setStatus("loading");
    setDeck(code);
  };

  const deckName = (d: Deck) =>
    d.code === UKRAINIAN_DECK
      ? t("ukrainianDeck")
      : capitalize(localized(locale, d.name_en, d.name_uk, d.names));
  const currentDeck = decks.find((d) => d.code === deck);

  const share = async () => {
    if (!currentDeck) return;
    setSharing(true);
    try {
      const title = t("shareTitle", {
        count: sessionChecked,
        deck: deckName(currentDeck),
      });
      const footer = `${new URL(SITE_URL).host}/${locale}/check?deck=${deck}`;
      const blob = await resultCard({
        kicker: t("shareKicker"),
        title,
        footer,
      });
      if (blob)
        await shareOrDownload(
          blob,
          `dialectio-${deck}.png`,
          `${title} ${SITE_URL}/${locale}/check?deck=${deck}`,
        );
    } finally {
      setSharing(false);
    }
  };

  const varietyName = card
    ? capitalize(
        localized(
          locale,
          card.variety_name_en,
          card.variety_name_uk,
          card.variety_names,
        ),
      )
    : "";

  return (
    <article className="space-y-5 p-4">
      <header>
        <h1 className="font-serif text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm opacity-80">{t("intro")}</p>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="check-deck" className="opacity-70">
          {t("deck")}
        </label>
        <select
          id="check-deck"
          value={deck}
          onChange={(e) => chooseDeck(e.target.value)}
          className="rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
        >
          {decks
            .filter((d) => d.code === UKRAINIAN_DECK)
            .map((d) => (
              <option key={d.code} value={d.code}>
                {deckName(d)} ({d.words})
              </option>
            ))}
          {(["dialect", "language"] as const).map((kind) => (
            <optgroup
              key={kind}
              label={
                kind === "dialect" ? t("dialectDecks") : t("languageDecks")
              }
            >
              {decks
                .filter((d) => d.kind === kind && d.code !== UKRAINIAN_DECK)
                .map((d) => (
                  <option key={d.code} value={d.code}>
                    {deckName(d)} ({d.words})
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </div>

      {askRegion && (
        <div className="rounded-md bg-black/5 p-2 dark:bg-white/10">
          <RegionQuestion onDone={() => setAskRegion(false)} />
        </div>
      )}

      {!card && status === "loading" && (
        <p className="text-sm opacity-60">{t("loading")}</p>
      )}
      {status === "error" && (
        <p className="text-sm text-red-600">{t("error")}</p>
      )}
      {!card && status === "loaded" && <p className="text-sm">{t("empty")}</p>}

      {card && (
        <section
          key={card.form_id}
          className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-5 text-center"
        >
          <p className="text-xs tracking-wide uppercase opacity-60">
            {varietyName}
          </p>
          <p className="my-2 font-serif text-4xl font-semibold text-violet-800 dark:text-violet-300">
            {card.spelling}
          </p>
          <p className="text-sm">
            {locale === "uk" && card.variety_code === "ukr"
              ? // Standard Ukrainian: the Ukrainian meaning would just repeat the word.
                t("inEnglish", { word: card.english ?? card.gloss_en })
              : t("means", { meaning: meaning(card, locale) })}
          </p>
          <p className="mt-4 font-medium">
            {card.kind === "dialect"
              ? t("questionDialect")
              : t("questionLanguage")}
          </p>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => answer(-1)}
              className="rounded-lg border border-red-600/40 py-2 font-medium text-red-800 hover:bg-red-600/10 dark:text-red-300"
            >
              ← {t("no")}
            </button>
            <button
              type="button"
              onClick={() => answer(0)}
              className="rounded-lg border border-black/15 py-2 text-sm opacity-80 hover:bg-black/5 dark:border-white/20"
            >
              {t("dontKnow")} ↓
            </button>
            <button
              type="button"
              onClick={() => answer(1)}
              className="rounded-lg border border-green-600/40 py-2 font-medium text-green-800 hover:bg-green-600/10 dark:text-green-300"
            >
              {t("yes")} →
            </button>
          </div>
          <a
            href={`/${locale}/word/${card.slug}`}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-xs underline opacity-60"
          >
            {t("wordPage")}
          </a>
        </section>
      )}

      {checked > 0 && (
        <p className="text-sm opacity-80">{t("checked", { count: checked })}</p>
      )}
      {sessionChecked >= SHARE_AFTER && (
        <button
          type="button"
          onClick={share}
          disabled={sharing}
          className="rounded-md border border-violet-500/40 px-3 py-1.5 text-sm text-violet-800 hover:bg-violet-500/10 disabled:opacity-50 dark:text-violet-300"
        >
          📣 {t("share")}
        </button>
      )}
      <p className="text-xs opacity-60">{t("howItWorks")}</p>
    </article>
  );
}
