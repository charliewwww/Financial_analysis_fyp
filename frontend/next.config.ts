import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the floating dev/build activity indicator so demo and shared
  // builds don't show a "N" badge overlapping app content.
  devIndicators: false,
};

export default nextConfig;
