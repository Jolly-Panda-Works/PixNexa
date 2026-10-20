// Images: decode (canvas, HEIC via heic2any), resize, grayscale, encode with canvas or jSquash
// (MozJPEG, OxiPNG, AVIF) in a worker, target size by binary search, and images -> one PDF.
import { VENDOR, loadScript, baseName, extOf, UserError, cancelled, fa } from "./util.js";

// Safari limits a canvas to about 16.7 million pixels; bigger images are scaled down only if needed.
const SAFE_PIXELS = 16777216;
const MIME = { jpeg: "image/jpeg", png: "image/png", webp: "image/webp", avif: "image/avif" };
const EXT = { jpeg: "jpg", png: "png", webp: "webp", avif: "avif" };

export const webpOk = (() => {
  try {
    const c = document.createElement("canvas");
    c.width = c.height = 1;
    return c.toDataURL("image/webp").indexOf("data:image/webp") === 0;
  } catch (e) { return false; }
})();

// ---------- codec worker ----------
let worker = null, nextId = 0, pending = {};
function getWorker() {
  if (!worker) {
    worker = new Worker(new URL("./codec-worker.js", import.meta.url), { type: "module" });
    worker.onmessage = (e) => {
      const p = pending[e.data.id];
      if (!p) return;
      delete pending[e.data.id];
      if (e.data.ok) p.resolve(e.data.buf); else p.reject(new Error(e.data.error));
    };
    worker.onerror = (e) => {
      const all = pending; pending = {};
      Object.keys(all).forEach((k) => all[k].reject(new Error((e && e.message) || "worker")));
      worker = null;
    };
  }
  return worker;
}
function workerCall(op, image, options) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending[id] = { resolve, reject };
    getWorker().postMessage({ id, op, image, options });
  });
}
// Called when the user presses Cancel: stops a long AVIF/MozJPEG encode right away.
export function stop() {
  if (worker) { worker.terminate(); worker = null; }
  const all = pending; pending = {};
  Object.keys(all).forEach((k) => all[k].reject(cancelled()));
}

// ---------- decode ----------
function decodeNative(blob) {
  const viaImg = () => new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(blob);
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("decode")); };
    img.src = url;
  });
  if (window.createImageBitmap) {
    return createImageBitmap(blob, { imageOrientation: "from-image" }).catch(viaImg);
  }
  return viaImg();
}

export function isHeic(file) {
  return /^image\/hei[cf]/i.test(file.type) || /\.(heic|heif)$/i.test(file.name);
}

export async function decode(file, ctx) {
  try {
    const img = await decodeNative(file);
    if ((img.naturalWidth || img.width) > 0) return img;
  } catch (e) { /* try HEIC below */ }
  if (!isHeic(file)) throw new UserError("این فایل به‌عنوان تصویر خوانده نشد.");
  if (ctx) ctx.status("در حال آماده‌سازی خوانندهٔ HEIC (بار اول حدود ۱٫۳ مگابایت)…");
  await loadScript(VENDOR + "heic2any/heic2any.min.js");
  if (ctx) ctx.status("در حال باز کردن HEIC…");
  let out;
  try {
    out = await window.heic2any({ blob: file, toType: "image/png" });
  } catch (e) {
    throw new UserError("این فایل HEIC خوانده نشد.");
  }
  if (Array.isArray(out)) out = out[0];
  return decodeNative(out);
}

function dims(src) {
  return { w: src.naturalWidth || src.width, h: src.naturalHeight || src.height };
}

