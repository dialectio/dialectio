"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useAccount } from "@/components/Account";
import Captcha from "@/components/Captcha";
import { Link, usePathname } from "@/i18n/navigation";
import { AccountError } from "@/lib/account";
import { localized } from "@/lib/api";
import {
  addComment,
  deleteComment,
  type Discussion as DiscussionData,
  editComment,
  getDiscussion,
  hideComment,
  MAX_COMMENT,
  reportComment,
  restoreComment,
  type WordCard,
  type WordComment,
} from "@/lib/discussion";

type Problem = "error" | "tooMany" | "captcha" | null;

function problemOf(error: unknown): Problem {
  const reason = error instanceof AccountError ? error.message : "";
  if (reason === "captcha") return "captcha";
  return /^429$|too many/i.test(reason) ? "tooMany" : "error";
}

/** The word's card: what the data says about it, kept current (not a comment). */
function Card({ card }: { card: WordCard }) {
  const t = useTranslations("Discussion");
  const locale = useLocale();
  const meaning = localized(locale, card.gloss_en, card.gloss_uk, card.glosses);
  const description = localized(
    locale,
    card.description_en,
    card.description_uk,
    card.descriptions,
  );
  return (
    <div className="space-y-1 rounded bg-black/[.03] p-2 dark:bg-white/[.05]">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-serif text-base font-semibold">{card.spelling}</span>
        {card.ipa && <span className="font-mono opacity-80">{card.ipa}</span>}
        <span className="opacity-60">
          {localized(locale, card.variety_en, card.variety_uk, card.variety_names)}
        </span>
      </div>
      <p>
        <span className="opacity-60">{t("meaning")}:</span> {meaning}
        {description && <span className="opacity-70"> — {description}</span>}
      </p>
      {card.places.length > 0 && (
        <p>
          <span className="opacity-60">{t("whereSaid")}:</span>{" "}
          {card.places
            .map((p) => {
              const region = localized(locale, p.region_en, p.region_uk, p.region_names);
              const name = p.name ? `${p.names[locale] ?? p.name} (${region})` : region;
              return p.count > 1 ? `${name} ×${p.count}` : name;
            })
            .join(", ")}
        </p>
      )}
      <p className="opacity-70">
        {card.source && (
          <>
            {t("source")}:{" "}
            {card.source_url ? (
              <a href={card.source_url} target="_blank" rel="noreferrer" className="underline">
                {card.source}
              </a>
            ) : (
              card.source
            )}
            {card.license && ` (${card.license})`}
          </>
        )}
        {card.contributor && <> · {t("addedBy", { name: card.contributor })}</>}
      </p>
      {(card.unverified || card.votes_yes + card.votes_no > 0) && (
        <p className="opacity-70">
          {card.unverified && <>{t("unverified")} · </>}
          {t("votes", { yes: card.votes_yes, no: card.votes_no })}
          {card.community === "confirmed" && <> · {t("confirmed")}</>}
          {card.community === "disputed" && <> · {t("disputed")}</>}
        </p>
      )}
    </div>
  );
}

function ReportBox({ comment, onDone }: { comment: WordComment; onDone: () => void }) {
  const t = useTranslations("Discussion");
  const [reason, setReason] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  if (state === "sent") return <p className="text-green-700 dark:text-green-400">{t("reported")}</p>;
  return (
    <form
      className="mt-1 flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        setState("sending");
        try {
          await reportComment(comment.id, reason.trim());
          setState("sent");
          setTimeout(onDone, 2500);
        } catch {
          setState("error");
        }
      }}
    >
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={1000}
        placeholder={t("reportReason")}
        aria-label={t("reportReason")}
        className="min-w-0 flex-1 rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
      />
      <button
        type="submit"
        disabled={state === "sending"}
        className="rounded border border-current/30 px-2 py-1 disabled:opacity-50"
      >
        {t("reportSend")}
      </button>
      <button type="button" onClick={onDone} className="opacity-60 hover:underline">
        {t("cancel")}
      </button>
      {state === "error" && <span className="text-red-600">{t("error")}</span>}
    </form>
  );
}

