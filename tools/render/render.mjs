// Headless preview renders: node render.mjs <out.png> "<query string>" [...]
// Serves the repository root over HTTP and screenshots tools/render/preview.html.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg" };

const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { "content-type": types[path.extname(p)] || "application/octet-stream" });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const jobs = [];
for (let i = 2; i + 1 < process.argv.length; i += 2) jobs.push([process.argv[i], process.argv[i + 1]]);

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage();
page.on("console", (m) => { if (m.type() === "error") console.error("[page]", m.text()); });
for (const [out, query] of jobs) {
  const params = new URLSearchParams(query);
  const w = +(params.get("w") || 900), h = +(params.get("h") || 900);
  await page.setViewportSize({ width: w, height: h });
  await page.goto(`http://127.0.0.1:${port}/tools/render/preview.html?${query}`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
  await page.locator("canvas").screenshot({ path: out });
  console.log("rendered", out);
}
await browser.close();
server.close();