// Draws the image at its output size. opaque: fill white first (JPEG/PDF have no transparency).
function render(src, opt, opaque, extra) {
  const { w: w0, h: h0 } = dims(src);
  let k = 1, scaled = false;
  const maxEdge = Number(opt.maxEdge) || 0;
  if (maxEdge > 0 && Math.max(w0, h0) > maxEdge) k = maxEdge / Math.max(w0, h0);
  k *= extra || 1;
  if (w0 * h0 * k * k > SAFE_PIXELS) { k = Math.sqrt(SAFE_PIXELS / (w0 * h0)); scaled = true; }
  const w = Math.max(1, Math.round(w0 * k)), h = Math.max(1, Math.round(h0 * k));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const g = canvas.getContext("2d");
  if (!g) throw new UserError("حافظهٔ مرورگر برای این تصویر کافی نیست.");
  if (opaque) { g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); }
  g.imageSmoothingEnabled = true;
  g.imageSmoothingQuality = "high";
  g.drawImage(src, 0, 0, w, h);
  if (opt.gray) {
    const d = g.getImageData(0, 0, w, h), p = d.data;
    for (let i = 0; i < p.length; i += 4) {
      const y = Math.round(0.2126 * p[i] + 0.7152 * p[i + 1] + 0.0722 * p[i + 2]);
      p[i] = p[i + 1] = p[i + 2] = y;
    }
    g.putImageData(d, 0, 0);
  }
  return { canvas, scaled };
}
function free(canvas) { canvas.width = canvas.height = 0; }

async function encode(canvas, fmt, q, strong) {
  if (fmt === "avif" || (strong && (fmt === "jpeg" || fmt === "png"))) {
    const image = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height);
    const buf = await workerCall(fmt, image, { quality: Math.max(1, Math.min(100, Math.round(q * 100))) });
    return new Blob([buf], { type: MIME[fmt] });
  }
  const blob = await new Promise((r) => canvas.toBlob(r, MIME[fmt], q));
  if (!blob || blob.type !== MIME[fmt]) {
    throw new UserError(fmt === "webp" ? "این مرورگر نمی‌تواند WebP بسازد؛ AVIF یا JPEG را انتخاب کنید." : "مرورگر نتوانست این فرمت را بسازد.");
  }
  return blob;
}

// Highest quality (at most the slider value) whose file fits in targetBytes; shrinks the image if even 5% is too big.
async function encodeToTarget(src, opt, fmt, strong, targetBytes, ctx) {
  let extra = 1, smallest = null;
  for (let round = 0; round < 6; round++) {
    const { canvas } = render(src, opt, fmt === "jpeg", extra);
    try {
      let lo = 5, hi = Math.max(5, Math.min(95, Number(opt.quality) || 85)), found = null;
      for (let i = 0; i < 8 && lo <= hi; i++) {
        if (ctx.isCancelled()) throw cancelled();
        const q = i === 0 ? hi : Math.round((lo + hi) / 2);
        ctx.status("جست‌وجوی کیفیت مناسب… " + fa(q) + "٪");
        const b = await encode(canvas, fmt, q / 100, strong);
        if (!smallest || b.size < smallest.blob.size) smallest = { blob: b, q };
        if (b.size <= targetBytes) {
          found = { blob: b, q };
          if (i === 0) break;
          lo = q + 1;
        } else {
          hi = q - 1;
        }
      }
      if (found) {
        return {
          blob: found.blob,
          note: "کیفیت " + fa(found.q) + "٪" + (extra < 1 ? "، ابعاد " + fa(canvas.width) + "×" + fa(canvas.height) : "")
        };
      }
    } finally { free(canvas); }
    extra *= 0.75;
  }
  return { blob: smallest.blob, note: "به حجم هدف نرسید؛ کوچک‌ترین نتیجه" };
}

function formatOf(file) {
  const e = extOf(file.name), t = file.type;
  if (/jpe?g/.test(t) || /^(jpe?g|jfif)$/.test(e)) return "jpeg";
  if (/png/.test(t) || e === "png") return "png";
  if (/webp/.test(t) || e === "webp") return "webp";
  if (/avif/.test(t) || e === "avif") return "avif";
  return null;
}

