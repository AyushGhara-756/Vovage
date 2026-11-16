import test from "node:test";
import assert from "node:assert/strict";
import { safeNextPath } from "./safe-next.ts";

test("keeps local paths", () => {
  assert.equal(safeNextPath("/profile"), "/profile");
  assert.equal(safeNextPath("/profile?tab=saves#top"), "/profile?tab=saves#top");
});

test("falls back for missing or external paths", () => {
  assert.equal(safeNextPath(null), "/");
  assert.equal(safeNextPath(""), "/");
  assert.equal(safeNextPath("https://evil.example"), "/");
  assert.equal(safeNextPath("//evil.example"), "/");
  assert.equal(safeNextPath("/\\evil.example"), "/");
  assert.equal(safeNextPath("/profile", "/signin"), "/profile");
  assert.equal(safeNextPath("https://evil.example", "/signin"), "/signin");
});

test("rejects control characters that URL parsing can collapse into //", () => {
  for (const char of ["\t", "\n", "\r", "\u0000", "\u000b", "\u000c", "\u007f", " "]) {
    assert.equal(
      safeNextPath(`/${char}/evil.example`),
      "/",
      `control character ${JSON.stringify(char)} must not survive`,
    );
  }
});
