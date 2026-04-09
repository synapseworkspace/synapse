#!/usr/bin/env node
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const REQUIRED_PACKAGES = [
  "@synapseworkspace/sdk",
  "@synapseworkspace/schema",
  "@synapseworkspace/openclaw-plugin"
];

function parseArgs(argv) {
  const args = new Map();
  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const value = index + 1 < argv.length && !argv[index + 1].startsWith("--") ? argv[index + 1] : "true";
    args.set(key, value);
    if (value !== "true") {
      index += 1;
    }
  }
  return args;
}

function readPackageVersion(projectRoot, packageName) {
  const packageJsonPath = path.join(projectRoot, "node_modules", ...packageName.split("/"), "package.json");
  if (!fs.existsSync(packageJsonPath)) {
    throw new Error(`package not installed: ${packageName}`);
  }
  const payload = JSON.parse(fs.readFileSync(packageJsonPath, "utf-8"));
  return String(payload.version || "").trim();
}

async function main() {
  const args = parseArgs(process.argv);
  const expectedVersion = String(args.get("expected-version") || "").trim();
  const projectRoot = path.resolve(String(args.get("project-root") || process.cwd()));
  if (!expectedVersion) {
    throw new Error("--expected-version is required");
  }

  const versions = {};
  for (const packageName of REQUIRED_PACKAGES) {
    const installedVersion = readPackageVersion(projectRoot, packageName);
    versions[packageName] = installedVersion;
    if (installedVersion !== expectedVersion) {
      throw new Error(`version mismatch for ${packageName}: expected ${expectedVersion}, got ${installedVersion}`);
    }
  }

  const requireFromRoot = createRequire(path.join(projectRoot, "package.json"));
  const sdk = await import(pathToFileURL(requireFromRoot.resolve("@synapseworkspace/sdk")).href);
  const plugin = await import(pathToFileURL(requireFromRoot.resolve("@synapseworkspace/openclaw-plugin")).href);
  if (!sdk || typeof sdk !== "object") {
    throw new Error("SDK import failed");
  }
  if (!plugin || typeof plugin !== "object") {
    throw new Error("OpenClaw plugin import failed");
  }
  if (typeof sdk.Synapse !== "function") {
    throw new Error("SDK export Synapse missing");
  }
  if (typeof plugin.createSynapseOpenClawPlugin !== "function") {
    throw new Error("OpenClaw plugin export createSynapseOpenClawPlugin missing");
  }

  console.log(
    JSON.stringify({
      status: "ok",
      expected_version: expectedVersion,
      versions,
      sdk_exports: Object.keys(sdk).length,
      plugin_exports: Object.keys(plugin).length
    })
  );
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      status: "failed",
      error: String(error && error.message ? error.message : error)
    })
  );
  process.exit(1);
});
