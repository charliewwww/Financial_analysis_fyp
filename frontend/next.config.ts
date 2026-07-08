import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the floating dev/build activity indicator so demo and shared
  // builds don't show a "N" badge overlapping app content.
  devIndicators: false,

  // Pin Turbopack's workspace root to the frontend project directory. Without
  // this, Turbopack infers the git repo root (one level up, where .git lives)
  // as the workspace root and then fails to resolve CSS package imports like
  // `@import "tailwindcss"` in globals.css ("Can't resolve 'tailwindcss'").
  // The dev/build scripts always run with the frontend dir as the CWD.
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
