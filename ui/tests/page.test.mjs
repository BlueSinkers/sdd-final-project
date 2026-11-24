// The deployed page ships a strict Content Security Policy (ui/staticwebapp.config.json):
// no inline script, no inline style, no eval. These tests fail if the page ever
// starts needing any of those, so the policy cannot silently break the live page.

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const here = new URL("../", import.meta.url);
const read = (name) => readFileSync(new URL(name, here), "utf8");
const html = read("index.html");
const scripts = readdirSync(here).filter((name) => name.endsWith(".js"));

test("index.html has no inline script, no inline style and no inline event handlers", () => {
  assert.ok(!/<script(?![^>]*\bsrc=)[^>]*>/i.test(html), "inline <script>");
  assert.ok(!/<style/i.test(html), "inline <style>");
  assert.ok(!/\sstyle\s*=/i.test(html), "style attribute");
  assert.ok(!/\son[a-z]+\s*=/i.test(html), "inline event handler");
});

test("no script uses innerHTML, eval or the style property", () => {
  for (const name of scripts) {
    const code = read(name).replace(/^\s*\/\/.*$/gm, "");
    assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|\beval\(|new Function|\.style\b/.test(code), name);
  }
});

test("the policy allows what the page needs and nothing wider", () => {
  const config = JSON.parse(read("staticwebapp.config.json"));
  const policy = config.globalHeaders["Content-Security-Policy"];
  assert.match(policy, /default-src 'self'/);
  assert.match(policy, /script-src 'self'(;|$)/);
  assert.match(policy, /connect-src 'self' https:\/\/\*\.azurecontainerapps\.io/);
  assert.match(policy, /frame-ancestors 'none'/);
  assert.ok(!/unsafe-inline|unsafe-eval/.test(policy));
});

test("every script the page loads exists", () => {
  for (const [, src] of html.matchAll(/<script[^>]*\ssrc="([^"]+)"/g)) {
    assert.ok(scripts.includes(src), `${src} is missing`);
  }
});
