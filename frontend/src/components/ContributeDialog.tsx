"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useAccount } from "@/components/Account";
import Captcha, { CAPTCHA_SITE_KEY } from "@/components/Captcha";
import { Link, usePathname } from "@/i18n/navigation";
import PlacePicker, { regionCodesOf, type Where } from "@/components/PlacePicker";
import { API_URL, localized } from "@/lib/api";
import { VarietySelect } from "@/components/VarietySelect";
import { settlementArea, settlementName, varietiesOf } from "@/lib/settlements";
import { listPublicVarieties, sortVarieties, type Variety } from "@/lib/varieties";

const MAX_RECORDING_MS = 10_000;
// Browsers record in different containers: Chrome/Firefox WebM/Ogg, Safari MP4.
const RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];

type Status = "idle" | "sending" | "sent" | "error" | "tooMany" | "signedOut";

function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  const start = async () => {
    setError(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = RECORDING_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        setBlob(new Blob(chunks, { type: recorder.mimeType.split(";")[0] }));
        setRecording(false);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      timerRef.current = setTimeout(stop, MAX_RECORDING_MS);
    } catch {
      setError(true); // no microphone or permission denied
    }
  };

  useEffect(() => stop, []);

  return { recording, blob, error, start, stop, clear: () => setBlob(null) };
}

const LAST_VARIETY_KEY = "dialectio.contributeVariety";

function lastVariety(): string | null {
  try {
    return localStorage.getItem(LAST_VARIETY_KEY);
  } catch {
    return null;
  }
}

function rememberVariety(code: string) {
  try {
    localStorage.setItem(LAST_VARIETY_KEY, code);
  } catch {
    // storage unavailable: the choice just isn't remembered
  }
}

