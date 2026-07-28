// esbuild pipeline for the Codinal editor surface.
//
// The rest of the UI (startup.js, app.css, vendor/xterm.js) stays zero-build
// vanilla JS loaded via <script src>. Only the editor surface uses this
// bundler, because CodeMirror 6 ships as ESM modules.
//
// Output: desktop/ui/dist/editor.js (+ editor.css once CM6 lands in Phase 49)
// Loaded by index.html alongside the existing scripts. The editor exposes a
// global `window.CodinalEditor` that vanilla JS calls into.
import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

/** @type {import("esbuild").BuildOptions} */
const options = {
  entryPoints: ["ui-src/editor.ts"],
  bundle: true,
  format: "iife",
  globalName: "CodinalEditor",
  outfile: "ui/dist/editor.js",
  target: ["safari16", "chrome120", "firefox120"],
  platform: "browser",
  // Tauri CSP is script-src 'self' — esbuild's IIFE output is plain JS with
  // no eval/Function(), so this is safe.
  legalComments: "none",
  logLevel: "info",
  sourcemap: false,
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("esbuild watching (Ctrl+C to stop)...");
} else {
  await esbuild.build(options);
  console.log("esbuild: editor.js built");
}
