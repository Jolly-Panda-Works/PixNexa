// Archives with fflate: extract ZIP, TAR, TAR.GZ and GZ; build ZIP files (also "download all").
import { VENDOR, baseName, extOf, UserError, fa } from "./util.js";

let fP;
const fflate = () => (fP = fP || import(VENDOR + "fflate/fflate.js"));

// Already-compressed formats are stored as-is; deflating them again only costs time.
const STORED = /\.(jpe?g|png|webp|avif|gif|heic|heif|mp4|m4v|mov|mkv|webm|mp3|m4a|aac|ogg|opus|flac|zip|gz|tgz|7z|rar|xz|bz2|pdf|docx|xlsx|pptx|woff2?)$/i;

function uniqueNames(entries) {
  const used = {};
  return entries.map((e) => {
    let name = e.name.replace(/^\/+/, "") || "file", n = 1;
    const dot = name.lastIndexOf("."), base = dot > 0 ? name.slice(0, dot) : name, ext = dot > 0 ? name.slice(dot) : "";
    while (used[name.toLowerCase()]) name = base + " (" + n++ + ")" + ext;
    used[name.toLowerCase()] = true;
    return { name, blob: e.blob };
  });
}

// entries: [{name, blob}] -> Blob (application/zip). level: null = automatic per file.
export async function makeZip(entries, level) {
  const { zip } = await fflate();
  const data = {};
  const list = uniqueNames(entries);
  for (const e of list) {
    const bytes = new Uint8Array(await e.blob.arrayBuffer());
    data[e.name] = [bytes, { level: level != null ? level : STORED.test(e.name) ? 0 : 6 }];
  }
  return new Promise((resolve, reject) => {
    zip(data, { mtime: new Date() }, (err, out) => (err ? reject(err) : resolve(new Blob([out], { type: "application/zip" }))));
  });
}

function readTar(buf) {
  const out = [], dec = new TextDecoder();
  const str = (o, n) => dec.decode(buf.subarray(o, o + n)).replace(/\0.*$/s, "");
  let off = 0, longName = null;
  while (off + 512 <= buf.length) {
    if (buf[off] === 0) break;
    const size = parseInt(str(off + 124, 12).trim() || "0", 8) || 0;
    const type = String.fromCharCode(buf[off + 156] || 48);
    let name = str(off, 100);
    if (str(off + 257, 5) === "ustar") { const pre = str(off + 345, 155); if (pre) name = pre + "/" + name; }
    const body = buf.subarray(off + 512, off + 512 + size);
    if (type === "x") {
      const m = /\d+ path=([^\n]*)\n/.exec(dec.decode(body));
      if (m) longName = m[1];
    } else if (type === "L") {
      longName = dec.decode(body).replace(/\0.*$/s, "");
    } else if (type === "0" || type === "\0" || type === "7") {
      out.push({ name: longName || name, blob: new Blob([body.slice()]) });
      longName = null;
    } else {
      longName = null;
    }
    off += 512 + Math.ceil(size / 512) * 512;
  }
  return out;
}

async function extract(file) {
  const { unzipSync, gunzipSync, strFromU8 } = await fflate();
  const buf = new Uint8Array(await file.arrayBuffer());
  const isZip = buf[0] === 0x50 && buf[1] === 0x4B;
  const isGz = buf[0] === 0x1F && buf[1] === 0x8B;
  const isTar = (b) => b.length > 262 && strFromU8(b.subarray(257, 262), true) === "ustar";
  if (isZip) {
    let files;
    try { files = unzipSync(buf); } catch (e) { throw new UserError("این ZIP باز نشد (شاید خراب یا رمزدار باشد)."); }
    return Object.keys(files).filter((n) => !/\/$/.test(n)).map((n) => ({ name: n, blob: new Blob([files[n]]) }));
  }
  if (isGz) {
    let raw;
    try { raw = gunzipSync(buf); } catch (e) { throw new UserError("این فایل GZ باز نشد."); }
    if (isTar(raw)) return readTar(raw);
    return [{ name: file.name.replace(/\.gz$/i, "") || baseName(file.name), blob: new Blob([raw]) }];
  }
  if (isTar(buf)) return readTar(buf);
  throw new UserError("فقط ZIP، TAR، TAR.GZ و GZ باز می‌شوند.");
}

export async function run(item, opt, ctx, mode) {
  const file = item.file;
  ctx.status("در حال باز کردن…");
  const entries = await extract(file);
  if (!entries.length) throw new UserError("این فایل فشرده خالی است.");
  if (mode === "compress") {
    ctx.status("در حال فشرده‌سازی دوباره…");
    const blob = await makeZip(entries, 9);
    const name = baseName(file.name.replace(/\.tar\.gz$/i, ".tgz")) + (extOf(file.name) === "zip" ? "-small.zip" : ".zip");
    if (blob.size >= file.size && extOf(file.name) === "zip") {
      return { outputs: [{ blob: file, name: file.name }], note: "کوچک‌تر نشد؛ فایل اصلی نگه داشته شد" };
    }
    return { outputs: [{ blob, name }], note: fa(entries.length) + " فایل" };
  }
  return { outputs: entries, note: "" };
}
