var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __commonJS = (cb, mod) => function __require() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};
var __export = (target, all) => {
  for (var name2 in all)
    __defProp(target, name2, { get: all[name2], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// layout.js
var require_layout = __commonJS({
  "layout.js"(exports2, module2) {
    "use strict";
    var { createHash } = require("node:crypto");
    function panes2(node) {
      return node.pane ? [node.pane] : node.children.flatMap(panes2);
    }
    function groups2(node, direction) {
      if (node.pane) return [{ size: 1 }];
      if (node.direction !== direction) return [{ size: 1, groups: groups2(node, node.direction) }];
      return node.children.flatMap((child, i) => groups2(child, direction).map((g) => ({ ...g, size: g.size * (i ? 1 - node.split : node.split) })));
    }
    function urlFor2(doc, surface) {
      const u = new URL(surface.url);
      if (["localhost", "127.0.0.1", "[::1]"].includes(u.hostname)) {
        const match = surface.url.match(/^([^:]+):\/\/([^/?#]*)/);
        const origin = match[1].toLowerCase() + "://" + match[2];
        const hash = createHash("sha256").update(origin).digest("hex").slice(0, 10);
        return `https://b-${hash}.${doc.host}${u.pathname}${u.search}${u.hash}`;
      }
      return surface.url;
    }
    module2.exports = { panes: panes2, groups: groups2, urlFor: urlFor2 };
  }
});

// extension.ts
var extension_exports = {};
__export(extension_exports, {
  activate: () => activate,
  deactivate: () => deactivate
});
module.exports = __toCommonJS(extension_exports);
var vscode3 = __toESM(require("vscode"));
var fs = __toESM(require("node:fs"));
var path = __toESM(require("node:path"));
var os = __toESM(require("node:os"));
var import_node_child_process = require("node:child_process");
var import_node_crypto = require("node:crypto");

// vendor/workspace-layout/terminals.ts
var vscode = __toESM(require("vscode"));
var COLOR_PREFIX = "terminal.ansi";
function prepareTerminal(config) {
  if (config.color && !config.color.startsWith(COLOR_PREFIX)) {
    const color = config.color.charAt(0).toUpperCase() + config.color.slice(1);
    const themeColor = `${COLOR_PREFIX}${color}`;
    config.color = new vscode.ThemeColor(themeColor);
  }
  if (config.icon) {
    config.iconPath = new vscode.ThemeIcon(config.icon);
  }
}
function initializeTerminal(terminal, config) {
  if (config.command) {
    terminal.sendText(config.command);
  }
}
async function createTerminal(config) {
  prepareTerminal(config);
  const existing = vscode.window.terminals.find((t) => t.name === config.name);
  if (existing) return existing;
  const terminal = vscode.window.createTerminal(config);
  initializeTerminal(terminal, config);
  return terminal;
}
async function createTerminals(terminals) {
  let activeTerminal;
  for (let terminalGroup of terminals) {
    if (Array.isArray(terminalGroup)) {
      terminalGroup.reverse();
      let terminal = terminalGroup.pop();
      if (typeof terminal === "string") {
        terminal = { command: terminal };
      }
      let parentTerminal = await createTerminal(terminal);
      if (!activeTerminal || terminal.active) {
        activeTerminal = parentTerminal;
      }
      let splitTerminal;
      while (splitTerminal = terminalGroup.pop()) {
        if (typeof splitTerminal === "string") {
          splitTerminal = {
            command: splitTerminal,
            location: { parentTerminal }
          };
        } else {
          splitTerminal.location = {
            parentTerminal
          };
        }
        parentTerminal = await createTerminal(splitTerminal);
        if (splitTerminal.active) {
          activeTerminal = parentTerminal;
        }
      }
    } else if (typeof terminalGroup === "string") {
      const terminal = await createTerminal({ command: terminalGroup });
      if (!activeTerminal) {
        activeTerminal = terminal;
      }
    } else {
      const terminal = await createTerminal(terminalGroup);
      if (!activeTerminal || terminalGroup.active) {
        activeTerminal = terminal;
      }
    }
  }
  if (activeTerminal) {
    activeTerminal.show(true);
  }
}

// vendor/simple-browser/src/simpleBrowserView.ts
var vscode2 = __toESM(require("vscode"));

// vendor/simple-browser/src/dispose.ts
function disposeAll(disposables) {
  while (disposables.length) {
    const item = disposables.pop();
    item?.dispose();
  }
}
var Disposable = class {
  _isDisposed = false;
  _disposables = [];
  dispose() {
    if (this._isDisposed) {
      return;
    }
    this._isDisposed = true;
    disposeAll(this._disposables);
  }
  _register(value) {
    if (this._isDisposed) {
      value.dispose();
    } else {
      this._disposables.push(value);
    }
    return value;
  }
  get isDisposed() {
    return this._isDisposed;
  }
};

// vendor/simple-browser/src/uuid.ts
function generateUuid() {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID.bind(crypto)();
  }
  const _data = new Uint8Array(16);
  const _hex = [];
  for (let i2 = 0; i2 < 256; i2++) {
    _hex.push(i2.toString(16).padStart(2, "0"));
  }
  crypto.getRandomValues(_data);
  _data[6] = _data[6] & 15 | 64;
  _data[8] = _data[8] & 63 | 128;
  let i = 0;
  let result = "";
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += "-";
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += "-";
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += "-";
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += "-";
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  result += _hex[_data[i++]];
  return result;
}

// vendor/simple-browser/src/simpleBrowserView.ts
var SimpleBrowserView = class _SimpleBrowserView extends Disposable {
  constructor(extensionUri, url, webviewPanel) {
    super();
    this.extensionUri = extensionUri;
    this._webviewPanel = this._register(webviewPanel);
    this._webviewPanel.webview.options = _SimpleBrowserView.getWebviewOptions(extensionUri);
    this._register(this._webviewPanel.webview.onDidReceiveMessage((e) => {
      switch (e.type) {
        case "openExternal":
          try {
            const url2 = vscode2.Uri.parse(e.url);
            vscode2.env.openExternal(url2);
          } catch {
          }
          break;
      }
    }));
    this._register(this._webviewPanel.onDidDispose(() => {
      this.dispose();
    }));
    this._register(vscode2.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("simpleBrowser.focusLockIndicator.enabled")) {
        const configuration = vscode2.workspace.getConfiguration("simpleBrowser");
        this._webviewPanel.webview.postMessage({
          type: "didChangeFocusLockIndicatorEnabled",
          focusLockEnabled: configuration.get("focusLockIndicator.enabled", true)
        });
      }
    }));
    this.show(url);
  }
  static viewType = "simpleBrowser.view";
  static title = vscode2.l10n.t("Simple Browser");
  static getWebviewLocalResourceRoots(extensionUri) {
    return [
      vscode2.Uri.joinPath(extensionUri, "media")
    ];
  }
  static getWebviewOptions(extensionUri) {
    return {
      enableScripts: true,
      enableForms: true,
      localResourceRoots: _SimpleBrowserView.getWebviewLocalResourceRoots(extensionUri)
    };
  }
  _webviewPanel;
  _onDidDispose = this._register(new vscode2.EventEmitter());
  onDispose = this._onDidDispose.event;
  static create(extensionUri, url, showOptions) {
    const webview = vscode2.window.createWebviewPanel(_SimpleBrowserView.viewType, _SimpleBrowserView.title, {
      viewColumn: showOptions?.viewColumn ?? vscode2.ViewColumn.Active,
      preserveFocus: showOptions?.preserveFocus
    }, {
      retainContextWhenHidden: true,
      ..._SimpleBrowserView.getWebviewOptions(extensionUri)
    });
    return new _SimpleBrowserView(extensionUri, url, webview);
  }
  static restore(extensionUri, url, webviewPanel) {
    return new _SimpleBrowserView(extensionUri, url, webviewPanel);
  }
  // Adapter addition: distinguish multiple saved browser panes in editor tabs.
  setTitle(title) {
    this._webviewPanel.title = title;
  }
  dispose() {
    this._onDidDispose.fire();
    super.dispose();
  }
  show(url, options) {
    this._webviewPanel.webview.html = this.getHtml(url);
    this._webviewPanel.reveal(options?.viewColumn, options?.preserveFocus);
  }
  getHtml(url) {
    const configuration = vscode2.workspace.getConfiguration("simpleBrowser");
    const nonce = generateUuid();
    const mainJs = this.extensionResourceUrl("media", "index.js");
    const mainCss = this.extensionResourceUrl("media", "main.css");
    const codiconsUri = this.extensionResourceUrl("media", "codicon.css");
    return (
      /* html */
      `<!DOCTYPE html>
			<html>
			<head>
				<meta http-equiv="Content-type" content="text/html;charset=UTF-8">

				<meta http-equiv="Content-Security-Policy" content="
					default-src 'none';
					font-src data:;
					style-src ${this._webviewPanel.webview.cspSource};
					script-src 'nonce-${nonce}';
					frame-src *;
					">

				<meta id="simple-browser-settings" data-settings="${escapeAttribute(JSON.stringify({
        url,
        focusLockEnabled: configuration.get("focusLockIndicator.enabled", true)
      }))}">

				<link rel="stylesheet" type="text/css" href="${mainCss}">
				<link rel="stylesheet" type="text/css" href="${codiconsUri}">
			</head>
			<body>
				<header class="header">
					<nav class="controls">
						<button
							title="${vscode2.l10n.t("Back")}"
							class="back-button icon"><i class="codicon codicon-arrow-left"></i></button>

						<button
							title="${vscode2.l10n.t("Forward")}"
							class="forward-button icon"><i class="codicon codicon-arrow-right"></i></button>

						<button
							title="${vscode2.l10n.t("Reload")}"
							class="reload-button icon"><i class="codicon codicon-refresh"></i></button>
					</nav>

					<input class="url-input" type="text">

					<nav class="controls">
						<button
							title="${vscode2.l10n.t("Open in browser")}"
							class="open-external-button icon"><i class="codicon codicon-link-external"></i></button>
					</nav>
				</header>
				<div class="content">
					<div class="iframe-focused-alert">${vscode2.l10n.t("Focus Lock")}</div>
					<iframe sandbox="allow-scripts allow-forms allow-same-origin allow-downloads"></iframe>
				</div>

				<script src="${mainJs}" nonce="${nonce}"></script>
			</body>
			</html>`
    );
  }
  extensionResourceUrl(...parts) {
    return this._webviewPanel.webview.asWebviewUri(vscode2.Uri.joinPath(this.extensionUri, ...parts));
  }
};
function escapeAttribute(value) {
  return value.toString().replace(/"/g, "&quot;");
}

// extension.ts
var { panes, groups, urlFor } = require_layout();
var root = path.join(os.homedir(), ".local/share/vps-workspaces");
var name = process.env.VWS_WORKSPACE;
var previews = [];
var ownedClients = /* @__PURE__ */ new Map();
var ownedHapi = /* @__PURE__ */ new Map();
function processStart(pid) {
  try {
    return fs.readFileSync(`/proc/${pid}/stat`, "utf8").split(") ")[1].split(" ")[19];
  } catch {
    return void 0;
  }
}
function deactivate() {
  for (const [pid, start] of ownedHapi) {
    if (processStart(pid) === start) {
      try {
        process.kill(pid, "SIGHUP");
      } catch {
      }
    }
  }
  ownedHapi.clear();
  if (!ownedClients.size) return;
  try {
    const lines = (0, import_node_child_process.execFileSync)("/usr/bin/tmux", ["-L", "vps-workspaces", "list-clients", "-F", "#{client_pid}	#{session_name}	#{client_name}"], { encoding: "utf8", timeout: 2e3 });
    for (const line of lines.trim().split("\n")) {
      const [pid, session, client] = line.split("	");
      if (client && ownedClients.get(Number(pid)) === session) {
        (0, import_node_child_process.execFileSync)("/usr/bin/tmux", ["-L", "vps-workspaces", "detach-client", "-t", client], { timeout: 2e3 });
      }
    }
  } catch {
  }
  ownedClients.clear();
}
function load() {
  if (!name || !/^[a-z][a-z0-9-]{0,47}$/.test(name)) throw Error("No VPS workspace configured");
  return JSON.parse(fs.readFileSync(path.join(root, name + ".json"), "utf8"));
}
async function activate(context) {
  const output = vscode3.window.createOutputChannel("VPS Workspaces");
  context.subscriptions.push(output);
  const report = (error) => {
    output.appendLine(String(error.stack || error));
    vscode3.window.showErrorMessage(String(error.message || error));
  };
  async function open() {
    const doc = load();
    if (!vscode3.workspace.isTrusted) return;
    await vscode3.commands.executeCommand("workbench.action.closeAuxiliaryBar");
    const direction = doc.layout.direction || "horizontal";
    await vscode3.commands.executeCommand("vscode.setEditorLayout", {
      orientation: direction === "horizontal" ? 0 : 1,
      groups: groups(doc.layout, direction)
    });
    for (const p of previews.splice(0)) p.dispose();
    const restored = vscode3.window.tabGroups.all.flatMap((group) => group.tabs).filter((tab) => tab.input instanceof vscode3.TabInputWebview && tab.input.viewType.includes("simpleBrowser.view"));
    if (restored.length) await vscode3.window.tabGroups.close(restored, true);
    for (const [index, pane] of panes(doc.layout).entries()) {
      const ordered = pane.surfaces.filter((_, i) => i !== (pane.selected || 0));
      ordered.push(pane.surfaces[pane.selected || 0]);
      for (const surface of ordered) {
        const column = index + 1;
        if (surface.type === "terminal") {
          const title = `${doc.name}: ${surface.id}`;
          const existing = new Set(vscode3.window.terminals);
          await createTerminals([{
            name: title,
            shellPath: surface.hapi_session ? "/usr/bin/python3" : "/usr/bin/tmux",
            shellArgs: surface.hapi_session ? [path.join(root, "app/remote.py"), "attach", doc.id, surface.id] : ["-L", "vps-workspaces", "-u", "attach-session", "-t", "=" + surface.session],
            location: { viewColumn: column, preserveFocus: true },
            isTransient: true
          }]);
          for (const terminal of vscode3.window.terminals) {
            if (!existing.has(terminal)) {
              context.subscriptions.push(terminal);
              terminal.processId.then((pid) => {
                if (!pid) return;
                if (surface.hapi_session) {
                  const start = processStart(pid);
                  if (start) ownedHapi.set(pid, start);
                } else ownedClients.set(pid, surface.session);
              });
            }
          }
        } else {
          const preview = SimpleBrowserView.create(context.extensionUri, urlFor(doc, surface), { viewColumn: column, preserveFocus: true });
          preview.setTitle(surface.title || surface.id);
          previews.push(preview);
        }
      }
    }
    output.appendLine(`Opened ${doc.id} revision ${doc.revision}: ${panes(doc.layout).length} panes`);
  }
  context.subscriptions.push(vscode3.commands.registerCommand("vpsWorkspaces.hapi", async () => {
    try {
      const url = (0, import_node_child_process.execFileSync)("/usr/bin/python3", [path.join(root, "app/hapi-workspace.py"), "link"], { encoding: "utf8", timeout: 5e3 }).trim();
      await vscode3.env.openExternal(vscode3.Uri.parse(url));
    } catch (error) {
      report(error);
    }
  }));
  if (fs.existsSync(path.join(root, "hapi/install.json"))) {
    const status = vscode3.window.createStatusBarItem(vscode3.StatusBarAlignment.Left, 90);
    status.text = "$(comment-discussion) HAPI Sessions";
    status.command = "vpsWorkspaces.hapi";
    status.tooltip = "Open the HAPI session app";
    status.show();
    context.subscriptions.push(status);
  }
  context.subscriptions.push(vscode3.commands.registerCommand("vpsWorkspaces.open", () => open().catch(report)));
  context.subscriptions.push(vscode3.commands.registerCommand("vpsWorkspaces.share", async () => {
    const doc = load();
    const access = JSON.parse(fs.readFileSync(path.join(root, "access.json"), "utf8"));
    const key = (0, import_node_crypto.createHmac)("sha256", access.key).update("share-link:" + doc.id).digest("hex");
    await vscode3.env.clipboard.writeText(`https://${doc.host}/#key=${key}`);
    vscode3.window.showInformationMessage("Sharing link copied");
  }));
  context.subscriptions.push({ dispose: () => previews.splice(0).forEach((p) => p.dispose()) });
  if (name) await open().catch(report);
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  activate,
  deactivate
});
