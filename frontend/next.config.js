// =============================================================================
// next.config.js — Next.js configuration for the LateD SOC frontend.
// =============================================================================
//
// PURPOSE
// -------
// Configures build options, environment variable exposure, and any rewrites
// to the backend supervision API.
//
// CYBERSECURITY NOTES
// -------------------
//   - Public env vars are prefixed NEXT_PUBLIC_* (Next.js convention).
//     Anything ELSE never reaches the browser bundle — this is critical
//     since the SOC UI is served to authenticated analysts on internal
//     networks but should still treat browser memory as untrusted.
//   - Strict CSP headers are applied (see headers() below).
// =============================================================================

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false, // do not advertise the framework version
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          {
            key: 'Content-Security-Policy',
            value:
              "default-src 'self'; " +
              "script-src 'self' 'unsafe-inline'; " +
              "style-src 'self' 'unsafe-inline'; " +
              "img-src 'self' data:; " +
              "connect-src 'self' " +
              (process.env.NEXT_PUBLIC_API_URL || '') + ' ' +
              (process.env.NEXT_PUBLIC_WS_URL || '') + ';',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
