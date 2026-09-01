/**
 * Short-lived signed download URLs.
 *
 * Replaces session tokens in query strings (which leak via logs/referrers):
 * each download link is an HMAC signature over (filename, expiry) with a
 * 1-hour TTL, so a leaked link only works for an hour and only for that file.
 */
import crypto from "crypto";

export const DOWNLOAD_TTL_SECONDS = 60 * 60;

export function downloadSignature(filename: string, expiry: number, secret: string): string {
  return crypto.createHmac("sha256", secret).update(`${filename}:${expiry}`).digest("hex");
}

export function signDownload(
  filename: string,
  secret: string,
  ttlSeconds: number = DOWNLOAD_TTL_SECONDS,
  now: number = Date.now()
): string {
  const expiry = Math.floor(now / 1000) + ttlSeconds;
  return `/download/${filename}?dl=${expiry}.${downloadSignature(filename, expiry, secret)}`;
}

export function verifyDownloadSignature(
  filename: string,
  dl: string | undefined,
  secret: string,
  now: number = Date.now()
): boolean {
  if (!dl || typeof dl !== "string" || !dl.includes(".")) return false;
  const [expiryStr, signature] = dl.split(".", 2);
  const expiry = parseInt(expiryStr, 10);
  if (!Number.isFinite(expiry)) return false;
  if (expiry * 1000 < now) return false;
  const expected = downloadSignature(filename, expiry, secret);
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/** Replace a job's plain download paths with signed, time-limited URLs. */
export function withSignedDownloads<T extends { downloads?: { json?: string; csv?: string } }>(
  job: T,
  secret: string
): T {
  if (!job?.downloads) return job;
  const jsonName = job.downloads.json?.split("/").pop();
  const csvName = job.downloads.csv?.split("/").pop();
  return {
    ...job,
    downloads: {
      ...(jsonName ? { json: signDownload(jsonName, secret) } : {}),
      ...(csvName ? { csv: signDownload(csvName, secret) } : {}),
    },
  };
}
