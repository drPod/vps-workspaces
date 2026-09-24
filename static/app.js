'use strict';
function render(node) {
  const element = document.createElement('div');
  if (node.pane) {
    element.className = 'pane';
    const tabs = document.createElement('div'), view = document.createElement('div');
    tabs.className = 'tabs'; view.className = 'view'; element.append(tabs, view);
    for (const [i, surface] of node.pane.surfaces.entries()) {
      const button = document.createElement('button'), frame = document.createElement('iframe');
      button.textContent = surface.title || surface.id; frame.title = button.textContent;
      frame.src = surface.web_url; frame.allow = 'clipboard-read; clipboard-write';
      frame.referrerPolicy = 'no-referrer'; frame.hidden = i !== (node.pane.selected || 0);
      button.classList.toggle('active', !frame.hidden);
      button.onclick = () => { for (const f of view.children) f.hidden = f !== frame; for (const b of tabs.children) b.classList.toggle('active', b === button); };
      tabs.append(button); view.append(frame);
    }
    return element;
  }
  element.className = 'split ' + node.direction;
  const children = node.children.map(child => { const cell = document.createElement('div'); cell.className = 'cell'; cell.append(render(child)); element.append(cell); return cell; });
  requestAnimationFrame(() => Split(children, {direction: node.direction, sizes: [100 * node.split, 100 * (1-node.split)], minSize: 80, gutterSize: 5,
    onDragStart: () => document.body.classList.add('resizing'), onDragEnd: () => document.body.classList.remove('resizing')}));
  return element;
}
(async () => {
  try { const r = await fetch('/workspace.json'); if (!r.ok) throw Error('Could not load workspace'); const doc = await r.json(); document.title = doc.name; document.querySelector('#name').textContent = doc.name; document.querySelector('#workspace').append(render(doc.layout)); }
  catch(e) { document.querySelector('#error').textContent = e.message; }
})();
document.querySelector('#reload').onclick = () => location.reload();

document.querySelector('#share').onclick = async () => {
  const button = document.querySelector('#share');
  try {
    const response = await fetch('/share-link');
    if (!response.ok) throw Error('Could not retrieve sharing link');
    const {url} = await response.json();
    try { await navigator.clipboard.writeText(url); button.textContent = 'Copied'; }
    catch { window.prompt('Copy this sharing link:', url); }
    setTimeout(() => { button.textContent = 'Copy sharing link'; }, 2000);
  } catch(error) { document.querySelector('#error').textContent = error.message; }
};
