"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useAccount } from "@/components/Account";
import { Link } from "@/i18n/navigation";
import { AccountError } from "@/lib/account";
import { localized } from "@/lib/api";
import { forgetQuizzes } from "@/lib/feedback";
import {
  answerCard,
  type CardResult,
  type SpeakerTest,
  startTest,
  type TestableVariety,
  testableVarieties,
} from "@/lib/speaker";

type Stage =
  | "loading"
  | "intro"
  | "question"
  | "done"
  | "tested"
  | "later"
  | "unavailable"
  | "error";

const hours = (seconds: number) => Math.max(1, Math.ceil(seconds / 3600));

/** The speaker test of one language or dialect: rules, the cards one by one, the result. */
export default function SpeakerTestView({ code }: { code: string }) {
  const t = useTranslations("Speaker");
  const tGame = useTranslations("Game");
  const locale = useLocale();
  const { member } = useAccount();
  const [variety, setVariety] = useState<TestableVariety | null>(null);
  const [stage, setStage] = useState<Stage>("loading");
  const [test, setTest] = useState<SpeakerTest | null>(null);
  const [index, setIndex] = useState(0);
  const [last, setLast] = useState<CardResult | null>(null);
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!member) return;
    testableVarieties()
      .then((varieties) => {
        const found = varieties.find((v) => v.code === code) ?? null;
        setVariety(found);
        if (!found) setStage("unavailable");
        else if (found.tested) setStage("tested");
        else if (found.retry_after) {
          setWait(found.retry_after);
          setStage("later");
        } else setStage("intro");
      })
      .catch(() => setStage("error"));
  }, [member, code]);

  if (member === undefined) return <p className="opacity-60">…</p>;
  if (member === null) {
    return (
      <p>
        {t("signInFirst")}{" "}
        <Link
          href={`/login?next=${encodeURIComponent(`/account/test/${code}`)}`}
          rel="nofollow"
        >
          {t("signIn")}
        </Link>
      </p>
    );
  }

  const name = variety
    ? localized(locale, variety.name_en, variety.name_uk, variety.names)
    : code;
  const begin = async () => {
    setBusy(true);
    try {
      const started = await startTest(code, locale);
      if (started.retry_after) {
        setWait(started.retry_after);
        setStage("later");
      } else {
        setTest(started);
        setIndex(0);
        setStage("question");
      }
    } catch (err) {
      const reason = err instanceof AccountError ? err.message : "";
      setStage(
        reason === "already_speaker"
          ? "tested"
          : reason === "not_testable"
            ? "unavailable"
            : "error",
      );
    } finally {
      setBusy(false);
    }
  };

  const answer = async (value: -1 | 0 | 1) => {
    if (!test?.id || busy) return;
    setBusy(true);
    try {
      const result = await answerCard(test.id, test.cards[index].token, value);
      setLast(result);
      if (result.finished) {
        forgetQuizzes(); // the test's answers count as the language's quiz too
        setStage("done");
      } else setIndex(index + 1);
    } catch {
      setStage("error");
    } finally {
      setBusy(false);
    }
  };

  const back = (
    <p className="mt-6">
      <Link href="/account">{t("backToProfile")}</Link>
    </p>
  );

  if (stage === "loading") return <p className="opacity-60">…</p>;
  if (stage === "intro") {
    return (
      <div className="max-w-md space-y-4">
        <p>{t("intro", { variety: name })}</p>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>{t("ruleCards", { cards: 12, pass: 11 })}</li>
          <li>{t("ruleDontKnow")}</li>
          <li>{t("ruleOnce")}</li>
        </ul>
        <button
          type="button"
          onClick={begin}
          disabled={busy}
          className="rounded-lg bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {t("start")}
        </button>
      </div>
    );
  }
  if (stage === "question" && test) {
    const card = test.cards[index];
    return (
      <div className="max-w-md">
        <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-5 text-center">
          <p className="text-xs tracking-wide uppercase opacity-60">{name}</p>
          <p className="my-1 font-serif text-3xl font-semibold text-violet-800 dark:text-violet-300">
            {card.spelling}
          </p>
          <p className="text-sm">
            {card.described
              ? t("describedAs", { meaning: card.meaning })
              : tGame("means", { meaning: card.meaning })}
          </p>
        </div>
        <p className="mt-3 text-center text-sm font-medium">{t("question")}</p>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => answer(-1)}
            disabled={busy}
            className="rounded-lg border border-red-500/40 py-2 text-red-700 hover:bg-red-500/10 dark:text-red-300"
          >
            {tGame("no")}
          </button>
          <button
            type="button"
            onClick={() => answer(0)}
            disabled={busy}
            className="rounded-lg border border-black/15 py-2 text-sm hover:bg-black/5 dark:border-white/20"
          >
            {tGame("dontKnow")}
          </button>
          <button
            type="button"
            onClick={() => answer(1)}
            disabled={busy}
            className="rounded-lg border border-green-600/40 py-2 text-green-800 hover:bg-green-600/10 dark:text-green-300"
          >
            {tGame("yes")}
          </button>
        </div>
        <p className="mt-3 text-center text-xs opacity-60">
          {t("progress", { n: index + 1, total: test.cards.length })}
          {last && (
            <span
              className={
                last.correct
                  ? "text-green-700 dark:text-green-300"
                  : "text-red-700 dark:text-red-300"
              }
            >
              {" · "}
              {last.correct ? t("lastRight") : t("lastWrong")}
            </span>
          )}
        </p>
      </div>
    );
  }
  if (stage === "done" && last && test) {
    return (
      <div className="max-w-md space-y-3">
        <p className="text-lg font-medium">
          {last.passed ? t("passed", { variety: name }) : t("failed")}
        </p>
        <p className="text-sm opacity-80">
          {t("score", { score: last.score, total: test.cards.length })}
        </p>
        {back}
      </div>
    );
  }
  return (
    <div className="max-w-md">
      <p>
        {stage === "tested"
          ? t("alreadyTested", { variety: name })
          : stage === "later"
            ? t("later", { hours: hours(wait) })
            : stage === "unavailable"
              ? t("unavailable")
              : t("error")}
      </p>
      {back}
    </div>
  );
}