export default function ContributeDialog({
  conceptId,
  conceptName,
  regionCode,
  onClose,
}: {
  conceptId: number;
  conceptName: string;
  /** Oblast selected on the map, if any: "where do they say it?" starts there */
  regionCode: string | null;
  onClose: () => void;
}) {
  const t = useTranslations("Contribute");
  const locale = useLocale();
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [where, setWhere] = useState<Where | null>(null);
  // The language or dialect the visitor picked; null = the place's suggestion
  const [chosen, setChosen] = useState<string | null>(null);
  const [anyVariety, setAnyVariety] = useState(false); // the full list instead of the place's
  const [spelling, setSpelling] = useState("");
  const [place, setPlace] = useState("");
  const { member } = useAccount();
  const [captcha, setCaptcha] = useState(""); // Turnstile token, works once
  const [captchaRound, setCaptchaRound] = useState(0);
  const pathname = usePathname();
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot, hidden from people
  const [status, setStatus] = useState<Status>("idle");
  const recorder = useRecorder();
  const audioSrc = useMemo(
    () => (recorder.blob ? URL.createObjectURL(recorder.blob) : null),
    [recorder.blob],
  );
  useEffect(() => () => void (audioSrc && URL.revokeObjectURL(audioSrc)), [audioSrc]);

  useEffect(() => {
    listPublicVarieties()
      .then((result) => setVarieties(sortVarieties(result, locale)))
      .catch(() => setVarieties([]));
  }, [locale]);

  // The languages and dialects of the place, most specific first
  const candidates = useMemo(() => varietiesOf(varieties, regionCodesOf(where)), [varieties, where]);
  const dialects = candidates.filter((v) => v.kind === "dialect");
  // Suggested for the place: the last choice if it is spoken there, the oblast's only dialect,
  // nothing when it has several (the visitor picks one, or "don't know"), else its language
  const suggested = (() => {
    const last = lastVariety();
    if (candidates.some((v) => v.code === last)) return last;
    if (dialects.length === 1) return dialects[0].code;
    if (dialects.length > 1) return null;
    return candidates[0]?.code ?? null;
  })();
  const fullList = anyVariety || candidates.length === 0;
  const variety = chosen ?? (fullList ? (lastVariety() ?? "ukr") : suggested);
  /** The language of the place's dialects: picking it means "I don't know my dialect" */
  const dialectLanguage = (v: Variety) =>
    v.kind === "language" && dialects.some((d) => d.code.split("-")[0] === v.code);
  const varietyName = (v: Variety) => localized(locale, v.name_en, v.name_uk, v.names);

  const changeWhere = (next: Where | null) => {
    setWhere(next);
    setChosen(null);
    setAnyVariety(false);
  };
  const pick = (code: string) => {
    setChosen(code);
    rememberVariety(code);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!spelling.trim() || !consent || !where || !variety) return;
    setStatus("sending");
    const data = new FormData();
    data.append("concept_id", String(conceptId));
    data.append("variety", variety);
    data.append("spelling", spelling.trim());
    if (where.kind === "settlement") {
      const s = where.settlement;
      data.append("settlement_id", String(s.id));
      // What editors see, in Ukrainian where GeoNames has it
      data.append("place", `${settlementName(s, "uk")}, ${settlementArea(s, "uk")}`);
    } else {
      const region = localized("uk", where.region.name_en, where.region.name_uk);
      data.append("region", where.region.code);
      data.append("place", [place.trim(), region].filter(Boolean).join(", "));
    }
    data.append("consent", "true");
    data.append("website", website);
    data.append("captcha", captcha);
    if (recorder.blob) {
      const extension = recorder.blob.type.includes("mp4") ? "m4a" : recorder.blob.type.split("/")[1];
      data.append("audio", recorder.blob, `recording.${extension}`);
    }
    try {
      // With the member's session: the word carries their name
      const response = await fetch(`${API_URL}/api/contributions`, {
        method: "POST",
        body: data,
        credentials: "include",
      });
      const failure = response.status === 401 ? "signedOut" : response.status === 429 ? "tooMany" : "error";
      setStatus(response.ok ? "sent" : failure);
      if (!response.ok) setCaptchaRound((n) => n + 1);
    } catch {
      setStatus("error");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contribute-title"
        className="max-h-full w-full max-w-md overflow-y-auto rounded-lg bg-[var(--background)] p-5 shadow-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-4">
          <h2 id="contribute-title" className="text-lg font-semibold">
            {t("title", { word: conceptName })}
          </h2>
          <button type="button" onClick={onClose} aria-label={t("close")} className="opacity-60">
            ✕
          </button>
        </div>

        {member === undefined ? (
          <p className="text-sm opacity-60">…</p>
        ) : member === null || status === "signedOut" ? (
          <div className="space-y-3 text-sm">
            <p>{t("signInFirst")}</p>
            <Link
              href={`/login?next=${encodeURIComponent(pathname)}`}
              rel="nofollow"
              className="inline-block rounded bg-blue-600 px-3 py-1.5 text-white no-underline!"
            >
              {t("signIn")}
            </Link>
          </div>
        ) : status === "sent" ? (
          <div className="space-y-4">
            <p>{t("thanks")}</p>
            <button type="button" onClick={onClose} className="rounded bg-blue-600 px-3 py-1.5 text-white">
              {t("close")}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3 text-sm">
            <fieldset>
              <legend className="mb-1 font-medium">{t("where")}</legend>
              <PlacePicker regionCode={regionCode} value={where} onChange={changeWhere} />
              {where?.kind === "region" && (
                <input
                  maxLength={120}
                  value={place}
                  onChange={(e) => setPlace(e.target.value)}
                  placeholder={t("placeHint")}
                  aria-label={t("place")}
                  className="mt-2 w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
                />
              )}
            </fieldset>
            {where && (
              <fieldset>
                <legend className="mb-1 opacity-70">{t("variety")}</legend>
                {fullList ? (
                  <VarietySelect varieties={varieties} value={variety ?? ""} onChange={pick} />
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {candidates.map((v) => (
                      <button
                        key={v.code}
                        type="button"
                        aria-pressed={variety === v.code}
                        onClick={() => pick(v.code)}
                        className={`rounded-full border px-2.5 py-1 ${
                          variety === v.code
                            ? "border-blue-600 bg-blue-600 text-white"
                            : "border-current/30"
                        }`}
                      >
                        {dialectLanguage(v)
                          ? t("dontKnowDialect", { language: varietyName(v) })
                          : varietyName(v)}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setAnyVariety(true)}
                      className="px-1 text-xs opacity-60 hover:underline"
                    >
                      {t("otherVariety")}
                    </button>
                  </div>
                )}
                {!fullList && dialects.length > 1 && !variety && (
                  <p className="mt-1 text-xs opacity-70">{t("severalDialects")}</p>
                )}
                {!fullList && !chosen && dialects.length === 1 && variety === dialects[0].code && (
                  <p className="mt-1 text-xs opacity-60">{t("varietyFromPlace")}</p>
                )}
              </fieldset>
            )}
            <label className="block">
              <span className="mb-1 block opacity-70">{t("word")}</span>
              <input
                required
                maxLength={200}
                value={spelling}
                onChange={(e) => setSpelling(e.target.value)}
                className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 text-base dark:border-white/20"
              />
            </label>
            <p className="text-xs opacity-70">{t("signedAs", { name: member.name })}</p>
            {/* Honeypot: invisible to people, bots fill it in. */}
            <input
              type="text"
              name="website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="absolute -left-[9999px] h-0 w-0 opacity-0"
            />

            <div>
              <span className="mb-1 block opacity-70">{t("recording")}</span>
              <div className="flex flex-wrap items-center gap-2">
                {recorder.recording ? (
                  <button
                    type="button"
                    onClick={recorder.stop}
                    className="rounded bg-red-600 px-3 py-1.5 text-white"
                  >
                    ■ {t("stop")}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={recorder.start}
                    className="rounded border border-current/30 px-3 py-1.5"
                  >
                    ● {recorder.blob ? t("recordAgain") : t("record")}
                  </button>
                )}
                {audioSrc && !recorder.recording && (
                  <>
                    <audio src={audioSrc} controls className="h-8 max-w-full" />
                    <button type="button" onClick={recorder.clear} className="opacity-60">
                      {t("removeRecording")}
                    </button>
                  </>
                )}
              </div>
              <p className="mt-1 text-xs opacity-60">
                {recorder.error ? t("micError") : t("recordingHint")}
              </p>
            </div>

            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5"
              />
              <span className="text-xs opacity-80">{t("consent")}</span>
            </label>

            <Captcha onToken={setCaptcha} resetKey={captchaRound} />
            {status === "error" && <p className="text-red-600">{t("error")}</p>}
            {status === "tooMany" && <p className="text-red-600">{t("tooMany")}</p>}
            <button
              type="submit"
              disabled={
                status === "sending" ||
                !spelling.trim() ||
                !consent ||
                !where ||
                !variety ||
                recorder.recording ||
                (!!CAPTCHA_SITE_KEY && !captcha)
              }
              className="w-full rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-40"
            >
              {status === "sending" ? t("sending") : t("send")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
