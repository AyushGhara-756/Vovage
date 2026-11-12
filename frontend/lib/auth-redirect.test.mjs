import test from "node:test";
import assert from "node:assert/strict";
import { authCallbackUrl, verificationResendOptions } from "./auth-redirect.ts";

test("authCallbackUrl points at the callback and encodes next", () => {
  assert.equal(
    authCallbackUrl("http://localhost:3000", "/profile"),
    "http://localhost:3000/auth/callback?next=%2Fprofile",
  );
  assert.equal(
    authCallbackUrl("https://vovage.example", "/profile?tab=saves"),
    "https://vovage.example/auth/callback?next=%2Fprofile%3Ftab%3Dsaves",
  );
});

test("resent verification emails go through the callback", () => {
  const options = verificationResendOptions("user@example.com", "http://localhost:3000");
  assert.equal(options.type, "signup");
  assert.equal(options.email, "user@example.com");
  assert.equal(
    options.options.emailRedirectTo,
    "http://localhost:3000/auth/callback?next=%2Fprofile",
  );
});
