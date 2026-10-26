#!/usr/bin/env node
// cleancopy is a Python program. This runs the PyPI release with the same
// version as this package, through uv, which fetches Python 3.12 if needed.
const { spawnSync } = require("node:child_process");
const { version } = require("../package.json");

const run = spawnSync("uvx", [`cleancopy@${version}`, ...process.argv.slice(2)], { stdio: "inherit" });
if (run.error) {
  const missing = run.error.code === "ENOENT";
  console.error(missing ? "cleancopy needs uv: https://docs.astral.sh/uv/getting-started/installation/" : run.error.message);
  process.exit(1);
}
process.exit(run.status ?? 1);
