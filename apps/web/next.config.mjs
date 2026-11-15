const backend = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
/** @type {import('next').NextConfig} */
const config = {
  poweredByHeader: false,
  devIndicators: false,
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
      { key: 'Content-Security-Policy', value: "frame-ancestors 'self'" },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    ] }];
  },
  async rewrites() {
    return [{ source: '/backend/:path*', destination: `${backend}/api/v1/:path*` }];
  },
};
export default config;
