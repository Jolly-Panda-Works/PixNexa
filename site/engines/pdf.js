// PDF: merge, split, page ranges (pdf-lib); pages -> PNG/JPEG, PDF -> TXT (pdf.js);
// compress by re-rendering each page as a JPEG and rebuilding the file with pdf-lib.
import { VENDOR, baseName, UserError, cancelled, fa, textBlob } from "./util.js";

let libP, jsP;
function lib() {
  if (!libP) libP = import(VENDOR + "pdf-lib/pdf-lib.js");
  return libP;
}
function pdfjs() {
  if (!jsP) {
    jsP = import(VENDOR + "pdfjs/pdf.min.js").then((m) => {
      m.GlobalWorkerOptions.workerSrc = VENDOR + "pdfjs/pdf.worker.min.js";
      return m;
    });
  }
  return jsP;
}

async function bytesOf(file) { return new Uint8Array(await file.arrayBuffer()); }

async function loadLib(file) {
  const { PDFDocument } = await lib();
  try {
    return await PDFDocument.load(await bytesOf(file), { ignoreEncryption: true });
  } catch (e) {
    throw new UserError("این PDF خوانده نشد (شاید خراب یا رمزدار باشد).");
  }
}
async function loadJs(file) {
  const m = await pdfjs();
  try {
    return await m.getDocument({ data: await bytesOf(file), isEvalSupported: false }).promise;
  } catch (e) {
    if (e && e.name === "PasswordException") throw new UserError("این PDF رمز دارد و باز نمی‌شود.");
    throw new UserError("این PDF خوانده نشد.");
  }
}

// "1-3, 5, 8-" -> [0,1,2,4,7,...]. Empty = all pages.
export function parseRange(text, count) {
  const s = String(text || "").replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٬،]/g, ",").replace(/[–—]/g, "-").trim();
  if (!s) return Array.from({ length: count }, (_, i) => i);
  const out = [], seen = {};
  s.split(/[,\s]+/).filter(Boolean).forEach((part) => {
    const m = /^(\d*)-(\d*)$/.exec(part);
    let a, b;
    if (m) { a = m[1] ? +m[1] : 1; b = m[2] ? +m[2] : count; }
    else if (/^\d+$/.test(part)) { a = b = +part; }
    else throw new UserError("بازهٔ صفحه نامعتبر است؛ مثلاً 1-3,5 بنویسید.");
    for (let p = Math.max(1, a); p <= Math.min(count, b); p++) if (!seen[p]) { seen[p] = 1; out.push(p - 1); }
  });
  if (!out.length) throw new UserError("این PDF " + fa(count) + " صفحه دارد؛ بازهٔ صفحه را درست کنید.");
  return out;
}

function pad(n, total) { return String(n).padStart(String(total).length, "0"); }

async function savePdf(doc) {
  doc.setProducer("PixNexa Web");
  return new Blob([await doc.save()], { type: "application/pdf" });
}

async function renderPage(page, scale) {
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.floor(viewport.width));
  canvas.height = Math.max(1, Math.floor(viewport.height));
  const g = canvas.getContext("2d");
  g.fillStyle = "#fff";
  g.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: g, viewport }).promise;
  return canvas;
}
function toBlob(canvas, type, q) {
  return new Promise((resolve, reject) => canvas.toBlob((b) => {
    canvas.width = canvas.height = 0;
    b ? resolve(b) : reject(new UserError("حافظهٔ مرورگر برای این صفحه کافی نیست."));
  }, type, q));
}

export async function merge(items, opt, ctx) {
  const { PDFDocument } = await lib();
  const out = await PDFDocument.create();
  let pages = 0;
  for (let i = 0; i < items.length; i++) {
    if (ctx.isCancelled()) throw cancelled();
    const it = items[i];
    ctx.status("فایل " + fa(i + 1) + " از " + fa(items.length));
    ctx.progress(i / items.length);
    ctx.member(it, "working");
    try {
      const src = await loadLib(it.file);
      const copied = await out.copyPages(src, src.getPageIndices());
      copied.forEach((p) => out.addPage(p));
      pages += copied.length;
      ctx.member(it, "done");
    } catch (e) {
      ctx.member(it, "failed", e && e.user ? e.message : "این PDF خوانده نشد.");
    }
  }
  if (!pages) throw new UserError("هیچ PDFی خوانده نشد.");
  ctx.status("در حال ذخیره…");
  return { outputs: [{ blob: await savePdf(out), name: "PixNexa-merged.pdf" }], note: fa(pages) + " صفحه" };
}

