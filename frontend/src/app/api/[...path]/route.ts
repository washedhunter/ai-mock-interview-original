// Same-origin proxy to the FastAPI backend. The browser only ever talks to this app's origin, so
// the httpOnly session cookie works without CORS, and BACKEND_URL is read at request time (one
// image runs anywhere).
import type { NextRequest } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "transfer-encoding",
  "set-cookie",
]);
const FORWARD = ["accept", "content-type", "cookie", "user-agent"];
const MAX_BODY_BYTES = Number(process.env.MAX_UPLOAD_BYTES ?? 10 * 1024 * 1024) + 64 * 1024;

/** The client IP as seen by the hop in front of this server: the LAST X-Forwarded-For entry
 *  (the platform ingress appends it; Next.js fills the header from the socket when absent).
 *  Earlier entries are whatever the browser claimed, so they are dropped. */
function clientIp(req: NextRequest): string | null {
  const parts = (req.headers.get("x-forwarded-for") ?? "").split(",").map((p) => p.trim()).filter(Boolean);
  return parts.at(-1) ?? null;
}

async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const backend = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const { path } = await ctx.params;
  const target = `${backend}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const length = Number(req.headers.get("content-length") ?? 0);
  if (length > MAX_BODY_BYTES) {
    return Response.json({ detail: "Recording is too large" }, { status: 413 });
  }

  const headers = new Headers();
  for (const name of FORWARD) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  const ip = clientIp(req);
  if (ip) {
    headers.set("x-forwarded-for", ip);
    // Also sent in a header of our own: some hosts' internal hop to the backend rewrites
    // X-Forwarded-For with this server's address (Vercel service bindings do); the name is
    // app-specific so it cannot collide with a header a platform sets. The browser
    // can't set it, because only the FORWARD allowlist above is copied from the request.
    headers.set("x-interview-client-ip", ip);
  }
  // Lets the backend mark the session cookie Secure when the site is served over HTTPS.
  const proto = req.headers.get("x-forwarded-proto")?.split(",")[0].trim() || req.nextUrl.protocol.replace(":", "");
  headers.set("x-forwarded-proto", proto);

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half"; // stream uploads (audio) straight through
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json({ detail: "The interview API is not reachable. Is the backend running?" }, { status: 502 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!HOP_BY_HOP.has(name)) out.set(name, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
