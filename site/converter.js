// PixNexa Web: converts images inside the browser with <canvas>. Nothing is uploaded.
(function () {
  "use strict";

  var FORMATS = {
    "image/jpeg": { ext: "jpg", lossy: true },
    "image/png": { ext: "png", lossy: false },
    "image/webp": { ext: "webp", lossy: true }
  };
  // Safari limits a canvas to about 16.7 million pixels; bigger images are scaled down only if needed.
  var SAFE_PIXELS = 16777216;

  var $ = function (id) { return document.getElementById(id); };
  var drop = $("drop"), picker = $("picker"), list = $("files"), summary = $("summary");
  var convertBtn = $("convertBtn"), zipBtn = $("zipBtn"), clearBtn = $("clearBtn");
  var quality = $("quality"), qualityValue = $("qualityValue"), qualityField = $("qualityField"), hint = $("hint");
  var formatButtons = Array.prototype.slice.call(document.querySelectorAll("#formats button"));
  if (!drop) return;

  var items = [];      // { id, file, row, result: {blob, name} | null }
  var nextId = 0;
  var busy = false;
  var format = load("format", "image/webp");
  var webpOk = canEncode("image/webp");

  // ---------- helpers ----------
  function load(key, fallback) {
    try { return localStorage.getItem("pixnexa." + key) || fallback; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem("pixnexa." + key, value); } catch (e) { /* private mode */ }
  }
  function fa(n) { return String(n).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }).replace(".", "٫"); }
  function size(bytes) {
    if (bytes < 1024) return fa(bytes) + " بایت";
    if (bytes < 1048576) return fa(Math.round(bytes / 1024)) + " کیلوبایت";
    return fa((bytes / 1048576).toFixed(1)) + " مگابایت";
  }
  function canEncode(type) {
    try {
      var c = document.createElement("canvas");
      c.width = c.height = 1;
      return c.toDataURL(type).indexOf("data:" + type) === 0;
    } catch (e) { return false; }
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function outName(file) {
    var base = file.name.replace(/\.[^./\\]+$/, "") || "image";
    return base + "." + FORMATS[format].ext;
  }

  // ---------- format / quality ----------
  if (!webpOk && format === "image/webp") format = "image/jpeg";
  quality.value = load("quality", "85");

  function renderControls() {
    formatButtons.forEach(function (b) {
      var f = b.getAttribute("data-format");
      var on = f === format;
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.disabled = busy || (f === "image/webp" && !webpOk);
    });
    qualityField.hidden = !FORMATS[format].lossy;
    quality.disabled = busy;
    qualityValue.textContent = "٪" + fa(quality.value);
    hint.textContent = !webpOk
      ? "این مرورگر نمی‌تواند WebP بسازد؛ برای WebP از کروم، اج یا فایرفاکس استفاده کنید."
      : format === "image/png" ? "PNG بدون افت کیفیت است و تنظیم کیفیت ندارد."
      : format === "image/jpeg" ? "JPEG شفافیت ندارد؛ بخش‌های شفاف سفید می‌شوند." : "";
    convertBtn.disabled = busy || items.length === 0;
    convertBtn.textContent = busy ? "در حال تبدیل…" : items.length ? "تبدیل " + fa(items.length) + " تصویر" : "تبدیل";
    var done = items.filter(function (it) { return it.result; });
    zipBtn.hidden = busy || done.length < 2;
    clearBtn.hidden = busy || items.length === 0;
  }

  formatButtons.forEach(function (b) {
    b.addEventListener("click", function () {
      format = b.getAttribute("data-format");
      save("format", format);
      renderControls();
    });
  });
  quality.addEventListener("input", renderControls);
  quality.addEventListener("change", function () { save("quality", quality.value); });

  // ---------- adding files ----------
  function addFiles(files) {
    Array.prototype.forEach.call(files, function (file) {
      if (!/^image\//.test(file.type) && !/\.(png|jpe?g|webp|gif|bmp|avif|ico|svg)$/i.test(file.name)) return;
      var item = { id: nextId++, file: file, result: null };
      item.row = buildRow(item);
      items.push(item);
      list.appendChild(item.row.li);
    });
    summary.hidden = true;
    renderControls();
  }

  function buildRow(item) {
    var li = el("li", "file");
    var thumb = el("img", "thumb");
    thumb.alt = "";
    thumb.src = URL.createObjectURL(item.file);
    thumb.onerror = function () { thumb.style.visibility = "hidden"; };
    var info = el("div", "info");
    var name = el("b", "name", item.file.name);
    var status = el("small", "status", size(item.file.size));
    var bar = el("span", "progress");
    info.appendChild(name);
    info.appendChild(status);
    info.appendChild(bar);
    var action = el("button", "icon-btn", "✕");
    action.type = "button";
    action.title = "حذف";
    action.addEventListener("click", function () {
      if (item.result) { download(item.result.blob, item.result.name); return; }
      if (busy) return;
      URL.revokeObjectURL(thumb.src);
      li.remove();
      items = items.filter(function (it) { return it !== item; });
      renderControls();
    });
    li.appendChild(thumb);
    li.appendChild(info);
    li.appendChild(action);
    return { li: li, status: status, bar: bar, action: action };
  }

  picker.addEventListener("change", function () { addFiles(picker.files); picker.value = ""; });
  drop.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); picker.click(); }
  });
  ["dragenter", "dragover"].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (e) { if (e.dataTransfer) addFiles(e.dataTransfer.files); });
  document.addEventListener("paste", function (e) {
    if (e.clipboardData && e.clipboardData.files.length) addFiles(e.clipboardData.files);
  });

  // ---------- converting ----------
  function decode(file) {
    if (window.createImageBitmap) {
      return createImageBitmap(file, { imageOrientation: "from-image" }).catch(function () { return decodeWithImg(file); });
    }
    return decodeWithImg(file);
  }
  function decodeWithImg(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("decode")); };
      img.src = url;
    });
  }
  function encode(source, w, h, type, q) {
    return new Promise(function (resolve) {
      var canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      var ctx = canvas.getContext("2d");
      if (!ctx) { resolve(null); return; }
      if (type === "image/jpeg") { ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h); }
      ctx.drawImage(source, 0, 0, w, h);
      canvas.toBlob(function (blob) {
        canvas.width = canvas.height = 0;   // free the memory right away
        resolve(blob);
      }, type, q);
    });
  }

  function convertOne(item, type, q) {
    return decode(item.file).then(function (img) {
      var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      if (!w || !h) throw new Error("decode");
      return encode(img, w, h, type, q).then(function (blob) {
        if (blob || w * h <= SAFE_PIXELS) return { blob: blob, scaled: false };
        var k = Math.sqrt(SAFE_PIXELS / (w * h));
        return encode(img, Math.floor(w * k), Math.floor(h * k), type, q).then(function (b) { return { blob: b, scaled: true }; });
      }).then(function (r) {
        if (img.close) img.close();
        if (!r.blob || r.blob.type !== type) throw new Error("encode");
        return r;
      });
    });
  }

  convertBtn.addEventListener("click", function () {
    if (busy || !items.length) return;
    busy = true;
    var type = format, q = Number(quality.value) / 100;
    items.forEach(function (it) {
      it.result = null;
      it.row.li.className = "file";
      it.row.status.textContent = "در انتظار";
      it.row.action.textContent = "✕";
      it.row.action.title = "حذف";
    });
    summary.hidden = true;
    renderControls();

    var queue = items.slice();
    (function next() {
      var item = queue.shift();
      if (!item) { busy = false; renderControls(); showSummary(); return; }
      item.row.li.className = "file working";
      item.row.status.textContent = "در حال تبدیل…";
      // Let the browser paint the progress state before the heavy work starts.
      setTimeout(function () {
        convertOne(item, type, q).then(function (r) {
          item.result = { blob: r.blob, name: outName(item.file) };
          var before = item.file.size, after = r.blob.size;
          var pct = before ? Math.round((after - before) * 100 / before) : 0;
          item.row.li.className = "file done";
          item.row.status.textContent = size(before) + " ← " + size(after);
          var badge = el("em", pct <= 0 ? "down" : "up", fa(Math.abs(pct)) + "٪ " + (pct <= 0 ? "کمتر" : "بیشتر"));
          item.row.status.appendChild(badge);
          if (r.scaled) item.row.status.appendChild(el("span", "note", " (کوچک‌شده برای مرورگر)"));
          item.row.action.textContent = "↓";
          item.row.action.title = "دانلود " + item.result.name;
        }).catch(function (e) {
          item.row.li.className = "file failed";
          item.row.status.textContent = e && e.message === "encode"
            ? "مرورگر نتوانست این فرمت را بسازد."
            : "این فایل به‌عنوان تصویر خوانده نشد.";
        }).then(next);
      }, 30);
    })();
  });

  function showSummary() {
    var done = items.filter(function (it) { return it.result; });
    var failed = items.length - done.length;
    if (!done.length) { summary.hidden = true; return; }
    var before = 0, after = 0;
    done.forEach(function (it) { before += it.file.size; after += it.result.blob.size; });
    summary.textContent = "✓ " + fa(done.length) + " تصویر تبدیل شد، " + size(before) + " ← " + size(after) +
      (failed ? "، " + fa(failed) + " ناموفق" : "") + ". برای دانلود هر فایل روی ↓ بزنید.";
    summary.hidden = false;
    if (done.length === 1) download(done[0].result.blob, done[0].result.name);
  }

  function download(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
  }

  clearBtn.addEventListener("click", function () {
    if (busy) return;
    items.forEach(function (it) { URL.revokeObjectURL(it.row.li.querySelector("img").src); });
    items = [];
    list.textContent = "";
    summary.hidden = true;
    renderControls();
  });

  // ---------- ZIP (stored, no compression: images are already compressed) ----------
  var CRC_TABLE = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(bytes) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }
  function makeZip(entries) {   // entries: [{name, data: Uint8Array}]
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    var now = new Date();
    var time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    var date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    entries.forEach(function (e) {
      var name = enc.encode(e.name), crc = crc32(e.data), len = e.data.length;
      var local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true);
      local.setUint16(8, 0, true); local.setUint16(10, time, true); local.setUint16(12, date, true);
      local.setUint32(14, crc, true); local.setUint32(18, len, true); local.setUint32(22, len, true);
      local.setUint16(26, name.length, true); local.setUint16(28, 0, true);
      parts.push(local.buffer, name, e.data);
      var cen = new DataView(new ArrayBuffer(46));
      cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true);
      cen.setUint16(8, 0x0800, true); cen.setUint16(10, 0, true); cen.setUint16(12, time, true);
      cen.setUint16(14, date, true); cen.setUint32(16, crc, true); cen.setUint32(20, len, true);
      cen.setUint32(24, len, true); cen.setUint16(28, name.length, true);
      cen.setUint32(42, offset, true);
      central.push(cen.buffer, name);
      offset += 30 + name.length + len;
    });
    var centralSize = central.reduce(function (s, p) { return s + p.byteLength; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
    end.setUint32(12, centralSize, true); end.setUint32(16, offset, true);
    return new Blob(parts.concat(central, [end.buffer]), { type: "application/zip" });
  }

  zipBtn.addEventListener("click", function () {
    var done = items.filter(function (it) { return it.result; });
    var used = {};
    Promise.all(done.map(function (it) {
      var name = it.result.name, base = name.replace(/\.[^.]+$/, ""), ext = name.slice(base.length), n = 1;
      while (used[name.toLowerCase()]) name = base + " (" + n++ + ")" + ext;
      used[name.toLowerCase()] = true;
      return it.result.blob.arrayBuffer().then(function (buf) { return { name: name, data: new Uint8Array(buf) }; });
    })).then(function (entries) { download(makeZip(entries), "PixNexa.zip"); });
  });

  renderControls();
})();
