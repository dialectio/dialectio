"use client";

import { useLocale, useTranslations } from "next-intl";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { capitalize, localized } from "@/lib/api";
import {
  answerGold,
  type Card,
  cardMeaning,
  getQuiz,
  getQuizStatus,
  quizPassed,
  rememberQuiz,
} from "@/lib/feedback";

/** Resolves true when this browser's votes on the language count (quiz passed). */
type Gate = (language: string) => Promise<boolean>;

const QuizContext = createContext<Gate>(async () => true);

/** Before a guest's first vote on a language: `await gate(language)` shows the quiz if needed. */
export const useQuizGate = () => useContext(QuizContext);

/** Provides the quiz gate and shows the quiz dialog when a vote needs it. */
export function QuizProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<{
    language: string;
    resolve: (passed: boolean) => void;
  } | null>(null);

  const gate = useCallback<Gate>(async (language) => {
    if (quizPassed(language)) return true;
    try {
      const state = await getQuizStatus(language);
      if (state.passed) {
        rememberQuiz(language, true);
        return true;
      }
    } catch {
      return true; // the API is unreachable: the vote will fail on its own
    }
    return new Promise<boolean>((resolve) => setPending({ language, resolve }));
  }, []);

  return (
    <QuizContext.Provider value={gate}>
      {children}
      {pending && (
        <QuizDialog
          language={pending.language}
          onDone={(passed) => {
            pending.resolve(passed);
            setPending(null);
          }}
        />
      )}
    </QuizContext.Provider>
  );
}

type Stage = "loading" | "question" | "passed" | "failed" | "later";

/** Three control cards, one at a time; the server decides whether the quiz is passed. */
function QuizDialog({
  language,
  onDone,
}: {
  language: string;
  onDone: (passed: boolean) => void;
}) {
  const t = useTranslations("Quiz");
  const tGame = useTranslations("Game");
  const locale = useLocale();
  const [cards, setCards] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [stage, setStage] = useState<Stage>("loading");

  useEffect(() => {
    getQuiz(language)
      .then((quiz) => {
        if (quiz.retry_after) return setStage("later");
        if (quiz.cards.length === 0) return setStage("failed");
        setCards(quiz.cards);
        setStage("question");
      })
      .catch(() => setStage("failed"));
  }, [language]);

  const answer = async (value: number) => {
    const card = cards[index];
    let passed = false;
    try {
      passed = (await answerGold(card, value)).passed;
    } catch {
      // a lost answer counts as not answered
    }
    if (index + 1 < cards.length) setIndex(index + 1);
    else setStage(passed ? "passed" : "failed");
  };

  const card = cards[index];
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="quiz-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl dark:bg-neutral-900">
        <h2 id="quiz-title" className="font-serif text-lg font-semibold">
          {t("title")}
        </h2>
        {stage === "loading" && <p className="mt-3 text-sm opacity-70">…</p>}
        {stage === "question" && card && (
          <>
            <p className="mt-1 text-sm opacity-80">{t("intro")}</p>
            <div className="mt-4 rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 text-center">
              <p className="text-xs tracking-wide uppercase opacity-60">
                {capitalize(
                  localized(
                    locale,
                    card.variety_name_en,
                    card.variety_name_uk,
                    card.variety_names,
                  ),
                )}
              </p>
              <p className="my-1 font-serif text-3xl font-semibold text-violet-800 dark:text-violet-300">
                {card.spelling}
              </p>
              <p className="text-sm">
                {tGame("means", { meaning: cardMeaning(card, locale) })}
              </p>
            </div>
            <p className="mt-3 text-center text-sm font-medium">
              {t("question")}
            </p>
            <div className="mt-2 grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => answer(-1)}
                className="rounded-lg border border-red-500/40 py-2 text-red-700 hover:bg-red-500/10 dark:text-red-300"
              >
                {tGame("no")}
              </button>
              <button
                type="button"
                onClick={() => answer(0)}
                className="rounded-lg border border-black/15 py-2 text-sm hover:bg-black/5 dark:border-white/20"
              >
                {tGame("dontKnow")}
              </button>
              <button
                type="button"
                onClick={() => answer(1)}
                className="rounded-lg border border-green-600/40 py-2 text-green-800 hover:bg-green-600/10 dark:text-green-300"
              >
                {tGame("yes")}
              </button>
            </div>
            <p className="mt-3 text-center text-xs opacity-60">
              {t("progress", { n: index + 1, total: cards.length })}
            </p>
          </>
        )}
        {stage !== "loading" && stage !== "question" && (
          <>
            <p className="mt-3 text-sm">{t(stage)}</p>
            <button
              type="button"
              onClick={() => onDone(stage === "passed")}
              className="mt-4 w-full rounded-lg bg-violet-600 py-2 text-sm font-medium text-white hover:bg-violet-700"
            >
              {stage === "passed" ? t("continue") : t("close")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
