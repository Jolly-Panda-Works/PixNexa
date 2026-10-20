// PixNexa Web: converts and compresses files inside the browser. Nothing is uploaded.
// The engines in engines/ (and the libraries in vendor/) are loaded only when their file type is used.
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var drop = $("drop"), picker = $("picker"), list = $("files"), summary = $("summary");
  var panelsEl = $("panels"), hint = $("hint"), notice = $("notice"), noticeText = $("noticeText"), noticeBar = $("noticeBar");
  var convertBtn = $("convertBtn"), cancelBtn = $("cancelBtn"), zipBtn = $("zipBtn"), packBtn = $("packBtn"), clearBtn = $("clearBtn");
  var modeButtons = Array.prototype.slice.call(document.querySelectorAll("#mode button"));
  if (!drop) return;

  // ---------- helpers ----------
  function fa(n) { return String(n).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }).replace(".", "٫"); }
  function size(bytes) {
    if (bytes < 1024) return fa(bytes) + " بایت";
    if (bytes < 1048576) return fa(Math.round(bytes / 1024)) + " کیلوبایت";
    if (bytes < 1073741824) return fa((bytes / 1048576).toFixed(1)) + " مگابایت";
    return fa((bytes / 1073741824).toFixed(2)) + " گیگابایت";
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function load(key, fallback) {
    try { var v = localStorage.getItem("pixnexa." + key); return v == null ? fallback : v; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem("pixnexa." + key, value); } catch (e) { /* private mode */ }
  }
  function extOf(name) { var m = /\.([^./\\]+)$/.exec(name); return m ? m[1].toLowerCase() : ""; }
  function baseName(name) { return name.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "") || "file"; }
  function canEncode(type) {
    try {
      var c = document.createElement("canvas");
      c.width = c.height = 1;
      return c.toDataURL(type).indexOf("data:" + type) === 0;
    } catch (e) { return false; }
  }
  var webpOk = canEncode("image/webp");

  // ---------- categories ----------
  var CATS = ["image", "pdf", "video", "audio", "data", "subtitle", "archive", "other"];
  var LABEL = { image: "تصویر", pdf: "PDF", video: "ویدیو", audio: "صدا", data: "داده", subtitle: "زیرنویس", archive: "فایل فشرده", other: "فایل‌های دیگر" };
  var ENGINE = { image: "image", pdf: "pdf", video: "media", audio: "media", data: "data", subtitle: "subtitle", archive: "archive" };
  var EXT_CAT = {};
  [["image", "png jpg jpeg jfif pjpeg webp gif bmp avif heic heif ico svg tif tiff"],
   ["pdf", "pdf"],
   ["video", "mp4 m4v mov mkv webm avi wmv flv mpeg mpg m2ts mts 3gp 3g2 ogv vob"],
   ["audio", "mp3 wav m4a aac ogg oga opus flac wma aif aiff amr weba"],
   ["data", "json yaml yml csv tsv xml toml"],
   ["subtitle", "srt vtt ass ssa"],
   ["archive", "zip tar gz tgz"]].forEach(function (p) {
    p[1].split(" ").forEach(function (e) { EXT_CAT[e] = p[0]; });
  });
  function categoryOf(file) {
    var e = extOf(file.name), t = file.type || "";
    if (EXT_CAT[e]) return EXT_CAT[e];
    if (/^image\//.test(t)) return "image";
    if (/^video\//.test(t)) return "video";
    if (/^audio\//.test(t)) return "audio";
    if (t === "application/pdf") return "pdf";
    return "other";
  }

  var engines = {};
  function engine(cat) {
    var name = ENGINE[cat];
    if (!engines[name]) {
      engines[name] = import("./engines/" + name + ".js").catch(function (e) {
        delete engines[name];
        var err = new Error("بارگذاری این بخش ناموفق بود؛ اتصال را بررسی کنید و دوباره امتحان کنید.");
        err.user = true;
        throw err;
      });
    }
    return engines[name];
  }

  // ---------- settings ----------
  var DEFAULTS = {
    convert: {
      image: { target: webpOk ? "webp" : "jpeg", quality: 85, targetKB: "", maxEdge: 0, gray: false, strong: false },
      pdf: { target: "png", pages: "", scale: 2, quality: 85 },
      video: { target: "mp4", gifWidth: 480, fps: 10, bitrate: 192 },
      audio: { target: "mp3", bitrate: 192 },
      data: { target: "json" },
      subtitle: { target: "srt" },
      archive: { target: "extract" },
      other: {}
    },
    compress: {
      image: { target: "same", quality: 75, targetKB: "", maxEdge: 0, gray: false },
      pdf: { quality: 60, dpi: 96 },
      video: { res: 720, crf: 28, abr: 96 },
      audio: { bitrate: 96, mono: false },
      data: {}, subtitle: {}, archive: {}, other: {}
    }
  };
  var settings = (function () {
    var s = {};
    try { s = JSON.parse(load("web.settings", "{}")) || {}; } catch (e) { s = {}; }
    ["convert", "compress"].forEach(function (m) {
      s[m] = s[m] || {};
      CATS.forEach(function (c) { s[m][c] = Object.assign({}, DEFAULTS[m][c], s[m][c] || {}); });
    });
    return s;
  })();
  var mode = load("web.mode", "convert") === "compress" ? "compress" : "convert";
  // Per-task values (target size, page range) are not remembered, so an old limit is never applied by surprise.
  var TRANSIENT = { targetKB: 1, pages: 1 };
  function saveSettings() {
    save("web.settings", JSON.stringify(settings, function (k, v) { return TRANSIENT[k] ? undefined : v; }));
  }

  var items = [];   // { id, file, cat, row, result: {outputs, before, note} | null }
  var groups = [];  // result rows made from several inputs (merged PDF, images -> PDF, ZIP of files)
  var nextId = 0, busy = false, cancelled = false;

  function count(cat) { return items.filter(function (it) { return it.cat === cat; }).length; }
  function presentCats() { return CATS.filter(function (c) { return count(c) > 0; }); }

  // What each category offers in each mode: targets, option fields and hints.
  function spec(cat) {
    var s = settings[mode][cat], n = count(cat), c = mode === "convert";
    var t = s.target, sp = { targets: null, fields: [], hints: [] };
    var Q = { type: "range", key: "quality", label: "کیفیت", min: 1, max: 100 };
    var BR = function (opts) {
      return { type: "select", key: "bitrate", label: "بیت‌ریت", options: opts.map(function (v) { return [v, fa(v) + " kbps"]; }) };
    };
    if (cat === "image") {
      sp.targets = c
        ? [["jpeg", "JPEG"], ["png", "PNG"], ["webp", "WebP", !webpOk], ["avif", "AVIF"], ["pdf", "PDF"]]
        : [["same", "همان فرمت"], ["jpeg", "JPEG"], ["webp", "WebP", !webpOk], ["avif", "AVIF"]];
      t = pick(sp.targets, s);
      if (t !== "png") sp.fields.push(Q);
      if (t !== "png" && t !== "pdf") sp.fields.push({ type: "number", key: "targetKB", label: "حجم هدف (کیلوبایت)", placeholder: "اختیاری" });
      sp.fields.push({ type: "select", key: "maxEdge", label: "بیشینهٔ ضلع بلند", options: [[0, "اندازهٔ اصلی"], [3840, "۳۸۴۰ px"], [2560, "۲۵۶۰ px"], [1920, "۱۹۲۰ px"], [1280, "۱۲۸۰ px"], [1024, "۱۰۲۴ px"], [800, "۸۰۰ px"], [512, "۵۱۲ px"]] });
      sp.fields.push({ type: "check", key: "gray", label: "سیاه‌وسفید" });
      if (c && (t === "jpeg" || t === "png")) sp.fields.push({ type: "check", key: "strong", label: t === "jpeg" ? "فشرده‌سازی قوی‌تر (MozJPEG)" : "فشرده‌سازی قوی‌تر (OxiPNG، کندتر)" });
      if (!webpOk) sp.hints.push("این مرورگر نمی‌تواند WebP بسازد؛ AVIF یا JPEG را انتخاب کنید.");
      if (t === "png") sp.hints.push("PNG بدون افت کیفیت است و تنظیم کیفیت ندارد.");
      if (t === "jpeg") sp.hints.push("JPEG شفافیت ندارد؛ بخش‌های شفاف سفید می‌شوند.");
      if (t === "avif") sp.hints.push("AVIF معمولاً کم‌حجم‌ترین نتیجه را می‌دهد، ولی ساختنش برای هر عکس چند ثانیه طول می‌کشد.");
      if (t === "pdf") sp.hints.push("همهٔ تصاویر به ترتیب فهرست در یک فایل PDF قرار می‌گیرند.");
      if (!c) sp.hints.push("JPEG با MozJPEG و PNG بدون افت با OxiPNG فشرده می‌شود. با «حجم هدف» بهترین کیفیتی پیدا می‌شود که در آن حجم جا شود. اگر فایلی کوچک‌تر نشد، همان فایل اصلی می‌ماند.");
    } else if (cat === "pdf") {
      if (c) {
        sp.targets = (n > 1 ? [["merge", "ادغام در یک PDF"]] : []).concat([["split", "جدا کردن صفحه‌ها"], ["extract", "استخراج صفحه‌ها"], ["png", "PNG"], ["jpeg", "JPEG"], ["txt", "متن (TXT)"]]);
        t = pick(sp.targets, s);
        if (t !== "merge") sp.fields.push({ type: "text", key: "pages", label: "صفحه‌ها", placeholder: "همه (مثلاً 1-3,5)" });
        if (t === "png" || t === "jpeg") sp.fields.push({ type: "select", key: "scale", label: "وضوح تصویر", options: [[1, "کم (۷۲ dpi)"], [1.5, "متوسط (۱۰۸ dpi)"], [2, "خوب (۱۴۴ dpi)"], [3, "زیاد (۲۱۶ dpi)"]] });
        if (t === "jpeg") sp.fields.push(Q);
        if (t === "merge") sp.hints.push("PDFها به ترتیب فهرست پشت سر هم قرار می‌گیرند.");
        if (t === "split") sp.hints.push("هر صفحه یک فایل PDF جدا می‌شود.");
        if (t === "extract") sp.hints.push("صفحه‌های انتخاب‌شده در یک PDF تازه ذخیره می‌شوند.");
        if (t === "txt") sp.hints.push("متن PDFهای اسکن‌شده (تصویری) خوانده نمی‌شود.");
      } else {
        sp.fields.push({ type: "range", key: "quality", label: "کیفیت تصویر صفحه‌ها", min: 10, max: 95 });
        sp.fields.push({ type: "select", key: "dpi", label: "وضوح", options: [[72, "۷۲ dpi (کم‌حجم‌ترین)"], [96, "۹۶ dpi"], [120, "۱۲۰ dpi"], [150, "۱۵۰ dpi (خواناتر)"]] });
        sp.hints.push("⚠ صفحه‌ها به تصویر JPEG تبدیل می‌شوند، پس متن دیگر قابل انتخاب و جست‌وجو نیست. برای PDFهای اسکن‌شده و پر از عکس بهترین نتیجه را می‌دهد.");
      }
    } else if (cat === "video") {
      if (c) {
        sp.targets = [["mp4", "MP4"], ["webm", "WebM"], ["mov", "MOV"], ["mkv", "MKV"], ["gif", "GIF"], ["mp3", "MP3 (صدا)"], ["m4a", "M4A (صدا)"], ["wav", "WAV (صدا)"]];
        t = pick(sp.targets, s);
        if (t === "gif") {
          sp.fields.push({ type: "select", key: "gifWidth", label: "عرض GIF", options: [[320, "۳۲۰ px"], [480, "۴۸۰ px"], [640, "۶۴۰ px"], [0, "اندازهٔ اصلی"]] });
          sp.fields.push({ type: "select", key: "fps", label: "فریم در ثانیه", options: [[8, "۸"], [10, "۱۰"], [15, "۱۵"]] });
          sp.hints.push("GIF برای کلیپ‌های چندثانیه‌ای مناسب است؛ ویدیوی بلند GIF بسیار حجیمی می‌سازد.");
        }
        if (t === "mp3" || t === "m4a") sp.fields.push(BR([128, 192, 256, 320]));
        if (t === "webm") sp.hints.push("ساخت WebM در مرورگر کند است؛ برای سرعت بیشتر MP4 را انتخاب کنید.");
        if (t === "mp4" || t === "mov" || t === "mkv") sp.hints.push("اگر ممکن باشد، ویدیو بدون فشرده‌سازی دوباره و در چند ثانیه منتقل می‌شود.");
      } else {
        sp.fields.push({ type: "select", key: "res", label: "وضوح", options: [[0, "اندازهٔ اصلی"], [1080, "1080p"], [720, "720p"], [480, "480p"], [360, "360p"]] });
        sp.fields.push({ type: "select", key: "crf", label: "کیفیت", options: [[23, "بالا"], [28, "متوسط"], [32, "حجم کم"]] });
        sp.fields.push({ type: "select", key: "abr", label: "کیفیت صدا", options: [[64, "۶۴ kbps"], [96, "۹۶ kbps"], [128, "۱۲۸ kbps"]] });
        sp.hints.push("خروجی MP4 (H.264) است.");
      }
    } else if (cat === "audio") {
      if (c) {
        sp.targets = [["mp3", "MP3"], ["m4a", "M4A"], ["ogg", "OGG"], ["wav", "WAV"], ["flac", "FLAC"]];
        t = pick(sp.targets, s);
        if (t === "mp3" || t === "m4a" || t === "ogg") sp.fields.push(BR([96, 128, 192, 256, 320]));
        if (t === "wav" || t === "flac") sp.hints.push("WAV و FLAC بدون افت‌اند و حجم بیشتری دارند.");
      } else {
        sp.fields.push(BR([48, 64, 96, 128]));
        sp.fields.push({ type: "check", key: "mono", label: "تک‌کاناله (مونو)" });
        sp.hints.push("MP3، M4A و OGG در همان فرمت می‌مانند؛ WAV و FLAC به MP3 تبدیل می‌شوند.");
      }
    } else if (cat === "data") {
      if (c) {
        sp.targets = [["json", "JSON"], ["yaml", "YAML"], ["csv", "CSV"], ["xml", "XML"], ["toml", "TOML"]];
        t = pick(sp.targets, s);
        if (t === "csv") sp.hints.push("CSV برای فهرستی از رکوردهاست؛ فیلدهای تودرتو با نام نقطه‌دار (a.b) می‌آیند.");
        if (t === "toml") sp.hints.push("TOML مقدار خالی (null) ندارد؛ این مقدارها حذف می‌شوند.");
      } else {
        sp.hints.push("JSON و XML بدون فاصله‌های اضافه ذخیره می‌شوند (minify). YAML، CSV و TOML را با «ساخت ZIP» فشرده کنید.");
      }
    } else if (cat === "subtitle") {
      if (c) {
        sp.targets = [["srt", "SRT"], ["vtt", "WebVTT"], ["ass", "ASS"]];
        t = pick(sp.targets, s);
        sp.hints.push("زیرنویس‌های قدیمی فارسی (Windows-1256) هم درست خوانده می‌شوند؛ خروجی UTF-8 است.");
      } else {
        sp.hints.push("زیرنویس‌ها کاهش حجم ندارند و در این حالت کنار گذاشته می‌شوند.");
      }
    } else if (cat === "archive") {
      if (c) {
        sp.targets = [["extract", "باز کردن (استخراج)"]];
        t = pick(sp.targets, s);
        sp.hints.push("ZIP، TAR، TAR.GZ و GZ. فایل‌های داخل را یکی‌یکی یا همه را با هم دانلود کنید.");
      } else {
        sp.hints.push("محتوای فایل با بیشترین فشرده‌سازی دوباره در یک ZIP ذخیره می‌شود.");
      }
    } else {
      sp.hints.push("این فایل‌ها تبدیل نمی‌شوند؛ با «ساخت ZIP» می‌توانید همهٔ فایل‌ها را در یک ZIP فشرده بگذارید.");
    }
    sp.target = t;
    return sp;
  }
  // Keeps the saved target if it is still offered, otherwise uses the first one.
  function pick(targets, s) {
    var ok = targets.filter(function (x) { return !x[2]; });
    if (!ok.some(function (x) { return x[0] === s.target; })) s.target = ok.length ? ok[0][0] : null;
    return s.target;
  }

  // ---------- controls ----------
  function renderPanels() {
    panelsEl.textContent = "";
    var cats = presentCats();
    panelsEl.hidden = cats.length === 0;
    cats.forEach(function (cat) {
      var s = settings[mode][cat], sp = spec(cat), n = count(cat);
      var panel = el("div", "panel");
      panel.setAttribute("data-cat", cat);
      var head = el("div", "panel-head");
      head.appendChild(el("b", null, LABEL[cat]));
      head.appendChild(el("small", null, fa(n) + " فایل"));
      panel.appendChild(head);
      if (sp.targets) {
        var row = el("div", "choice");
        row.setAttribute("role", "radiogroup");
        row.setAttribute("aria-label", "خروجی " + LABEL[cat]);
        sp.targets.forEach(function (x) {
          var b = el("button", x[0] === sp.target ? "on" : "", x[1]);
          b.type = "button";
          b.setAttribute("role", "radio");
          b.setAttribute("aria-checked", x[0] === sp.target ? "true" : "false");
          b.setAttribute("data-target", x[0]);
          b.disabled = !!x[2];
          b.addEventListener("click", function () {
            s.target = x[0];
            saveSettings();
            renderPanels();
          });
          row.appendChild(b);
        });
        panel.appendChild(row);
      }
      if (sp.fields.length) {
        var opts = el("div", "opts");
        sp.fields.forEach(function (f) { opts.appendChild(field(f, s)); });
        panel.appendChild(opts);
      }
      sp.hints.forEach(function (h) { panel.appendChild(el("p", "panel-hint", h)); });
      panelsEl.appendChild(panel);
    });
    renderHint();
  }

  function field(f, s) {
    if (f.type === "check") {
      var lab = el("label", "check");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!s[f.key];
      cb.setAttribute("data-key", f.key);
      cb.addEventListener("change", function () { s[f.key] = cb.checked; saveSettings(); });
      lab.appendChild(cb);
      lab.appendChild(el("span", null, f.label));
      return lab;
    }
    var wrap = el("label", "field");
    var label = el("span", "label", f.label);
    wrap.appendChild(label);
    var input;
    if (f.type === "range") {
      var val = el("b", null, "٪" + fa(s[f.key]));
      label.appendChild(val);
      input = document.createElement("input");
      input.type = "range";
      input.min = f.min; input.max = f.max; input.value = s[f.key];
      input.addEventListener("input", function () { s[f.key] = Number(input.value); val.textContent = "٪" + fa(input.value); });
      input.addEventListener("change", saveSettings);
      wrap.classList.add("wide");
    } else if (f.type === "select") {
      input = document.createElement("select");
      f.options.forEach(function (o) {
        var op = el("option", null, o[1]);
        op.value = o[0];
        if (String(o[0]) === String(s[f.key])) op.selected = true;
        input.appendChild(op);
      });
      input.addEventListener("change", function () {
        s[f.key] = isNaN(Number(input.value)) ? input.value : Number(input.value);
        saveSettings();
      });
    } else {
      input = document.createElement("input");
      input.type = f.type === "number" ? "number" : "text";
      if (f.type === "number") { input.min = "1"; input.inputMode = "numeric"; }
      input.dir = "ltr";
      input.placeholder = f.placeholder || "";
      input.value = s[f.key] == null ? "" : s[f.key];
      input.addEventListener("input", function () { s[f.key] = input.value.trim(); });
      input.addEventListener("change", saveSettings);
    }
    input.setAttribute("data-key", f.key);
    input.setAttribute("aria-label", f.label);
    wrap.appendChild(input);
    return wrap;
  }

  function renderHint() {
    var media = items.filter(function (it) { return it.cat === "video" || it.cat === "audio"; });
    var big = media.some(function (it) { return it.file.size > 300 * 1048576; });
    hint.textContent = media.length
      ? (big ? "⚠ بعضی فایل‌ها بزرگ‌اند و ممکن است حافظهٔ مرورگر کافی نباشد. " : "") +
        "ویدیو و صدا در مرورگر چند برابر کندتر از نسخهٔ ویندوز و اندروید پردازش می‌شوند و بار اول موتور ویدیو (حدود ۳۱ مگابایت) دانلود می‌شود. برای ویدیوهای بزرگ PixNexa Desktop یا Mobile سریع‌تر است."
      : "";
  }

  function allOutputs() {
    var out = [];
    items.concat(groups).forEach(function (x) { if (x.result) out = out.concat(x.result.outputs); });
    return out;
  }

  function renderControls() {
    modeButtons.forEach(function (b) {
      var on = b.getAttribute("data-mode") === mode;
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.disabled = busy;
    });
    panelsEl.disabled = busy;
    var verb = mode === "compress" ? "کاهش حجم" : "تبدیل";
    convertBtn.disabled = busy || items.length === 0;
    convertBtn.textContent = busy ? "در حال پردازش…" : items.length ? verb + " " + fa(items.length) + " فایل" : verb;
    cancelBtn.hidden = !busy;
    zipBtn.hidden = busy || allOutputs().length < 2;
    packBtn.hidden = busy || items.length === 0;
    clearBtn.hidden = busy || items.length === 0;
  }

  modeButtons.forEach(function (b) {
    b.addEventListener("click", function () {
      if (busy) return;
      mode = b.getAttribute("data-mode");
      save("web.mode", mode);
      renderPanels();
      renderControls();
    });
  });

  function showNotice(text, frac) {
    if (!text) { notice.hidden = true; return; }
    notice.hidden = false;
    noticeText.textContent = text + (frac != null && frac > 0 ? " " + fa(Math.round(frac * 100)) + "٪" : "");
    noticeBar.style.width = Math.round((frac || 0) * 100) + "%";
  }

  // ---------- file rows ----------
  function thumbFor(file, cat) {
    var tile = el("div", "thumb kind kind-" + cat, (extOf(file.name) || "?").slice(0, 4).toUpperCase());
    if (cat !== "image") return tile;
    var img = el("img", "thumb");
    img.alt = "";
    img.src = URL.createObjectURL(file);
    img.onerror = function () { URL.revokeObjectURL(img.src); if (img.parentNode) img.parentNode.replaceChild(tile, img); };
    return img;
  }

  function buildRow(file, cat, onAction) {
    var li = el("li", "file");
    var thumb = thumbFor(file, cat);
    var info = el("div", "info");
    var name = el("b", "name", file.name);
    name.title = file.name;
    var status = el("small", "status", size(file.size) + " · " + LABEL[cat]);
    var bar = el("span", "progress");
    var fill = el("i");
    bar.appendChild(fill);
    info.appendChild(name);
    info.appendChild(status);
    info.appendChild(bar);
    var action = el("button", "icon-btn", "✕");
    action.type = "button";
    action.title = "حذف";
    action.addEventListener("click", onAction);
    li.appendChild(thumb);
    li.appendChild(info);
    li.appendChild(action);
    return { li: li, thumb: thumb, info: info, status: status, bar: bar, fill: fill, action: action, outs: null };
  }

  function addFiles(files) {
    Array.prototype.forEach.call(files, function (file) {
      var item = { id: nextId++, file: file, cat: categoryOf(file), result: null };
      item.row = buildRow(file, item.cat, function () {
        if (item.result) { downloadResult(item.result); return; }
        if (busy) return;
        removeRow(item.row);
        items = items.filter(function (it) { return it !== item; });
        renderPanels();
        renderControls();
      });
      if (item.cat === "other") item.row.li.classList.add("muted");
      items.push(item);
      list.appendChild(item.row.li);
    });
    summary.hidden = true;
    renderPanels();
    renderControls();
  }
  function removeRow(row) {
    if (row.thumb.tagName === "IMG") URL.revokeObjectURL(row.thumb.src);
    row.li.remove();
  }

  function setRow(row, state, text) {
    row.li.className = "file" + (state ? " " + state : "");
    row.status.textContent = text;
    if (state !== "working") setProgress(row, null);
  }
  function setProgress(row, f) {
    if (f == null) { row.bar.classList.remove("det"); row.fill.style.width = ""; return; }
    row.bar.classList.add("det");
    row.fill.style.width = Math.max(2, Math.round(f * 100)) + "%";
  }
  function resetRow(it) {
    if (it.row.outs) { it.row.outs.remove(); it.row.outs = null; }
    setRow(it.row, it.cat === "other" ? "muted" : "", size(it.file.size) + " · " + LABEL[it.cat]);
    it.row.action.textContent = "✕";
    it.row.action.title = "حذف";
  }

  function showResult(row, result) {
    var outs = result.outputs, after = 0;
    outs.forEach(function (o) { after += o.blob.size; });
    var before = result.before;
    row.li.className = "file done";
    setProgress(row, null);
    row.status.textContent = (outs.length > 1 ? fa(outs.length) + " فایل · " : "") + size(before) + " ← " + size(after);
    var unchanged = outs.length === 1 && result.original;
    if (!unchanged && before) {
      var pct = Math.round((after - before) * 100 / before);
      row.status.appendChild(el("em", pct <= 0 ? "down" : "up", fa(Math.abs(pct)) + "٪ " + (pct <= 0 ? "کمتر" : "بیشتر")));
    }
    if (result.note) row.status.appendChild(el("span", "extra", " · " + result.note));
    row.action.textContent = "↓";
    row.action.title = outs.length > 1 ? "دانلود همه (ZIP)" : "دانلود " + baseLeaf(outs[0].name);
    if (outs.length > 1) {
      var det = el("details", "outs");
      det.appendChild(el("summary", null, "نمایش " + fa(outs.length) + " فایل"));
      var ul = el("ul");
      outs.slice(0, 300).forEach(function (o) {
        var li = el("li");
        var b = el("button", "out-link", baseLeaf(o.name));
        b.type = "button";
        b.title = o.name;
        b.addEventListener("click", function () { download(o.blob, baseLeaf(o.name)); });
        li.appendChild(b);
        li.appendChild(el("small", null, size(o.blob.size)));
        ul.appendChild(li);
      });
      if (outs.length > 300) ul.appendChild(el("li", null, "و " + fa(outs.length - 300) + " فایل دیگر (در ZIP)"));
      det.appendChild(ul);
      row.info.appendChild(det);
      row.outs = det;
    }
  }
  function baseLeaf(name) { return name.replace(/^.*\//, ""); }

  function downloadResult(result) {
    var outs = result.outputs;
    if (outs.length === 1) { download(outs[0].blob, baseLeaf(outs[0].name)); return; }
    engine("archive").then(function (m) { return m.makeZip(outs); })
      .then(function (zip) { download(zip, (result.zipName || "PixNexa") + ".zip"); });
  }

  function download(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 60000);
  }

  // ---------- input ----------
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
  drop.addEventListener("drop", function (e) { if (e.dataTransfer && !busy) addFiles(e.dataTransfer.files); });
  document.addEventListener("paste", function (e) {
    if (busy || !e.clipboardData || !e.clipboardData.files.length) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    addFiles(e.clipboardData.files);
  });

  // ---------- running ----------
  function buildJobs() {
    var jobs = [];
    presentCats().forEach(function (cat) {
      var its = items.filter(function (it) { return it.cat === cat; });
      var sp = spec(cat);
      var opt = Object.assign({}, settings[mode][cat], { target: sp.target });
      var skip = function (it, text) { setRow(it.row, "muted", text); };
      if (cat === "other") {
        its.forEach(function (it) { skip(it, size(it.file.size) + " · تبدیل نمی‌شود؛ فقط در «ساخت ZIP»"); });
      } else if (mode === "compress" && cat === "subtitle") {
        its.forEach(function (it) { skip(it, size(it.file.size) + " · زیرنویس کاهش حجم ندارد"); });
      } else if (mode === "compress" && cat === "data") {
        its.forEach(function (it) {
          if (/^(json|xml)$/.test(extOf(it.file.name))) jobs.push({ item: it, cat: cat, opt: opt });
          else skip(it, size(it.file.size) + " · کاهش حجم ندارد؛ از «ساخت ZIP» استفاده کنید");
        });
      } else if (mode === "convert" && ((cat === "image" && sp.target === "pdf") || (cat === "pdf" && sp.target === "merge"))) {
        jobs.push({ group: true, items: its, cat: cat, opt: opt, fn: cat === "image" ? "toPdf" : "merge" });
      } else {
        its.forEach(function (it) { jobs.push({ item: it, cat: cat, opt: opt }); });
      }
    });
    return jobs;
  }

  function makeCtx(row) {
    return {
      status: function (t) { row.status.textContent = t; },
      progress: function (f) { setProgress(row, f); },
      notice: showNotice,
      isCancelled: function () { return cancelled; },
      member: function (it, state, msg) {
        if (state === "working") setRow(it.row, "working", "در حال افزودن…");
        else if (state === "done") setRow(it.row, "merged", size(it.file.size) + " · افزوده شد");
        else setRow(it.row, "failed", msg || "ناموفق");
      }
    };
  }
  function failText(e) {
    if (e && e.user) return e.message;
    return "تبدیل نشد؛ این فایل خوانده نشد یا برای مرورگر پشتیبانی نمی‌شود.";
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function newGroupRow(cat, label) {
    var g = { result: null };
    var fake = { name: label, size: 0 };
    g.row = buildRow(fake, cat, function () { if (g.result) downloadResult(g.result); });
    g.row.li.classList.add("group");
    list.insertBefore(g.row.li, list.firstChild);
    groups.push(g);
    return g;
  }

  function runJob(job) {
    if (job.group) {
      var label = job.cat === "image" ? "PixNexa-images.pdf" : "PixNexa-merged.pdf";
      var g = newGroupRow("pdf", label);
      setRow(g.row, "working", "در حال آماده‌سازی…");
      job.items.forEach(function (it) { setRow(it.row, "", "در صف"); });
      var before = job.items.reduce(function (s, it) { return s + it.file.size; }, 0);
      return wait(30).then(function () { return engine(job.cat); }).then(function (m) {
        return m[job.fn](job.items, job.opt, makeCtx(g.row));
      }).then(function (r) {
        g.result = { outputs: r.outputs, before: before, note: r.note };
        showResult(g.row, g.result);
      }).catch(function (e) {
        if (!(e && e.user)) console.error(e);
        setRow(g.row, "failed", cancelled ? "لغو شد" : failText(e));
        job.items.forEach(function (it) { if (/working|^file$/.test(it.row.li.className)) setRow(it.row, "", size(it.file.size)); });
      });
    }
    var it = job.item;
    setRow(it.row, "working", "در حال آماده‌سازی…");
    return wait(30).then(function () { return engine(job.cat); }).then(function (m) {
      return m.run(it, job.opt, makeCtx(it.row), mode);
    }).then(function (r) {
      it.result = {
        outputs: r.outputs, before: it.file.size, note: r.note,
        original: r.outputs.length === 1 && r.outputs[0].blob === it.file,
        zipName: baseName(it.file.name).replace(/\.tar$/i, "")
      };
      showResult(it.row, it.result);
    }).catch(function (e) {
      if (!(e && e.user) && !(e && e.cancelled)) console.error(e);
      setRow(it.row, "failed", cancelled || (e && e.cancelled) ? "لغو شد" : failText(e));
    });
  }

  convertBtn.addEventListener("click", function () {
    if (busy || !items.length) return;
    busy = true;
    cancelled = false;
    groups.forEach(function (g) { removeRow(g.row); });
    groups = [];
    items.forEach(function (it) { it.result = null; resetRow(it); });
    summary.hidden = true;
    renderControls();
    var jobs = buildJobs();
    jobs.forEach(function (j) { if (!j.group) setRow(j.item.row, "", "در صف"); });
    var chain = Promise.resolve();
    jobs.forEach(function (job) {
      chain = chain.then(function () {
        if (cancelled) {
          (job.group ? job.items : [job.item]).forEach(function (it) { setRow(it.row, "failed", "لغو شد"); });
          return;
        }
        return runJob(job);
      });
    });
    chain.then(function () {
      busy = false;
      showNotice(null);
      renderControls();
      showSummary();
    });
  });

  cancelBtn.addEventListener("click", function () {
    if (!busy) return;
    cancelled = true;
    cancelBtn.hidden = true;
    // Stop long-running engines right away; the others stop after the current page or file.
    ["image", "media"].forEach(function (n) {
      if (engines[n]) engines[n].then(function (m) { if (m.stop) m.stop(); }).catch(function () {});
    });
  });

  function showSummary() {
    var outs = allOutputs();
    var done = items.concat(groups).filter(function (x) { return x.result; });
    var failed = items.filter(function (it) { return /failed/.test(it.row.li.className); }).length;
    if (!outs.length) {
      summary.hidden = !failed;
      summary.textContent = failed ? "هیچ فایلی آماده نشد." : "";
      return;
    }
    var before = 0, after = 0;
    done.forEach(function (x) { before += x.result.before; });
    outs.forEach(function (o) { after += o.blob.size; });
    summary.textContent = "✓ " + fa(outs.length) + " فایل آماده شد، " + size(before) + " ← " + size(after) +
      (failed ? "، " + fa(failed) + " ناموفق" : "") + ". برای دانلود هر فایل روی ↓ بزنید.";
    summary.hidden = false;
    if (outs.length === 1) download(outs[0].blob, baseLeaf(outs[0].name));
  }

  clearBtn.addEventListener("click", function () {
    if (busy) return;
    items.concat(groups).forEach(function (x) { removeRow(x.row); });
    items = [];
    groups = [];
    list.textContent = "";
    summary.hidden = true;
    renderPanels();
    renderControls();
  });

  zipBtn.addEventListener("click", function () {
    var outs = allOutputs();
    if (outs.length < 2) return;
    zipBtn.disabled = true;
    zipBtn.textContent = "در حال ساخت ZIP…";
    engine("archive").then(function (m) { return m.makeZip(outs); }).then(function (zip) {
      download(zip, "PixNexa.zip");
    }).catch(function (e) { console.error(e); }).then(function () {
      zipBtn.disabled = false;
      zipBtn.textContent = "دانلود همه (ZIP)";
    });
  });

  // Any files (the originals) -> one ZIP.
  packBtn.addEventListener("click", function () {
    if (busy || !items.length) return;
    busy = true;
    renderControls();
    var g = newGroupRow("archive", "PixNexa-files.zip");
    setRow(g.row, "working", "در حال ساخت ZIP…");
    var before = items.reduce(function (s, it) { return s + it.file.size; }, 0);
    engine("archive").then(function (m) {
      return m.makeZip(items.map(function (it) { return { name: it.file.name, blob: it.file }; }));
    }).then(function (zip) {
      g.result = { outputs: [{ blob: zip, name: "PixNexa-files.zip" }], before: before, note: fa(items.length) + " فایل" };
      showResult(g.row, g.result);
      download(zip, "PixNexa-files.zip");
    }).catch(function (e) {
      console.error(e);
      setRow(g.row, "failed", failText(e));
    }).then(function () {
      busy = false;
      renderControls();
    });
  });

  renderPanels();
  renderControls();
})();
