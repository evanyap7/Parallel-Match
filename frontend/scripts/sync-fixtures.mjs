import { mkdir, copyFile } from "node:fs/promises";

// scripts/ is one level below frontend/: resolve shared fixtures from repo root.

const rootFixtures = new URL("../../fixtures/", import.meta.url);

const target = new URL("../public/fixtures/", import.meta.url);

await mkdir(target, { recursive: true });

for (const name of [
  "m012.json",
  "fork_m012.json",
  "m052.json",
  "fork_m052.json",
]) {
  await copyFile(new URL(name, rootFixtures), new URL(name, target));
}

console.log("Copied the shared repository fixtures unchanged.");
