// Data: JSON <-> YAML <-> CSV <-> XML <-> TOML. YAML with js-yaml, TOML with smol-toml,
// CSV and XML are handled here (XML is parsed with the browser's DOMParser).
import { VENDOR, baseName, extOf, readText, textBlob, UserError } from "./util.js";

const yaml = () => import(VENDOR + "js-yaml/js-yaml.js");
const toml = () => import(VENDOR + "smol-toml/index.js");

export function kindOf(name) {
  const e = extOf(name);
  return e === "yml" ? "yaml" : e === "tsv" ? "csv" : e;
}

// ---------- CSV ----------
function detectDelimiter(text, ext) {
  if (ext === "tsv") return "\t";
  const line = text.split(/\r?\n/, 1)[0];
  const counts = [",", ";", "\t", "|"].map((d) => [d, line.split(d).length]);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 1 ? counts[0][0] : ",";
}
export function parseCSV(text, delim) {
  const rows = [];
  let row = [], field = "", i = 0, quoted = false;
  while (i < text.length) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        quoted = false; i++; continue;
      }
      field += c; i++; continue;
    }
    if (c === '"' && field === "") { quoted = true; i++; continue; }
    if (c === delim) { row.push(field); field = ""; i++; continue; }
    if (c === "\r" || c === "\n") {
      row.push(field); field = "";
      rows.push(row); row = [];
      i += c === "\r" && text[i + 1] === "\n" ? 2 : 1;
      continue;
    }
    field += c; i++;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.length > 1 || r[0] !== "");
}
function guessValue(s) {
  if (/^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?$/.test(s) && s.length < 16) return Number(s);
  if (s === "true") return true;
  if (s === "false") return false;
  return s;
}
function csvToValue(text, ext) {
  const rows = parseCSV(text, detectDelimiter(text, ext));
  if (!rows.length) return [];
  const head = rows[0].map((h, i) => h.trim() || "column" + (i + 1));
  return rows.slice(1).map((r) => {
    const o = {};
    head.forEach((h, i) => { o[h] = guessValue(r[i] == null ? "" : r[i]); });
    return o;
  });
}
function flatten(obj, prefix, out) {
  Object.keys(obj).forEach((k) => {
    const v = obj[k], key = prefix ? prefix + "." + k : k;
    if (v && typeof v === "object" && !Array.isArray(v) && !(v instanceof Date)) flatten(v, key, out);
    else out[key] = v;
  });
  return out;
}
function cell(v) {
  if (v == null) return "";
  if (v instanceof Date) return v.toISOString();
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
function valueToCSV(v) {
  // Find the list of records: the value itself, or the only array inside an object ({"items": [...]}).
  let rows = v, note = "";
  const isRecord = (x) => x && typeof x === "object" && !Array.isArray(x);
  if (isRecord(rows)) {
    const keys = Object.keys(rows);
    const lists = keys.filter((k) => Array.isArray(rows[k]) && rows[k].length && rows[k].every(isRecord));
    if (keys.length === 1 && isRecord(rows[keys[0]])) return valueToCSV(rows[keys[0]]);
    if (lists.length === 1) {
      if (keys.length > 1) note = "فقط فهرست «" + lists[0] + "» جدول شد";
      rows = rows[lists[0]];
    } else rows = [rows];
  }
  if (!Array.isArray(rows)) rows = [{ value: rows }];
  const flat = rows.map((r) => (r && typeof r === "object" && !Array.isArray(r) ? flatten(r, "", {}) : { value: r }));
  const cols = [];
  flat.forEach((r) => Object.keys(r).forEach((k) => { if (cols.indexOf(k) < 0) cols.push(k); }));
  const esc = (s) => (/[",\r\n]/.test(s) || /^\s|\s$/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s);
  const lines = [cols.map(esc).join(",")];
  flat.forEach((r) => lines.push(cols.map((c) => esc(cell(r[c]))).join(",")));
  // The BOM lets Excel open Persian text correctly.
  return { text: "\uFEFF" + lines.join("\r\n") + "\r\n", note };
}

// ---------- XML ----------
function xmlToValue(text) {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) throw new UserError("XML نامعتبر است.");
  const conv = (el) => {
    const o = {}, multi = new Set();
    let hasKeys = false;
    Array.prototype.forEach.call(el.attributes, (a) => { o["@" + a.name] = a.value; hasKeys = true; });
    let text = "";
    Array.prototype.forEach.call(el.childNodes, (n) => {
      if (n.nodeType === 1) {
        const v = conv(n), k = n.nodeName;
        if (k in o) { if (!multi.has(k)) { o[k] = [o[k]]; multi.add(k); } o[k].push(v); }
        else o[k] = v;
        hasKeys = true;
      } else if (n.nodeType === 3 || n.nodeType === 4) {
        text += n.nodeValue;
      }
    });
    text = text.trim();
    if (!hasKeys) return text === "" ? "" : guessValue(text);
    if (text) o["#text"] = text;
    return o;
  };
  const root = doc.documentElement;
  return { [root.nodeName]: conv(root) };
}
function xmlName(k) {
  let n = String(k).replace(/[^\p{L}\p{N}_.\-:]/gu, "_");
  if (!/^[\p{L}_]/u.test(n)) n = "_" + n;
  return n;
}
function escXml(s) {
  return cell(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function valueToXML(v) {
  let rootName = "root", body = v;
  if (v && typeof v === "object" && !Array.isArray(v)) {
    const keys = Object.keys(v);
    if (keys.length === 1 && !Array.isArray(v[keys[0]])) { rootName = keys[0]; body = v[keys[0]]; }
  }
  const out = ['<?xml version="1.0" encoding="UTF-8"?>'];
  const write = (name, val, ind) => {
    name = xmlName(name);
    if (Array.isArray(val)) { val.forEach((x) => write(name, x, ind)); return; }
    if (val && typeof val === "object" && !(val instanceof Date)) {
      let attrs = "", text = null;
      const kids = [];
      Object.keys(val).forEach((k) => {
        if (k[0] === "@") attrs += " " + xmlName(k.slice(1)) + '="' + escXml(val[k]) + '"';
        else if (k === "#text") text = val[k];
        else kids.push(k);
      });
      if (!kids.length) {
        out.push(ind + "<" + name + attrs + (text == null ? "/>" : ">" + escXml(text) + "</" + name + ">"));
        return;
      }
      out.push(ind + "<" + name + attrs + ">");
      if (text != null) out.push(ind + "  " + escXml(text));
      kids.forEach((k) => write(k, val[k], ind + "  "));
      out.push(ind + "</" + name + ">");
      return;
    }
    out.push(ind + "<" + name + (val == null || val === "" ? "/>" : ">" + escXml(val) + "</" + name + ">"));
  };
  if (Array.isArray(body)) {
    out.push("<" + rootName + ">");
    body.forEach((x) => write("item", x, "  "));
    out.push("</" + rootName + ">");
  } else {
    write(rootName, body, "");
  }
  return out.join("\n") + "\n";
}

// ---------- TOML ----------
function forToml(v) {
  if (Array.isArray(v)) return v.filter((x) => x != null).map(forToml);
  if (v && typeof v === "object" && !(v instanceof Date)) {
    const o = {};
    Object.keys(v).forEach((k) => { if (v[k] != null) o[k] = forToml(v[k]); });
    return o;
  }
  return v;
}

async function parse(kind, text, ext) {
  try {
    if (kind === "json") return JSON.parse(text);
    if (kind === "yaml") return (await yaml()).load(text);
    if (kind === "toml") return (await toml()).parse(text);
    if (kind === "csv") return csvToValue(text, ext);
    if (kind === "xml") return xmlToValue(text);
  } catch (e) {
    if (e && e.user) throw e;
    throw new UserError(kind.toUpperCase() + " نامعتبر است" + (e && e.message ? ": " + String(e.message).split("\n")[0].slice(0, 80) : "") + ".");
  }
  throw new UserError("این نوع داده پشتیبانی نمی‌شود.");
}

const MIME = { json: "application/json", yaml: "application/yaml", csv: "text/csv", xml: "application/xml", toml: "application/toml" };

export async function run(item, opt, ctx, mode) {
  const file = item.file, ext = extOf(file.name), kind = kindOf(file.name), base = baseName(file.name);
  const text = await readText(file);
  if (mode === "compress") {
    if (kind === "json") {
      const v = await parse("json", text, ext);
      return { outputs: [{ blob: textBlob(JSON.stringify(v), MIME.json), name: base + ".min.json" }], note: "فشرده (minify)" };
    }
    if (kind === "xml") {
      xmlToValue(text);  // validate
      const min = text.replace(/<!--[\s\S]*?-->/g, "").replace(/>\s+</g, "><").trim();
      return { outputs: [{ blob: textBlob(min, MIME.xml), name: base + ".min.xml" }], note: "فشرده (minify)" };
    }
    throw new UserError("این فرمت کاهش حجم ندارد؛ از «ساخت ZIP» استفاده کنید.");
  }
  const target = opt.target;
  const value = await parse(kind, text, ext);
  let out, note = "";
  if (target === "json") out = JSON.stringify(value, (k, v) => (typeof v === "bigint" ? Number(v) : v), 2) + "\n";
  else if (target === "yaml") out = (await yaml()).dump(JSON.parse(JSON.stringify(value)), { noRefs: true, lineWidth: -1 });
  else if (target === "csv") ({ text: out, note } = valueToCSV(value));
  else if (target === "xml") out = valueToXML(value);
  else if (target === "toml") {
    let v = forToml(value);
    if (Array.isArray(v) || !v || typeof v !== "object") v = { items: Array.isArray(v) ? v : [v] };
    try { out = (await toml()).stringify(v); } catch (e) { throw new UserError("این داده به TOML تبدیل نمی‌شود."); }
  } else throw new UserError("فرمت خروجی نامعتبر است.");
  return { outputs: [{ blob: textBlob(out, MIME[target]), name: base + "." + target }], note };
}
