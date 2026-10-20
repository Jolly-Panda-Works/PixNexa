// Small helpers shared by the PixNexa Web engines. Everything here runs locally in the browser.
export const VENDOR = new URL("../vendor/", import.meta.url).href;

const scripts = {};
// Loads a classic (UMD) script once, e.g. heic2any or the ffmpeg.wasm wrapper.
export function loadScript(src) {
  if (!scripts[src]) {
    scripts[src] = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => { delete scripts[src]; reject(new Error("load " + src)); };
      document.head.appendChild(s);
    });
  }
  return scripts[src];
}

export function baseName(name) {
  return (name.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "") || "file").trim() || "file";
}

export function extOf(name) {
  const m = /\.([^./\\]+)$/.exec(name);
  return m ? m[1].toLowerCase() : "";
}

// Reads text as UTF-8; old Persian/Arabic subtitle and CSV files are often Windows-1256.
// persian: in Windows-1256 files, Arabic yeh/kaf are turned into the Persian letters.
export async function readText(file, persian) {
  const buf = new Uint8Array(await file.arrayBuffer());
  if (buf[0] === 0xFF && buf[1] === 0xFE) return new TextDecoder("utf-16le").decode(buf.subarray(2));
  if (buf[0] === 0xFE && buf[1] === 0xFF) return new TextDecoder("utf-16be").decode(buf.subarray(2));
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buf).replace(/^\uFEFF/, "");
  } catch (e) {
    try {
      const t = new TextDecoder("windows-1256").decode(buf);
      return persian ? t.replace(/\u064A/g, "\u06CC").replace(/\u0643/g, "\u06A9") : t;
    } catch (e2) { return new TextDecoder().decode(buf); }
  }
}

export function textBlob(text, type) {
  return new Blob([text], { type: (type || "text/plain") + ";charset=utf-8" });
}

// An error whose message is shown to the user as-is (Persian).
export class UserError extends Error {
  constructor(message) { super(message); this.user = true; }
}

export function cancelled() {
  const e = new Error("cancelled");
  e.cancelled = true;
  return e;
}

// Persian digits, e.g. fa(12.5) -> "۱۲٫۵".
export function fa(n) {
  return String(n).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]).replace(".", "٫");
}
