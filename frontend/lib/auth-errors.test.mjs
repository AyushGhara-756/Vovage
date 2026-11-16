import test from "node:test";
import assert from "node:assert/strict";
import { authErrorMessage, verifyErrorMessage } from "./auth-errors.ts";

test("cross-device PKCE failures get an actionable message", () => {
  const raw =
    "PKCE code verifier not found in storage. This can happen if the auth flow was initiated in a different browser or device, or if the storage was cleared.";
  const message = verifyErrorMessage(raw);
  assert.match(message, /same browser/i);
  assert.doesNotMatch(message, /pkce|verifier|storage/i);
});

test("expired links keep the existing recovery message", () => {
  assert.match(verifyErrorMessage("Email link is invalid or has expired"), /expired/i);
});

test("generic invalid links keep the existing message", () => {
  assert.match(verifyErrorMessage("Invalid token"), /invalid or already used/i);
});

test("plain auth errors still pass through the mapping", () => {
  assert.match(authErrorMessage("Invalid login credentials"), /incorrect email or password/i);
});
