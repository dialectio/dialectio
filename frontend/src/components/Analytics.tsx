"use client";

import { useEffect } from "react";

// Signs of a person: scrapers that load a page in a headless browser and leave never send them.
const HUMAN_EVENTS = ["pointermove", "pointerdown", "touchstart", "keydown", "wheel", "scroll"];

/**
 * Visit statistics (Umami, self-hosted, no cookies). The script loads only after the visitor
 * first moves the mouse, touches, scrolls or types: headless scrapers posing as ordinary
 * browsers (thousands of one-page "visits" a day from proxy networks) are then not counted.
 * Once loaded, Umami counts the current page and every later navigation by itself.
 */
export default function Analytics({ src, websiteId }: { src: string; websiteId: string }) {
  useEffect(() => {
    const load = () => {
      HUMAN_EVENTS.forEach((e) => window.removeEventListener(e, load));
      if (document.querySelector(`script[data-website-id="${websiteId}"]`)) return;
      const script = document.createElement("script");
      script.src = src;
      script.defer = true;
      script.dataset.websiteId = websiteId;
      // Every word is its own page; ?region= is a filter on the same page, so the query
      // string is left out.
      script.dataset.excludeSearch = "true";
      document.body.appendChild(script);
    };
    HUMAN_EVENTS.forEach((e) => window.addEventListener(e, load, { passive: true }));
    return () => HUMAN_EVENTS.forEach((e) => window.removeEventListener(e, load));
  }, [src, websiteId]);
  return null;
}
