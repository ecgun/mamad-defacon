// Renders src/video.html frame by frame with headless Chromium.
//
//   node tools/render.cjs                       full video -> build/video.mp4 (no audio)
//   node tools/render.cjs --stills 3.5,60,120   PNG previews -> build/stills/
//
// Options: --fps 30  --workers 3  --from <s>  --to <s>
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(ROOT, "build");
const W = 1920, H = 1080;

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1] ?? true]] : acc), [])
);
const fps = +(args.fps || 30);
const workers = +(args.workers || 3);
const timeline = JSON.parse(fs.readFileSync(path.join(BUILD, "timeline.json"), "utf8"));

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.addInitScript(`window.__TIMELINE__ = ${JSON.stringify(timeline)};`);
  await page.goto("file://" + path.join(ROOT, "src", "video.html"));
  await page.evaluate(() => document.fonts.ready);
  if (errors.length || !(await page.evaluate(() => typeof window.renderFrame === "function"))) {
    throw new Error("page failed to initialise:\n" + errors.join("\n"));
  }
  return page;
}

function encoder(file) {
  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", String(fps), file,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => ff.on("close", (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exited ${c}`)))));
  return { ff, done };
}

async function renderRange(browser, first, last, file, report) {
  const page = await openPage(browser);
  const { ff, done } = encoder(file);
  for (let f = first; f < last; f++) {
    await page.evaluate((t) => window.renderFrame(t), f / fps);
    const jpg = await page.screenshot({ type: "jpeg", quality: 94 });
    if (!ff.stdin.write(jpg)) await new Promise((r) => ff.stdin.once("drain", r));
    report();
  }
  ff.stdin.end();
  await done;
  await page.close();
}

async function stills(browser, times) {
  const dir = path.join(BUILD, "stills");
  fs.mkdirSync(dir, { recursive: true });
  const page = await openPage(browser);
  for (const t of times) {
    await page.evaluate((t) => window.renderFrame(t), t);
    const file = path.join(dir, `t${t.toFixed(2).padStart(7, "0")}.png`);
    await page.screenshot({ path: file });
    console.log(file);
  }
}

async function main() {
  const browser = await chromium.launch();
  try {
    if (args.stills) {
      await stills(browser, String(args.stills).split(",").map(Number));
      return;
    }
    const from = Math.round(+(args.from || 0) * fps);
    const to = Math.round(+(args.to || timeline.duration) * fps);
    const total = to - from;

    const page = await openPage(browser);
    fs.writeFileSync(path.join(BUILD, "events.json"), JSON.stringify(await page.evaluate(() => window.__EVENTS__), null, 2));
    await page.close();

    let rendered = 0;
    const started = Date.now();
    const report = () => {
      rendered++;
      if (rendered % 150 === 0 || rendered === total) {
        const rate = rendered / ((Date.now() - started) / 1000);
        console.log(`${rendered}/${total} frames  ${rate.toFixed(1)} fps  eta ${((total - rendered) / rate).toFixed(0)}s`);
      }
    };
    const per = Math.ceil(total / workers);
    const parts = [];
    for (let i = 0; i < workers; i++) {
      const a = from + i * per, b = Math.min(to, a + per);
      if (a < b) parts.push({ a, b, file: path.join(BUILD, `part${i}.mp4`) });
    }
    await Promise.all(parts.map((p) => renderRange(browser, p.a, p.b, p.file, report)));

    const list = path.join(BUILD, "parts.txt");
    fs.writeFileSync(list, parts.map((p) => `file '${p.file}'`).join("\n") + "\n");
    await new Promise((res, rej) => spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", path.join(BUILD, "video.mp4")], { stdio: "inherit" })
      .on("close", (c) => (c === 0 ? res() : rej(new Error("concat failed")))));
    parts.forEach((p) => fs.unlinkSync(p.file));
    console.log("wrote build/video.mp4");
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
