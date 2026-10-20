// Video & audio with ffmpeg.wasm. The small wrapper (@ffmpeg/ffmpeg, @ffmpeg/util) is vendored so its
// worker is same-origin; the ~31 MB single-threaded core is fetched from jsDelivr the first time only
// (the browser caches it). Input files are mounted read-only (WORKERFS), so they are not copied into memory.
import { VENDOR, loadScript, baseName, extOf, UserError, cancelled, fa } from "./util.js";

export const CORE_BASE = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/umd/";

let ff = null, loading = null, core = null, logs = [], onLog = null, dirN = 0;

async function coreUrls(ctx) {
  if (core) return core;
  const { toBlobURL } = await import(VENDOR + "ffmpeg/util/index.js");
  const title = "در حال دریافت موتور ویدیو (حدود ۳۱ مگابایت، فقط بار اول)…";
  ctx.notice(title, 0);
  try {
    const js = await toBlobURL(CORE_BASE + "ffmpeg-core.js", "text/javascript");
    const wasm = await toBlobURL(CORE_BASE + "ffmpeg-core.wasm", "application/wasm", true, (e) => {
      if (e && e.total > 0) ctx.notice(title, e.received / e.total);
    });
    core = { coreURL: js, wasmURL: wasm };
    return core;
  } catch (e) {
    throw new UserError("موتور ویدیو دانلود نشد. اتصال اینترنت را بررسی کنید و دوباره امتحان کنید.");
  } finally {
    ctx.notice(null);
  }
}

async function ensure(ctx) {
  if (ff && ff.loaded) return ff;
  if (!loading) {
    loading = (async () => {
      await loadScript(VENDOR + "ffmpeg/ffmpeg.js");
      const urls = await coreUrls(ctx);
      const inst = new window.FFmpegWASM.FFmpeg();
      inst.on("log", ({ message }) => {
        logs.push(message);
        if (logs.length > 400) logs.splice(0, 200);
        if (onLog) onLog(message);
      });
      ctx.status("در حال آماده‌سازی موتور ویدیو…");
      await inst.load(urls);
      ff = inst;
      return inst;
    })().finally(() => { loading = null; });
  }
  return loading;
}

// Cancel: kill the worker. The next job loads the core again from the cached blob URLs.
export function stop() {
  if (ff) { try { ff.terminate(); } catch (e) { /* already gone */ } ff = null; }
}

function parseTime(s) {
  const m = /(\d+):(\d+):(\d+(?:\.\d+)?)/.exec(s);
  return m ? (+m[1]) * 3600 + (+m[2]) * 60 + parseFloat(m[3]) : 0;
}

async function probe(inst, input) {
  logs = [];
  await inst.exec(["-hide_banner", "-i", input]);  // exits with 1 ("no output file"), but prints the streams
  const text = logs.join("\n");
  const v = /Stream #[^\n]*Video: (\w+)/.exec(text);
  const a = /Stream #[^\n]*Audio: (\w+)/.exec(text);
  const d = /Duration: (\d+:\d+:\d+(?:\.\d+)?)/.exec(text);
  return { video: v ? v[1] : null, audio: a ? a[1] : null, duration: d ? parseTime(d[1]) : 0, text };
}

const EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2";
const X264 = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"];
const AUDIO_ARGS = {
  mp3: (br) => ["-c:a", "libmp3lame", "-b:a", br + "k"],
  m4a: (br) => ["-c:a", "aac", "-b:a", br + "k"],
  aac: (br) => ["-c:a", "aac", "-b:a", br + "k"],
  ogg: (br) => ["-c:a", "libvorbis", "-b:a", br + "k"],
  opus: (br) => ["-c:a", "libopus", "-b:a", br + "k"],
  wav: () => ["-c:a", "pcm_s16le"],
  flac: () => ["-c:a", "flac"]
};
const MIME = {
  mp4: "video/mp4", mov: "video/quicktime", mkv: "video/x-matroska", webm: "video/webm", gif: "image/gif",
  mp3: "audio/mpeg", m4a: "audio/mp4", aac: "audio/aac", ogg: "audio/ogg", opus: "audio/ogg", wav: "audio/wav", flac: "audio/flac"
};

function scaleFor(res) {
  res = Number(res) || 0;
  if (!res) return EVEN;
  // The short side becomes at most `res` pixels (portrait videos too), keeping even dimensions.
  return "scale=w='if(gte(iw,ih),-2,trunc(min(" + res + ",iw)/2)*2)':h='if(gte(iw,ih),trunc(min(" + res + ",ih)/2)*2,-2)',setsar=1";
}

