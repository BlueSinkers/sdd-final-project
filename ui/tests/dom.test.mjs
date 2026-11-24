// Tests for ui/dom.js: formatting helpers, and that text never becomes markup.

import assert from "node:assert/strict";
import { test } from "node:test";

import { CONDITION_LABELS, el, formatEuros } from "../dom.js";

// A tiny stand-in for the browser's DOM: enough to see how el() builds a node.
class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.attributes = {};
    this.children = [];
    this.listeners = {};
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  set innerHTML(value) {
    throw new Error(`innerHTML must never be used (got ${value})`);
  }
}
globalThis.Node = FakeNode;
globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createTextNode: (text) => ({ text: String(text) }),
};

test("formats euros the Irish way", () => {
  assert.equal(formatEuros(35), "€35.00");
  assert.equal(formatEuros(0.74), "€0.74");
});

test("every condition from 1 to 5 has a label", () => {
  assert.deepEqual(Object.keys(CONDITION_LABELS), ["1", "2", "3", "4", "5"]);
});

test("text from a service goes in as text, so markup in a title stays inert", () => {
  const node = el("strong", { text: "<img src=x onerror=alert(1)>" });
  assert.equal(node.textContent, "<img src=x onerror=alert(1)>");
  assert.equal(node.children.length, 0);
});

test("attributes: class, true, false and null", () => {
  const node = el("button", { class: "btn", disabled: true, hidden: false, title: null, type: "button" });
  assert.equal(node.className, "btn");
  assert.equal(node.attributes.disabled, "");
  assert.equal(node.attributes.type, "button");
  assert.ok(!("hidden" in node.attributes));
  assert.ok(!("title" in node.attributes));
});

test("on* attributes become event listeners", () => {
  const handler = () => {};
  assert.equal(el("button", { onclick: handler }).listeners.click, handler);
});

test("children: nodes are kept, strings become text, empty values are skipped", () => {
  const child = el("span");
  const node = el("p", {}, child, "hello", null, false, undefined, [el("i"), "x"]);
  assert.equal(node.children.length, 4);
  assert.equal(node.children[0], child);
  assert.deepEqual(node.children[1], { text: "hello" });
});
