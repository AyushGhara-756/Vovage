import test from "node:test";
import assert from "node:assert/strict";
import { AVATAR_MAX_BYTES, validateAvatarFile } from "./avatar.ts";

test("accepts the supported avatar extensions and MIME types", () => {
  for (const [name, type] of [
    ["a.png", "image/png"],
    ["a.jpg", "image/jpeg"],
    ["a.jpeg", "image/jpeg"],
    ["a.webp", "image/webp"],
    ["a.gif", "image/gif"],
  ]) {
    assert.equal(validateAvatarFile({ name, type, size: 100 }), type);
  }
});

test("rejects unsupported extensions", () => {
  assert.throws(
    () => validateAvatarFile({ name: "a.svg", type: "image/svg+xml", size: 10 }),
    /PNG, JPEG, WebP, or GIF/i,
  );
});

test("rejects extension and declared type mismatches", () => {
  assert.throws(
    () => validateAvatarFile({ name: "a.png", type: "image/jpeg", size: 10 }),
    /match/i,
  );
  assert.throws(
    () => validateAvatarFile({ name: "a.png", type: "", size: 10 }),
    /could not be verified/i,
  );
});

test("rejects empty and over-2MB files", () => {
  assert.throws(
    () => validateAvatarFile({ name: "a.png", type: "image/png", size: 0 }),
    /empty/i,
  );
  assert.throws(
    () =>
      validateAvatarFile({
        name: "a.png",
        type: "image/png",
        size: AVATAR_MAX_BYTES + 1,
      }),
    /2 MB/i,
  );
});
