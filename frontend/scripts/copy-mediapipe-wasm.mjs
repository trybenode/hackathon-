/**
 * Purpose: Serve MediaPipe's WASM from this app instead of a CDN.
 * Dependencies: @mediapipe/tasks-vision, node:fs.
 * Used by: the postinstall hook.
 *
 * The runtime files are ~34MB, so they are copied out of node_modules at
 * install time and gitignored rather than committed. Serving them ourselves
 * keeps the binary and the package version in step.
 */

import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../node_modules/@mediapipe/tasks-vision/wasm");
const destination = resolve(here, "../public/mediapipe/wasm");

try {
  await rm(destination, { recursive: true, force: true });
  await mkdir(destination, { recursive: true });
  await cp(source, destination, { recursive: true });
  console.log(`Copied MediaPipe WASM to ${destination}`);
} catch (error) {
  // A missing package is not fatal: the liveness screen falls back to manual
  // capture when the detector cannot load.
  console.warn(`Could not copy MediaPipe WASM: ${error.message}`);
}