function CommentItem({
  comment,
  canModerate,
  signedIn,
  onReply,
  onChange,
  onRemoved,
}: {
  comment: WordComment;
  canModerate: boolean;
  signedIn: boolean;
  onReply: (comment: WordComment) => void;
  onChange: (data: DiscussionData) => void;
  onRemoved: (id: number) => void;
}) {
  const t = useTranslations("Discussion");
  const locale = useLocale();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(comment.body);
  const [reporting, setReporting] = useState(false);
  const [error, setError] = useState(false);

  const run = async (action: () => Promise<DiscussionData | null>, removed = false) => {
    setError(false);
    try {
      const data = await action();
      if (removed) onRemoved(comment.id);
      else if (data) onChange(data);
      setEditing(false);
    } catch {
      setError(true);
    }
  };

  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
    new Date(comment.created_at),
  );
  const action = "opacity-60 hover:underline hover:opacity-100";

  return (
    <li
      id={`comment-${comment.id}`}
      className={`border-t border-black/5 py-2 dark:border-white/10 ${comment.hidden ? "opacity-50" : ""}`}
    >
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-semibold">{comment.author}</span>
        {comment.badge && (
          <span className="rounded bg-violet-500/15 px-1.5 text-[11px] text-violet-800 dark:text-violet-300">
            {t(`badge.${comment.badge}`)}
          </span>
        )}
        <span className="opacity-50">
          {date}
          {comment.edited_at && ` · ${t("edited")}`}
        </span>
        {comment.hidden && (
          <span className="text-red-700 dark:text-red-400">
            {t("hiddenNote", { count: comment.reports })}
          </span>
        )}
        {!comment.hidden && canModerate && comment.reports > 0 && (
          <span className="text-amber-700 dark:text-amber-400">
            {t("reports", { count: comment.reports })}
          </span>
        )}
      </div>
      {comment.reply_to && (
        <a
          href={`#comment-${comment.reply_to.id}`}
          className="mt-0.5 block border-l-2 border-black/15 pl-2 opacity-60 no-underline! dark:border-white/20"
        >
          {comment.reply_to.author}: {comment.reply_to.text}
        </a>
      )}
      {editing ? (
        <div className="mt-1 space-y-1">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={MAX_COMMENT}
            rows={3}
            aria-label={t("edit")}
            className="w-full rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          />
          <div className="flex gap-3">
            <button
              type="button"
              disabled={!draft.trim()}
              onClick={() => run(() => editComment(comment.id, draft.trim()))}
              className="rounded bg-blue-600 px-2 py-0.5 text-white disabled:opacity-50"
            >
              {t("save")}
            </button>
            <button type="button" onClick={() => setEditing(false)} className={action}>
              {t("cancel")}
            </button>
          </div>
        </div>
      ) : (
        <p className="mt-0.5 whitespace-pre-wrap break-words">{comment.body}</p>
      )}
      {!editing && (
        <div className="mt-0.5 flex flex-wrap gap-x-3">
          {signedIn && !comment.hidden && (
            <button type="button" onClick={() => onReply(comment)} className={action}>
              {t("reply")}
            </button>
          )}
          {comment.mine && (
            <>
              <button
                type="button"
                onClick={() => {
                  setDraft(comment.body);
                  setEditing(true);
                }}
                className={action}
              >
                {t("edit")}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(t("confirmDelete")))
                    run(() => deleteComment(comment.id), true);
                }}
                className={action}
              >
                {t("delete")}
              </button>
            </>
          )}
          {!comment.mine && !comment.hidden && !reporting && (
            <button type="button" onClick={() => setReporting(true)} className={action}>
              {t("report")}
            </button>
          )}
          {canModerate &&
            (comment.hidden ? (
              <button type="button" onClick={() => run(() => restoreComment(comment.id))} className={action}>
                {t("restore")}
              </button>
            ) : (
              <button type="button" onClick={() => run(() => hideComment(comment.id))} className={action}>
                {t("hide")}
              </button>
            ))}
          {error && <span className="text-red-600">{t("error")}</span>}
        </div>
      )}
      {reporting && <ReportBox comment={comment} onDone={() => setReporting(false)} />}
    </li>
  );
}

