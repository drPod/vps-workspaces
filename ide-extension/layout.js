'use strict';
const {createHash} = require('node:crypto');
function panes(node) {
  return node.pane ? [node.pane] : node.children.flatMap(panes);
}
// VS Code nested group orientations alternate. Flatten equal-direction splits.
function groups(node, direction) {
  if (node.pane) return [{size: 1}];
  if (node.direction !== direction) return [{size: 1, groups: groups(node, node.direction)}];
  return node.children.flatMap((child, i) =>
    groups(child, direction).map(g => ({...g, size: g.size * (i ? 1-node.split : node.split)})));
}
function urlFor(doc, surface) {
  const u = new URL(surface.url);
  if (['localhost', '127.0.0.1', '[::1]'].includes(u.hostname)) {
    // Match model.origin: preserve explicit default ports and hostname spelling.
    const match = surface.url.match(/^([^:]+):\/\/([^/?#]*)/);
    const origin = match[1].toLowerCase() + '://' + match[2];
    const hash = createHash('sha256').update(origin).digest('hex').slice(0, 10);
    return `https://b-${hash}.${doc.host}${u.pathname}${u.search}${u.hash}`;
  }
  return surface.url;
}
module.exports = {panes, groups, urlFor};
