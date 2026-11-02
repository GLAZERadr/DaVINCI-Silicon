import type { NextConfig } from "next";

// Static export: the board is built from the committed evidence/ bundle and
// needs no server. NEXT_PUBLIC_DAVINCI_API (optional) enables live replay.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // Dev server only: the default bottom-left badge covers the sidebar's collapse button.
  devIndicators: { position: "bottom-right" },
};

export default config;
