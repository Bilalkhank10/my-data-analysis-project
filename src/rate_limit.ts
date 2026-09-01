import type { Request, Response, NextFunction } from "express";

/**
 * Minimal fixed-window in-memory rate limiter (no external dependencies).
 * Per-IP counters with automatic expiry; suitable for a single-process
 * local studio server.
 */
export interface RateLimiterOptions {
  windowMs: number;
  max: number;
  keyFn?: (req: Request) => string;
  onLimit?: (req: Request, res: Response) => void;
}

interface WindowState {
  count: number;
  resetAt: number;
}

export class RateLimiter {
  private states = new Map<string, WindowState>();
  private windowMs: number;
  private max: number;
  private keyFn: (req: Request) => string;
  private onLimit: (req: Request, res: Response) => void;

  constructor(opts: RateLimiterOptions) {
    this.windowMs = opts.windowMs;
    this.max = opts.max;
    this.keyFn = opts.keyFn || ((req) => req.ip || "unknown");
    this.onLimit =
      opts.onLimit ||
      ((req, res) => {
        res.status(429).json({ detail: "Too many requests. Please slow down." });
      });
  }

  /** Returns true when the request is allowed. */
  allow(key: string, now: number = Date.now()): boolean {
    const state = this.states.get(key);
    if (!state || state.resetAt <= now) {
      this.states.set(key, { count: 1, resetAt: now + this.windowMs });
      return true;
    }
    if (state.count >= this.max) return false;
    state.count++;
    return true;
  }

  /** Drop expired windows (keeps the map bounded). */
  sweep(now: number = Date.now()): void {
    for (const [key, state] of this.states) {
      if (state.resetAt <= now) this.states.delete(key);
    }
  }

  middleware = (req: Request, res: Response, next: NextFunction): void => {
    const now = Date.now();
    if (this.states.size > 10_000) this.sweep(now);
    const key = this.keyFn(req);
    if (!this.allow(key, now)) {
      res.setHeader("Retry-After", String(Math.ceil(this.windowMs / 1000)));
      this.onLimit(req, res);
      return;
    }
    next();
  };
}

/** General API limiter per IP. */
export const apiLimiter = new RateLimiter({
  windowMs: 60 * 1000,
  max: Number(process.env.API_RATE_LIMIT_MAX) || 600,
});
