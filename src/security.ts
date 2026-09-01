/**
 * Security headers applied to every response. The UIs are served as inline
 * HTML+JS documents, so CSP allows 'unsafe-inline' for script/style but
 * restricts everything else to self (images from Fiverr CDN allowed).
 */
export function securityHeaders(): Record<string, string> {
  return {
    "Content-Security-Policy": [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "connect-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
  };
}
