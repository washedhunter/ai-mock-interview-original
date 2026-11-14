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
const FORWARD = ["accept", "content-type", "cookie", "user-agent", "x-forwarded-for"];

async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const backend = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const { path } = await ctx.params;
  const target = `${backend}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

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
