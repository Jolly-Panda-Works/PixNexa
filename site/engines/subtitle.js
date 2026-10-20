// Subtitles: SRT <-> WebVTT <-> ASS/SSA. Old Persian files in Windows-1256 are read correctly.
import { baseName, extOf, readText, textBlob, UserError, fa } from "./util.js";

function ms(h, m, s, frac) {
  return ((+h || 0) * 3600 + (+m) * 60 + (+s)) * 1000 + (+String(frac || "0").padEnd(3, "0").slice(0, 3));
}
const TIME = /(?:(\d+):)?(\d{1,2}):(\d{1,2})[,.](\d{1,3})/;
function parseTime(t) {
  const m = TIME.exec(t);
  return m ? ms(m[1], m[2], m[3], m[4]) : NaN;
}

function parseSrtVtt(text) {
  const cues = [];
  text.replace(/\r\n?/g, "\n").split(/\n{2,}/).forEach((block) => {
    const lines = block.split("\n").filter((l, i) => i > 0 || l.trim() !== "");
    const ti = lines.findIndex((l) => l.indexOf("-->") >= 0);
    if (ti < 0) return;  // WEBVTT header, NOTE, STYLE, REGION
    const [a, b] = lines[ti].split("-->");
    const start = parseTime(a), end = parseTime(b);
    if (isNaN(start) || isNaN(end)) return;
    cues.push({ start, end, text: lines.slice(ti + 1).join("\n").trim() });
  });
  return cues;
}

function parseAss(text) {
  const cues = [];
  let fmt = null, inEvents = false;
  text.replace(/\r\n?/g, "\n").split("\n").forEach((line) => {
    const t = line.trim();
    if (/^\[.*\]$/.test(t)) { inEvents = /^\[events\]$/i.test(t); return; }
    if (!inEvents) return;
    if (/^format\s*:/i.test(t)) { fmt = t.replace(/^format\s*:/i, "").split(",").map((s) => s.trim().toLowerCase()); return; }
    if (!/^dialogue\s*:/i.test(t)) return;
    const f = fmt || ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"];
    const parts = t.replace(/^dialogue\s*:\s*/i, "").split(",");
    const head = parts.slice(0, f.length - 1), body = parts.slice(f.length - 1).join(",");
    const start = parseAssTime(head[f.indexOf("start")]), end = parseAssTime(head[f.indexOf("end")]);
    if (isNaN(start) || isNaN(end)) return;
    const txt = body
      .replace(/\{\\i1\}/g, "<i>").replace(/\{\\i0\}/g, "</i>")
      .replace(/\{\\b1\}/g, "<b>").replace(/\{\\b0\}/g, "</b>")
      .replace(/\{\\u1\}/g, "<u>").replace(/\{\\u0\}/g, "</u>")
      .replace(/\{[^}]*\}/g, "").replace(/\\N/gi, "\n").replace(/\\h/g, " ");
    cues.push({ start, end, text: txt.trim() });
  });
  return cues.sort((a, b) => a.start - b.start);
}
function parseAssTime(t) {
  const m = /(\d+):(\d{1,2}):(\d{1,2})[.,](\d{1,3})/.exec(t || "");
  if (!m) return NaN;
  const frac = m[4].length === 2 ? +m[4] * 10 : m[4].length === 1 ? +m[4] * 100 : +m[4];
  return ((+m[1]) * 3600 + (+m[2]) * 60 + (+m[3])) * 1000 + frac;
}

function two(n) { return String(n).padStart(2, "0"); }
function stamp(t, sep) {
  t = Math.max(0, Math.round(t));
  const h = Math.floor(t / 3600000), m = Math.floor(t / 60000) % 60, s = Math.floor(t / 1000) % 60, f = t % 1000;
  return two(h) + ":" + two(m) + ":" + two(s) + sep + String(f).padStart(3, "0");
}
function assStamp(t) {
  t = Math.max(0, Math.round(t / 10));
  const h = Math.floor(t / 360000), m = Math.floor(t / 6000) % 60, s = Math.floor(t / 100) % 60, c = t % 100;
  return h + ":" + two(m) + ":" + two(s) + "." + two(c);
}
const cleanTags = (s) => s.replace(/<(?!\/?[ibu]>)[^>]*>/gi, "");

function toSrt(cues) {
  return cues.map((c, i) => (i + 1) + "\n" + stamp(c.start, ",") + " --> " + stamp(c.end, ",") + "\n" + cleanTags(c.text)).join("\n\n") + "\n";
}
function toVtt(cues) {
  return "WEBVTT\n\n" + cues.map((c) => stamp(c.start, ".") + " --> " + stamp(c.end, ".") + "\n" + cleanTags(c.text).replace(/-->/g, "->")).join("\n\n") + "\n";
}
function toAss(cues) {
  const head = [
    "[Script Info]", "; Converted by PixNexa Web", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    "Style: Default,Tahoma,64,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1",
    "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
  ];
  const lines = cues.map((c) => {
    const t = cleanTags(c.text)
      .replace(/<i>/gi, "{\\i1}").replace(/<\/i>/gi, "{\\i0}")
      .replace(/<b>/gi, "{\\b1}").replace(/<\/b>/gi, "{\\b0}")
      .replace(/<u>/gi, "{\\u1}").replace(/<\/u>/gi, "{\\u0}")
      .replace(/\n/g, "\\N");
    return "Dialogue: 0," + assStamp(c.start) + "," + assStamp(c.end) + ",Default,,0,0,0,," + t;
  });
  return head.concat(lines).join("\n") + "\n";
}

export async function run(item, opt) {
  const file = item.file, ext = extOf(file.name);
  const text = await readText(file, true);
  const cues = ext === "ass" || ext === "ssa" || /^\s*\[script info\]/i.test(text) ? parseAss(text) : parseSrtVtt(text);
  if (!cues.length) throw new UserError("هیچ زیرنویسی در این فایل پیدا نشد.");
  const target = opt.target;
  const out = target === "vtt" ? toVtt(cues) : target === "ass" ? toAss(cues) : toSrt(cues);
  const type = target === "vtt" ? "text/vtt" : target === "ass" ? "text/x-ssa" : "application/x-subrip";
  return { outputs: [{ blob: textBlob(out, type), name: baseName(file.name) + "." + target }], note: fa(cues.length) + " زیرنویس" };
}