// Returns a list of argument sets to try in order (a fast stream copy first when it is safe).
function plan(target, info, opt, mode, inExt) {
  const audioBr = Number(opt.bitrate) || 192;
  const hasV = !!info.video, hasA = !!info.audio;
  if (mode === "compress") {
    // A music file's cover art shows up as an mjpeg/png "video" stream; that is not a video.
    if (hasV && !/^(mjpeg|png|bmp|gif)$/.test(info.video)) {
      return { ext: "mp4", tries: [[...X264, "-crf", String(opt.crf || 28), "-vf", scaleFor(opt.res),
        ...(hasA ? ["-c:a", "aac", "-b:a", (opt.abr || 96) + "k"] : ["-an"]), "-movflags", "+faststart"]] };
    }
    if (!hasA) throw new UserError("این فایل صدا ندارد.");
    const ext = AUDIO_ARGS[inExt] && !/^(wav|flac)$/.test(inExt) ? inExt : "mp3";
    return { ext, tries: [["-vn", ...AUDIO_ARGS[ext](Number(opt.bitrate) || 96), ...(opt.mono ? ["-ac", "1"] : [])]] };
  }
  if (AUDIO_ARGS[target]) {
    if (!hasA) throw new UserError("این فایل صدا ندارد.");
    return { ext: target, tries: [["-vn", ...AUDIO_ARGS[target](audioBr)]] };
  }
  if (!hasV) throw new UserError("در این فایل تصویر ویدیویی پیدا نشد.");
  if (target === "gif") {
    const w = Number(opt.gifWidth) || 0, fps = Number(opt.fps) || 10;
    const sc = w ? "scale='min(" + w + ",iw)':-1:flags=lanczos" : "scale=iw:-1:flags=lanczos";
    return { ext: "gif", tries: [["-an", "-vf", "fps=" + fps + "," + sc + ",split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5", "-loop", "0"]] };
  }
  const reencode = target === "webm"
    ? ["-c:v", "libvpx", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "1500k", "-crf", "10", "-vf", EVEN,
       ...(hasA ? ["-c:a", "libvorbis", "-b:a", "128k"] : ["-an"])]
    : [...X264, "-crf", "23", "-vf", EVEN, ...(hasA ? ["-c:a", "aac", "-b:a", "160k"] : ["-an"]),
       ...(target === "mkv" ? [] : ["-movflags", "+faststart"])];
  const tries = [];
  const vOk = { mp4: /^(h264|hevc|mpeg4|av1)$/, mov: /^(h264|hevc|mpeg4|prores|mjpeg)$/, mkv: /./, webm: /^(vp8|vp9|av1)$/ }[target];
  const aOk = { mp4: /^(aac|mp3)$/, mov: /^(aac|mp3|pcm_s16le|alac)$/, mkv: /./, webm: /^(vorbis|opus)$/ }[target];
  if (vOk && vOk.test(info.video) && (!hasA || aOk.test(info.audio))) {
    tries.push(["-map", "0:v:0", ...(hasA ? ["-map", "0:a:0"] : []), "-c", "copy", ...(/^(mp4|mov)$/.test(target) ? ["-movflags", "+faststart"] : [])]);
  }
  tries.push(reencode);
  return { ext: target, tries };
}

export async function run(item, opt, ctx, mode) {
  const file = item.file, inExt = extOf(file.name);
  const inst = await ensure(ctx);
  if (ctx.isCancelled()) throw cancelled();
  const dir = "/in" + dirN++;
  let mounted = false, input;
  try {
    await inst.createDir(dir);
    try {
      await inst.mount("WORKERFS", { files: [file] }, dir);
      mounted = true;
      input = dir + "/" + file.name;
    } catch (e) {
      input = dir + "/input." + (inExt || "bin");
      await inst.writeFile(input, new Uint8Array(await file.arrayBuffer()));
    }
    ctx.status("در حال بررسی فایل…");
    const info = await probe(inst, input);
    if (!info.video && !info.audio) throw new UserError("ffmpeg این فایل را نشناخت.");
    const p = plan(opt.target, info, opt, mode, inExt);
    const out = "/out" + dirN + "." + p.ext;
    const isCopy = (args) => args.indexOf("copy") >= 0;
    let ok = false;
    for (const args of p.tries) {
      if (ctx.isCancelled()) throw cancelled();
      ctx.status(isCopy(args) ? "در حال تبدیل سریع (بدون فشرده‌سازی دوباره)…" : "در حال تبدیل… ممکن است چند دقیقه طول بکشد");
      ctx.progress(0);
      onLog = (m) => {
        const t = /time=\s*(\d+:\d+:\d+(?:\.\d+)?)/.exec(m);
        if (t && info.duration) {
          const f = Math.min(1, parseTime(t[1]) / info.duration);
          ctx.progress(f);
          ctx.status((isCopy(args) ? "تبدیل سریع… " : "در حال تبدیل… ") + fa(Math.round(f * 100)) + "٪");
        }
      };
      logs = [];
      const code = await inst.exec(["-hide_banner", "-nostdin", "-i", input, ...args, "-y", out]);
      onLog = null;
      if (code === 0) { ok = true; break; }
      try { await inst.deleteFile(out); } catch (e) { /* not created */ }
    }
    if (!ok) {
      const last = logs.filter((l) => /error|invalid|not supported|unknown/i.test(l)).pop();
      throw new UserError("ffmpeg نتوانست این فایل را تبدیل کند" + (last ? " (" + last.slice(0, 120) + ")" : "") + ".");
    }
    const data = await inst.readFile(out);
    await inst.deleteFile(out);
    const name = baseName(file.name) + (mode === "compress" ? "-small." : ".") + p.ext;
    const blob = new Blob([data.buffer], { type: MIME[p.ext] || "application/octet-stream" });
    if (mode === "compress" && blob.size >= file.size) {
      return { outputs: [{ blob: file, name: file.name }], note: "کوچک‌تر نشد؛ فایل اصلی نگه داشته شد" };
    }
    return { outputs: [{ blob, name }], note: "" };
  } catch (e) {
    if (ctx.isCancelled() || /terminate/i.test(String(e && e.message))) throw cancelled();
    if (e && e.user) throw e;
    // Out of memory or a crashed core: start fresh next time.
    stop();
    throw new UserError("پردازش ناموفق بود؛ شاید فایل برای مرورگر بزرگ باشد. نسخهٔ ویندوز یا اندروید را امتحان کنید.");
  } finally {
    onLog = null;
    if (ff === inst) {
      try { if (mounted) await inst.unmount(dir); else await inst.deleteFile(input); } catch (e) { /* ignore */ }
      try { await inst.deleteDir(dir); } catch (e) { /* ignore */ }
    }
  }
}
