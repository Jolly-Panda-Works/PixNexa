# Third-party libraries used by PixNexa Web

Everything runs in the visitor's browser; no file is uploaded. Each library is loaded only when its
file type is used (see `../engines/`). Versions are pinned; every folder keeps the library's license.

| Folder | Package (npm, exact version) | License | Used for | Files kept |
|---|---|---|---|---|
| `fflate/` | `fflate@0.8.2` | MIT | ZIP create/extract, GZ | `esm/browser.js` → `fflate.js` |
| `pdf-lib/` | `pdf-lib@1.17.1` | MIT (bundles pako, MIT) | merge, split, page ranges, images → PDF, rebuilt compressed PDF | `dist/pdf-lib.esm.min.js` → `pdf-lib.js` |
| `pdfjs/` | `pdfjs-dist@4.10.38` (legacy build) | Apache-2.0 | PDF → PNG/JPEG/TXT, rendering pages for PDF compression | `legacy/build/pdf.min.mjs`, `pdf.worker.min.mjs` (renamed to `.js`) |
| `js-yaml/` | `js-yaml@4.1.0` | MIT | YAML | `dist/js-yaml.mjs` → `js-yaml.js` |
| `smol-toml/` | `smol-toml@1.3.1` | BSD-3-Clause | TOML | `dist/*.js` |
| `heic2any/` | `heic2any@0.0.4` | MIT; contains libheif and libde265 compiled to JS (LGPL-3.0) | HEIC/HEIF input | `dist/heic2any.min.js` |
| `jsquash/jpeg/` | `@jsquash/jpeg@1.6.0` | Apache-2.0; codec MozJPEG/libjpeg-turbo (IJG, BSD-3-Clause, zlib), see `LICENSE.codec.md` | MozJPEG encoder | `encode.js`, `meta.js`, `utils.js`, `codec/enc/mozjpeg_enc.{js,wasm}` |
| `jsquash/oxipng/` | `@jsquash/oxipng@2.3.0` | Apache-2.0; codec OxiPNG (MIT), see `LICENSE.codec.md` | lossless PNG optimisation | `optimise.js`, `meta.js`, `codec/pkg/squoosh_oxipng{.js,_bg.wasm}` |
| `jsquash/avif/` | `@jsquash/avif@2.1.1` | Apache-2.0; codec libavif + libaom (BSD-2-Clause) | AVIF encoder | `encode.js`, `meta.js`, `utils.js`, `codec/enc/avif_enc.{js,wasm}` |
| `ffmpeg/` | `@ffmpeg/ffmpeg@0.12.15` | MIT | ffmpeg.wasm wrapper (its worker must be same-origin) | `dist/umd/ffmpeg.js`, `dist/umd/814.ffmpeg.js` |
| `ffmpeg/util/` | `@ffmpeg/util@0.12.2` | MIT | `toBlobURL` with download progress | `dist/esm/{index,errors,const}.js` |

Total size of this folder: about 7.9 MB (the largest file is the AVIF encoder, 3.5 MB, loaded only when AVIF is chosen).

## Loaded from a CDN, not stored here

| Package | License | URL |
|---|---|---|
| `@ffmpeg/core@0.12.10` (single-threaded, ~31 MB wasm) | GPL-2.0-or-later (FFmpeg with x264, LAME, libvpx, Vorbis, Opus…) | `https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/umd/ffmpeg-core.{js,wasm}` |

It is fetched only the first time someone converts a video or audio file (the browser caches it), and runs
as a separate program inside a Web Worker. Its source is at https://github.com/ffmpegwasm/ffmpeg.wasm.

## Local changes

- Only the **single-threaded** builds are kept: GitHub Pages cannot send the COOP/COEP headers that
  `SharedArrayBuffer` (and so wasm threads) need. In `jsquash/avif/encode.js` and `jsquash/oxipng/optimise.js`
  the multi-threaded branch and its `wasm-feature-detect` import were removed (marked with a `PixNexa:` comment).
- `//# sourceMappingURL` comments were removed from `pdf-lib.js` and the ffmpeg files (the maps are not shipped).
- `ffmpeg/LICENSE` was added from the ffmpeg.wasm repository (the npm package has no license file).

## Updating

```sh
npm pack <package>@<version>   # then copy the files listed above
```
Keep the versions in `../engines/*.js` (for example `CORE_BASE` in `media.js`) and this table in sync.
