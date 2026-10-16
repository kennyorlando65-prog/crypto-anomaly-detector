/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Python engine is its own service (see the root vercel.json) and lives
  // in a sibling directory, so Next.js never compiles it here. There are
  // deliberately no rewrites in this file: on Vercel the root vercel.json owns
  // routing, and two places defining routes for the same path is how you get
  // a 404 that is hard to explain.
  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
