import { notFound } from "next/navigation";

/** Any other path under a locale: the localized 404 page. */
export default function CatchAll() {
  notFound();
}
