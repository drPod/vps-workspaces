const { test } = require("node:test");
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const { panes, groups, urlFor } = require("./.test-build/layout.cjs");
const leaf = (id) => ({ pane: { surfaces: [{ id }] } });
const split = (direction, ratio, left, right) => ({
  direction,
  split: ratio,
  children: [left, right],
});
test("mixed splits preserve proportions and pane order", () => {
  const tree = split(
    "horizontal",
    0.6,
    leaf("term"),
    split("vertical", 0.3, leaf("report"), leaf("app")),
  );
  assert.deepEqual(groups(tree, "horizontal"), [
    { size: 0.6 },
    { size: 0.4, groups: [{ size: 0.3 }, { size: 0.7 }] },
  ]);
  assert.deepEqual(
    panes(tree).map((p) => p.surfaces[0].id),
    ["term", "report", "app"],
  );
});
test("adjacent equal orientations flatten without changing proportions", () => {
  const tree = split(
    "horizontal",
    0.5,
    split("horizontal", 0.2, leaf("a"), leaf("b")),
    leaf("c"),
  );
  assert.deepEqual(groups(tree, "horizontal"), [
    { size: 0.1 },
    { size: 0.4 },
    { size: 0.5 },
  ]);
});
test("explicit default port is hashed the same way as the Python gateway", () => {
  const hash = createHash("sha256")
    .update("http://localhost:80")
    .digest("hex")
    .slice(0, 10);
  assert.equal(
    urlFor(
      { host: "demo.example" },
      { url: "http://localhost:80/report?q=1#section" },
    ),
    `https://b-${hash}.demo.example/report?q=1#section`,
  );
});
test("external pages retain their original URL", () => {
  assert.equal(
    urlFor({ host: "demo.example" }, { url: "https://example.com/docs" }),
    "https://example.com/docs",
  );
});

test("workspace validation rejects invalid tabs and incomplete terminals", () => {
  const { workspaceSchema } = require("./.test-build/layout.cjs");
  const doc = {
    id: "demo",
    name: "Demo",
    host: "demo.example",
    revision: 1,
    layout: {
      pane: {
        surfaces: [{ id: "agent", type: "terminal", session: "demo-agent" }],
        selected: 0,
      },
    },
  };
  assert.equal(
    workspaceSchema.parse(doc).layout.pane.surfaces[0].session,
    "demo-agent",
  );
  const invalid = structuredClone(doc);
  invalid.layout.pane.selected = 1;
  assert.equal(workspaceSchema.safeParse(invalid).success, false);
  delete invalid.layout.pane.selected;
  delete invalid.layout.pane.surfaces[0].session;
  assert.equal(workspaceSchema.safeParse(invalid).success, false);
});
test("browser schema rejects credentials and non-web schemes", () => {
  const { surfaceSchema } = require("./.test-build/layout.cjs");
  for (const url of [
    "file:///etc/passwd",
    "https://user:password@example.com/",
  ]) {
    assert.equal(
      surfaceSchema.safeParse({ id: "app", type: "browser", url }).success,
      false,
    );
  }
});
