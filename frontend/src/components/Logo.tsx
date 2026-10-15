import { useId } from "react";

/** The Dialectio mark (a speech bubble with a sound wave) and the name. */
export default function Logo({ withName = true }: { withName?: boolean }) {
  const gradient = useId();
  return (
    <span className="inline-flex items-center gap-2">
      <svg
        viewBox="0 0 32 32"
        width="28"
        height="28"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#4f46e5" />
            <stop offset="1" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <path
          d="M6 3h20a4 4 0 0 1 4 4v14a4 4 0 0 1-4 4H14l-6 5v-5H6a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4z"
          fill={`url(#${gradient})`}
        />
        <g fill="#fff">
          <rect x="7.5" y="11" width="2.8" height="6" rx="1.4" />
          <rect x="12" y="7.5" width="2.8" height="13" rx="1.4" />
          <rect x="16.5" y="9.5" width="2.8" height="9" rx="1.4" />
          <rect x="21" y="12" width="2.8" height="4" rx="1.4" />
        </g>
      </svg>
      {withName && (
        <span className="font-serif text-xl font-semibold tracking-tight">
          Dialectio
        </span>
      )}
    </span>
  );
}
