"use client";

import { useState } from "react";

// Account picture: the Google or GitHub photo when the account signed in with one,
// otherwise (or if the photo fails to load) the first letter of the name.
export default function Avatar({ name, src, className }: { name: string; src?: string | null; className: string }) {
  const [broken, setBroken] = useState(false);
  if (src && !broken) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" className={`${className} avatar-img`} referrerPolicy="no-referrer" onError={() => setBroken(true)} />;
  }
  return <span className={className} aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>;
}
