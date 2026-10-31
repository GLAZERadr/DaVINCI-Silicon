// DaVINCI mark redrawn from the brand board (no source file in the repo yet):
// a forward-slanted D, DaVINCI Blue → Purple. Replace with the official SVG when available.
export function Mark({ size = 30, id = "dv" }: { size?: number; id?: string }) {
  return (
    <svg width={size * 1.58} height={size} viewBox="0 0 120 76" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2563EB" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      <path fill={`url(#${id})`}
        d="M28 0H84C104 0 120 16 120 36V40C120 60 104 76 84 76H46L64 50H82C87 50 90 47 90 42V34C90 29 87 26 82 26H22Z" />
      <path fill={`url(#${id})`} d="M0 76H32L61 34H29Z" />
    </svg>
  );
}

export default function Logo() {
  return (
    <>
      <Mark />
      <span className="word">DaVINCI</span>
    </>
  );
}