export async function run(item, opt, ctx, mode) {
  const file = item.file, base = baseName(file.name);
  const target = mode === "compress" ? "compress" : opt.target;

  if (target === "split" || target === "extract" || target === "merge") {
    const { PDFDocument } = await lib();
    ctx.status("در حال خواندن…");
    const src = await loadLib(file);
    const count = src.getPageCount();
    const pages = parseRange(opt.pages, count);
    if (target === "split") {
      const outputs = [];
      for (let i = 0; i < pages.length; i++) {
        if (ctx.isCancelled()) throw cancelled();
        ctx.status("صفحهٔ " + fa(pages[i] + 1) + " از " + fa(count));
        ctx.progress(i / pages.length);
        const doc = await PDFDocument.create();
        const [p] = await doc.copyPages(src, [pages[i]]);
        doc.addPage(p);
        outputs.push({ blob: await savePdf(doc), name: base + "-p" + pad(pages[i] + 1, count) + ".pdf" });
      }
      return { outputs, note: "" };
    }
    const doc = await PDFDocument.create();
    (await doc.copyPages(src, pages)).forEach((p) => doc.addPage(p));
    return { outputs: [{ blob: await savePdf(doc), name: base + "-pages.pdf" }], note: fa(pages.length) + " صفحه" };
  }

  ctx.status("در حال خواندن…");
  const pdf = await loadJs(file);
  try {
    const count = pdf.numPages;
    if (target === "compress") {
      const { PDFDocument } = await lib();
      const doc = await PDFDocument.create();
      const scale = (Number(opt.dpi) || 96) / 72, q = (Number(opt.quality) || 60) / 100;
      for (let n = 1; n <= count; n++) {
        if (ctx.isCancelled()) throw cancelled();
        ctx.status("صفحهٔ " + fa(n) + " از " + fa(count));
        ctx.progress((n - 1) / count);
        const page = await pdf.getPage(n);
        const size = page.getViewport({ scale: 1 });
        const blob = await toBlob(await renderPage(page, scale), "image/jpeg", q);
        page.cleanup();
        const img = await doc.embedJpg(new Uint8Array(await blob.arrayBuffer()));
        const out = doc.addPage([size.width, size.height]);
        out.drawImage(img, { x: 0, y: 0, width: size.width, height: size.height });
      }
      ctx.status("در حال ذخیره…");
      const blob = await savePdf(doc);
      if (blob.size >= file.size) {
        return { outputs: [{ blob: file, name: file.name }], note: "کوچک‌تر نشد؛ فایل اصلی نگه داشته شد" };
      }
      return { outputs: [{ blob, name: base + "-small.pdf" }], note: "متن دیگر قابل انتخاب نیست" };
    }

    const pages = parseRange(opt.pages, count);
    if (target === "txt") {
      const parts = [];
      for (let i = 0; i < pages.length; i++) {
        if (ctx.isCancelled()) throw cancelled();
        ctx.progress(i / pages.length);
        const page = await pdf.getPage(pages[i] + 1);
        const tc = await page.getTextContent();
        let s = "";
        tc.items.forEach((it) => { if ("str" in it) s += it.str + (it.hasEOL ? "\n" : ""); });
        parts.push(s.trim());
        page.cleanup();
      }
      const text = parts.join("\n\n\f");
      const note = text.replace(/\s/g, "") ? fa(pages.length) + " صفحه" : "متنی پیدا نشد (شاید PDF اسکن‌شده باشد)";
      return { outputs: [{ blob: textBlob(text + "\n"), name: base + ".txt" }], note };
    }

    // png / jpeg
    const type = target === "jpeg" ? "image/jpeg" : "image/png", ext = target === "jpeg" ? "jpg" : "png";
    const scale = Number(opt.scale) || 2, q = (Number(opt.quality) || 85) / 100;
    const outputs = [];
    for (let i = 0; i < pages.length; i++) {
      if (ctx.isCancelled()) throw cancelled();
      ctx.status("صفحهٔ " + fa(pages[i] + 1) + " از " + fa(count));
      ctx.progress(i / pages.length);
      const page = await pdf.getPage(pages[i] + 1);
      const blob = await toBlob(await renderPage(page, scale), type, q);
      page.cleanup();
      outputs.push({ blob, name: base + "-p" + pad(pages[i] + 1, count) + "." + ext });
    }
    return { outputs, note: outputs.length === 1 ? "صفحهٔ " + fa(pages[0] + 1) : "" };
  } finally {
    pdf.destroy();
  }
}
