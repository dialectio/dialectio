import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";

/** Social preview size recommended by Open Graph consumers. */
export const OG_SIZE = { width: 1200, height: 630 };

// Noto Sans (SIL Open Font License, assets/fonts/OFL.txt): Latin, Cyrillic and Greek.
const FONT_DIR = join(process.cwd(), "assets", "fonts");
const fonts = Promise.all([
  readFile(join(FONT_DIR, "NotoSans-Regular.ttf")),
  readFile(join(FONT_DIR, "NotoSans-Bold.ttf")),
]);

/** Words the bundled font can draw (others would render as empty boxes). */
const DRAWABLE = /^[\p{Script=Latin}\p{Script=Cyrillic}\p{Script=Greek}\s'’.-]+$/u;
export const isDrawable = (text: string) => DRAWABLE.test(text);

export type OgCard = {
  kicker: string;
  title: string;
  /** Violet line, e.g. dialect words */
  highlight?: string[];
  /** Grey line, e.g. the word in other languages */
  secondary?: string[];
  footer: string;
};

/** A 1200×630 card: brand, big title, violet and grey word lines. */
export async function renderCard(card: OgCard): Promise<ImageResponse> {
  const [regular, bold] = await fonts;
  const line = (words: string[] | undefined) => (words ?? []).filter(isDrawable).join("  ·  ");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "linear-gradient(135deg, #eef2ff 0%, #f5f3ff 55%, #ede9fe 100%)",
          fontFamily: "Noto Sans",
          color: "#0f172a",
        }}
      >
        <div style={{ display: "flex", fontSize: 34, fontWeight: 700, color: "#4338ca" }}>
          Dialectio
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", fontSize: 30, color: "#64748b" }}>{card.kicker}</div>
          <div style={{ display: "flex", fontSize: 104, fontWeight: 700, lineHeight: 1.05 }}>
            {card.title}
          </div>
          {line(card.highlight) && (
            <div style={{ display: "flex", fontSize: 44, fontWeight: 700, color: "#6d28d9" }}>
              {line(card.highlight)}
            </div>
          )}
          {line(card.secondary) && (
            <div style={{ display: "flex", fontSize: 36, color: "#334155" }}>
              {line(card.secondary)}
            </div>
          )}
        </div>
        <div style={{ display: "flex", fontSize: 28, color: "#64748b" }}>{card.footer}</div>
      </div>
    ),
    {
      ...OG_SIZE,
      fonts: [
        { name: "Noto Sans", data: regular, weight: 400, style: "normal" },
        { name: "Noto Sans", data: bold, weight: 700, style: "normal" },
      ],
    },
  );
}