/**
 * The discussion of a word (one form): its card, members' comments in any language, and a box
 * to write one. Guests read and report; members write, answer, edit and delete their own.
 */
export default function Discussion({
  formId,
  onCount,
}: {
  formId: number;
  /** The number of visible comments, after loading or a change */
  onCount: (count: number) => void;
}) {
  const t = useTranslations("Discussion");
  const { member } = useAccount();
  const pathname = usePathname();
  const [data, setData] = useState<DiscussionData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<WordComment | null>(null);
  const [captcha, setCaptcha] = useState(""); // Turnstile token, works once
  const [captchaRound, setCaptchaRound] = useState(0);
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<Problem>(null);

  const show = (next: DiscussionData) => {
    setData(next);
    onCount(next.comments.filter((c) => !c.hidden).length);
  };

  useEffect(() => {
    let cancelled = false;
    getDiscussion(formId)
      .then((result) => !cancelled && show(result))
      .catch(() => !cancelled && setLoadError(true));
    return () => {
      cancelled = true;
    };
    // `member`: signing in shows the member's own comments and moderation
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formId, member?.id]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    setProblem(null);
    try {
      show(await addComment(formId, body.trim(), replyTo?.id ?? null, captcha));
      setBody("");
      setReplyTo(null);
    } catch (error) {
      setProblem(problemOf(error));
    } finally {
      setSending(false);
      setCaptcha("");
      setCaptchaRound((n) => n + 1);
    }
  };

  if (loadError) return <p className="mt-2 text-xs text-red-600">{t("error")}</p>;
  if (!data) return <p className="mt-2 text-xs opacity-60">{t("loading")}</p>;

  return (
    <section aria-label={t("title")} className="mt-2 space-y-2 text-xs">
      <Card card={data.card} />
      {data.comments.length === 0 ? (
        <p className="opacity-60">{t("noComments")}</p>
      ) : (
        <ul>
          {data.comments.map((comment) => (
            <CommentItem
              key={`${comment.id}-${comment.edited_at ?? ""}-${comment.hidden}`}
              comment={comment}
              canModerate={data.can_moderate}
              signedIn={Boolean(member)}
              onReply={setReplyTo}
              onChange={show}
              onRemoved={(id) =>
                show({ ...data, comments: data.comments.filter((c) => c.id !== id) })
              }
            />
          ))}
        </ul>
      )}
      {member ? (
        <form onSubmit={send} className="space-y-1.5">
          {replyTo && (
            <div className="flex items-baseline gap-2 opacity-70">
              <span>{t("replyingTo", { name: replyTo.author })}</span>
              <button type="button" onClick={() => setReplyTo(null)} className="hover:underline">
                ✕
              </button>
            </div>
          )}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={MAX_COMMENT}
            rows={3}
            placeholder={t("placeholder")}
            aria-label={t("placeholder")}
            className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 text-sm dark:border-white/20"
          />
          {body.trim() && <Captcha onToken={setCaptcha} resetKey={captchaRound} />}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={sending || !body.trim()}
              className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50"
            >
              {sending ? t("sending") : t("send")}
            </button>
            {problem && <span className="text-red-600">{t(problem)}</span>}
          </div>
          <p className="opacity-60">{t("rules")}</p>
        </form>
      ) : member === null ? (
        <p>
          <Link
            href={`/login?next=${encodeURIComponent(pathname)}`}
            rel="nofollow"
            className="underline"
          >
            {t("signIn")}
          </Link>
        </p>
      ) : null}
    </section>
  );
}