export async function run(item, opt, ctx, mode) {
  const file = item.file;
  let fmt, strong;
  const inFmt = formatOf(file);
  if (mode === "compress") {
    fmt = opt.target === "same" ? (inFmt === "webp" && !webpOk ? "jpeg" : inFmt || "jpeg") : opt.target;
    strong = true;
  } else {
    fmt = opt.target;
    strong = !!opt.strong;
  }
  if (!MIME[fmt]) throw new UserError("فرمت خروجی نامعتبر است.");
  ctx.status("در حال باز کردن…");
  const src = await decode(file, ctx);
  try {
    let blob, note = "";
    const targetKB = Number(opt.targetKB) || 0;
    if (fmt !== "png" && targetKB > 0) {
      const r = await encodeToTarget(src, opt, fmt, strong, targetKB * 1024, ctx);
      blob = r.blob; note = r.note;
    } else {
      const r = render(src, opt, fmt === "jpeg", 1);
      ctx.status(fmt === "avif" ? "در حال ساخت AVIF (چند ثانیه)…" : strong ? "در حال فشرده‌سازی…" : "در حال تبدیل…");
      try { blob = await encode(r.canvas, fmt, (Number(opt.quality) || 85) / 100, strong); } finally { free(r.canvas); }
      if (r.scaled) note = "کوچک‌شده برای مرورگر";
      if (fmt === "png" && targetKB > 0) note = "PNG بدون افت است؛ حجم هدف اعمال نشد";
    }
    const base = baseName(file.name);
    if (mode === "compress" && blob.size >= file.size && fmt === inFmt && !(Number(opt.maxEdge) > 0) && !opt.gray) {
      return { outputs: [{ blob: file, name: file.name }], note: "کوچک‌تر نشد؛ فایل اصلی نگه داشته شد" };
    }
    if (mode === "compress" && /gif/i.test(file.type)) note = (note ? note + "، " : "") + "فقط فریم اول";
    return { outputs: [{ blob, name: base + (mode === "compress" ? "-small." : ".") + EXT[fmt] }], note };
  } finally {
    if (src.close) src.close();
  }
}

// All images (in list order) -> one PDF, one page per image, long side 842 pt (A4 height).
export async function toPdf(items, opt, ctx) {
  ctx.status("در حال آماده‌سازی PDF…");
  const { PDFDocument } = await import(VENDOR + "pdf-lib/pdf-lib.js");
  const doc = await PDFDocument.create();
  doc.setProducer("PixNexa Web");
  doc.setCreator("PixNexa Web");
  let pages = 0;
  for (let i = 0; i < items.length; i++) {
    if (ctx.isCancelled()) throw cancelled();
    const it = items[i];
    ctx.status("تصویر " + fa(i + 1) + " از " + fa(items.length));
    ctx.progress(i / items.length);
    ctx.member(it, "working");
    try {
      const src = await decode(it.file, ctx);
      const { canvas } = render(src, opt, true, 1);
      if (src.close) src.close();
      const blob = await encode(canvas, "jpeg", (Number(opt.quality) || 85) / 100, false);
      const w = canvas.width, h = canvas.height;
      free(canvas);
      const img = await doc.embedJpg(new Uint8Array(await blob.arrayBuffer()));
      const k = 842 / Math.max(w, h);
      const page = doc.addPage([w * k, h * k]);
      page.drawImage(img, { x: 0, y: 0, width: w * k, height: h * k });
      pages++;
      ctx.member(it, "done");
    } catch (e) {
      if (e && e.cancelled) throw e;
      ctx.member(it, "failed", e && e.user ? e.message : "این فایل به‌عنوان تصویر خوانده نشد.");
    }
  }
  if (!pages) throw new UserError("هیچ تصویری خوانده نشد.");
  ctx.status("در حال ذخیرهٔ PDF…");
  const bytes = await doc.save();
  return { outputs: [{ blob: new Blob([bytes], { type: "application/pdf" }), name: "PixNexa-images.pdf" }], note: fa(pages) + " صفحه" };
}
