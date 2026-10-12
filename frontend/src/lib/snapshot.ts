import type { Map as MapLibreMap } from "maplibre-gl";

export type SnapshotText = { title: string; subtitle?: string; footer: string };

const HEADER = 64; // CSS pixels above the map for the title
const FOOTER = 32; // CSS pixels below it for the site address

/**
 * The map as a PNG: the WebGL canvas (read during a render, so no preserveDrawingBuffer is
 * needed), the visible word labels (HTML markers, redrawn onto the image), a title and the
 * site's address.
 */
export function snapshotMap(
  map: MapLibreMap,
  container: HTMLElement,
  text: SnapshotText,
): Promise<Blob | null> {
  return new Promise((resolve) => {
    map.once("render", () => {
      const source = map.getCanvas();
      const scale = source.width / source.clientWidth;
      const width = source.clientWidth;
      const height = source.clientHeight;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round((height + HEADER + FOOTER) * scale);
      const ctx = canvas.getContext("2d");
      if (!ctx) return resolve(null);
      ctx.scale(scale, scale);

      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width, height + HEADER + FOOTER);
      ctx.drawImage(source, 0, HEADER, width, height);

      const box = container.getBoundingClientRect();
      ctx.textBaseline = "middle";
      for (const el of container.querySelectorAll<HTMLElement>(
        ".maplibregl-marker",
      )) {
        if (el.style.visibility === "hidden") continue;
        const r = el.getBoundingClientRect();
        const x = r.left - box.left;
        const y = r.top - box.top + HEADER;
        if (
          x + r.width < 0 ||
          x > width ||
          r.top - box.top < 0 ||
          r.top - box.top > height
        ) {
          continue;
        }
        const style = getComputedStyle(el);
        ctx.fillStyle = style.backgroundColor;
        ctx.beginPath();
        ctx.roundRect(x, y, r.width, r.height, 4);
        ctx.fill();
        ctx.fillStyle = style.color;
        ctx.font = `600 ${style.fontSize} ${style.fontFamily}`;
        ctx.fillText(
          el.textContent ?? "",
          x + parseFloat(style.paddingLeft),
          y + r.height / 2,
          r.width,
        );
      }

      ctx.fillStyle = "#0f172a";
      ctx.font = `700 26px system-ui, sans-serif`;
      ctx.fillText(text.title, 16, 26);
      if (text.subtitle) {
        ctx.fillStyle = "#475569";
        ctx.font = `14px system-ui, sans-serif`;
        ctx.fillText(text.subtitle, 16, 50, width - 32);
      }
      ctx.fillStyle = "#4338ca";
      ctx.font = `600 14px system-ui, sans-serif`;
      ctx.fillText(text.footer, 16, HEADER + height + FOOTER / 2);
      ctx.fillStyle = "#64748b";
      ctx.font = `11px system-ui, sans-serif`;
      const credit = "© OpenStreetMap, OpenMapTiles, OpenFreeMap";
      ctx.fillText(
        credit,
        width - 16 - ctx.measureText(credit).width,
        HEADER + height + FOOTER / 2,
      );

      canvas.toBlob(resolve, "image/png");
    });
    map.triggerRepaint();
  });
}

/** Offer a blob to the visitor as a file download. */
export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** A 1200×630 card (the size social networks preview) with a big line of text. */
export function resultCard(text: {
  kicker: string;
  title: string;
  footer: string;
}): Promise<Blob | null> {
  const canvas = document.createElement("canvas");
  canvas.width = 1200;
  canvas.height = 630;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  const gradient = ctx.createLinearGradient(0, 0, 1200, 630);
  gradient.addColorStop(0, "#eef2ff");
  gradient.addColorStop(1, "#ede9fe");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 1200, 630);
  ctx.textBaseline = "top";
  ctx.fillStyle = "#4338ca";
  ctx.font = "700 40px system-ui, sans-serif";
  ctx.fillText("Dialectio", 72, 64);
  ctx.fillStyle = "#64748b";
  ctx.font = "32px system-ui, sans-serif";
  ctx.fillText(text.kicker, 72, 200, 1056);
  ctx.fillStyle = "#0f172a";
  ctx.font = "700 64px system-ui, sans-serif";
  // Wrap the title onto up to three lines
  const words = text.title.split(" ");
  let line = "";
  let y = 260;
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > 1056 && line) {
      ctx.fillText(line, 72, y);
      line = word;
      y += 80;
    } else {
      line = next;
    }
  }
  ctx.fillText(line, 72, y);
  ctx.fillStyle = "#6d28d9";
  ctx.font = "600 30px system-ui, sans-serif";
  ctx.fillText(text.footer, 72, 540);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

/** Share a picture through the system share sheet (phones), or download it. */
export async function shareOrDownload(
  blob: Blob,
  filename: string,
  text: string,
) {
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], text });
      return;
    } catch {
      // cancelled or not allowed: fall back to downloading
    }
  }
  download(blob, filename);
}
