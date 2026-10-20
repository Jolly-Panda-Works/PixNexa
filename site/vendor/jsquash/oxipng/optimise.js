/**
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *     http://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { defaultOptions } from './meta.js';
async function initST(moduleOrPath) {
    const { default: init, optimise, optimise_raw, } = await import('./codec/pkg/squoosh_oxipng.js');
    await init(moduleOrPath);
    return { optimise, optimise_raw };
}
let wasmReady;
export async function init(moduleOrPath) {
    var _a;
    if (!wasmReady) {
        // PixNexa: single-threaded build only (GitHub Pages cannot send COOP/COEP headers).
        wasmReady = initST(moduleOrPath);
    }
    return wasmReady;
}
export default async function optimise(data, options = {}) {
    const _options = { ...defaultOptions, ...options };
    const { optimise, optimise_raw } = await init();
    if (data instanceof ImageData) {
        return optimise_raw(data.data, data.width, data.height, _options.level, _options.interlace, _options.optimiseAlpha).buffer;
    }
    return optimise(new Uint8Array(data), _options.level, _options.interlace, _options.optimiseAlpha).buffer;
}
