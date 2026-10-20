// Module worker for the heavier image codecs (jSquash: MozJPEG, OxiPNG, AVIF).
// The single-threaded wasm builds are used, because GitHub Pages cannot enable SharedArrayBuffer.
const V = new URL("../vendor/jsquash/", import.meta.url).href;
const mods = {};
function mod(name, path) {
  if (!mods[name]) mods[name] = import(V + path);
  return mods[name];
}

self.onmessage = async (e) => {
  const { id, op, image, options } = e.data;
  try {
    let out;
    if (op === "jpeg") {
      const m = await mod("jpeg", "jpeg/encode.js");
      out = await m.default(image, { quality: options.quality, progressive: true, optimize_coding: true });
    } else if (op === "png") {
      const m = await mod("oxipng", "oxipng/optimise.js");
      out = await m.default(image, { level: options.level || 2, interlace: false, optimiseAlpha: true });
    } else if (op === "avif") {
      const m = await mod("avif", "avif/encode.js");
      out = await m.default(image, { quality: options.quality, speed: options.speed || 8 });
    } else {
      throw new Error("unknown op " + op);
    }
    self.postMessage({ id, ok: true, buf: out }, [out]);
  } catch (err) {
    self.postMessage({ id, ok: false, error: String((err && err.message) || err) });
  }
};
