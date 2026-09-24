import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { execFileSync } from "node:child_process";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createTerminals } from "./vendor/workspace-layout/terminals";
import { SimpleBrowserView } from "./vendor/simple-browser/src/simpleBrowserView";

import { panes, groups, urlFor, workspaceSchema } from "./layout";
const execute = promisify(execFile);

const root = path.join(os.homedir(), ".local/share/vps-workspaces");
const name = process.env.VWS_WORKSPACE;
const previews: SimpleBrowserView[] = [];
const ownedClients = new Map<number, { session: string; start: string }>();
let stopped = false;
const ownedHapi = new Map<number, string>();
function processStart(pid: number): string | undefined {
  try {
    return fs
      .readFileSync(`/proc/${pid}/stat`, "utf8")
      .split(") ")[1]
      .split(" ")[19];
  } catch {
    return undefined;
  }
}
// Disconnect this viewer's PTYs without stopping the shared agent.
export function deactivate() {
  stopped = true;
  for (const [pid, start] of ownedHapi) {
    if (processStart(pid) === start) {
      try {
        process.kill(pid, "SIGHUP");
      } catch {
        /* Already detached. */
      }
    }
  }
  ownedHapi.clear();
  if (!ownedClients.size) return;
  try {
    const lines = execFileSync(
      "/usr/bin/tmux",
      [
        "-L",
        "vps-workspaces",
        "list-clients",
        "-F",
        "#{client_pid}\t#{session_name}\t#{client_name}",
      ],
      { encoding: "utf8", timeout: 2000 },
    );
    for (const line of lines.trim().split("\n")) {
      const [pid, session, client] = line.split("\t");
      const owned = ownedClients.get(Number(pid));
      if (
        client &&
        owned?.session === session &&
        processStart(Number(pid)) === owned.start
      ) {
        execFileSync(
          "/usr/bin/tmux",
          ["-L", "vps-workspaces", "detach-client", "-t", client],
          { timeout: 2000 },
        );
      }
    }
  } catch {
    /* The tmux client may already have disconnected. */
  }
  ownedClients.clear();
}
function load() {
  if (!name || !/^[a-z][a-z0-9-]{0,47}$/.test(name))
    throw Error("No VPS workspace configured");
  return workspaceSchema.parse(
    JSON.parse(fs.readFileSync(path.join(root, name + ".json"), "utf8")),
  );
}
export async function activate(context: vscode.ExtensionContext) {
  stopped = false;
  const output = vscode.window.createOutputChannel("VPS Workspaces");
  context.subscriptions.push(output);
  const report = (error: unknown) => {
    output.appendLine(
      error instanceof Error ? error.stack || error.message : String(error),
    );
    void vscode.window.showErrorMessage(
      error instanceof Error ? error.message : String(error),
    );
  };
  async function open() {
    const doc = load();
    if (!vscode.workspace.isTrusted) return;
    await vscode.commands.executeCommand("workbench.action.closeAuxiliaryBar");
    const direction =
      "direction" in doc.layout ? doc.layout.direction : "horizontal";
    await vscode.commands.executeCommand("vscode.setEditorLayout", {
      orientation: direction === "horizontal" ? 0 : 1,
      groups: groups(doc.layout, direction),
    });
    for (const p of previews.splice(0)) p.dispose();
    const restored = vscode.window.tabGroups.all
      .flatMap((group) => group.tabs)
      .filter(
        (tab) =>
          tab.input instanceof vscode.TabInputWebview &&
          tab.input.viewType.includes("simpleBrowser.view"),
      );
    if (restored.length) await vscode.window.tabGroups.close(restored, true);
    for (const [index, pane] of panes(doc.layout).entries()) {
      let revealSelected: (() => void) | undefined;
      for (const [surfaceIndex, surface] of pane.surfaces.entries()) {
        const column = index + 1;
        if (surface.type === "terminal") {
          const title = `${doc.name}: ${surface.id}`;
          const existing = new Set(vscode.window.terminals);
          await createTerminals([
            {
              name: title,
              shellPath: surface.hapi_session
                ? "/usr/bin/python3"
                : "/usr/bin/tmux",
              shellArgs: surface.hapi_session
                ? [
                    path.join(root, "app/remote.py"),
                    "attach",
                    doc.id,
                    surface.id,
                  ]
                : [
                    "-L",
                    "vps-workspaces",
                    "-u",
                    "attach-session",
                    "-t",
                    "=" + surface.session,
                  ],
              location: { viewColumn: column, preserveFocus: true },
              isTransient: true,
            },
          ]);
          if (surfaceIndex === pane.selected) {
            const terminal = vscode.window.terminals.find(
              (t) => t.name === title,
            );
            if (terminal) revealSelected = () => terminal.show(true);
          }
          for (const terminal of vscode.window.terminals) {
            if (!existing.has(terminal)) {
              context.subscriptions.push(terminal);
              terminal.processId.then((pid) => {
                if (!pid || terminal.exitStatus !== undefined) return;
                if (stopped) {
                  terminal.dispose();
                  return;
                }
                const start = processStart(pid);
                if (!start) return;
                if (surface.hapi_session) ownedHapi.set(pid, start);
                else ownedClients.set(pid, { session: surface.session, start });
              });
            }
          }
        } else {
          const preview = SimpleBrowserView.create(
            context.extensionUri,
            urlFor(doc, surface),
            { viewColumn: column, preserveFocus: true },
          );
          preview.setTitle(surface.title || surface.id);
          previews.push(preview);
          if (surfaceIndex === pane.selected) {
            revealSelected = () =>
              preview.show(urlFor(doc, surface), {
                viewColumn: column,
                preserveFocus: true,
              });
          }
        }
      }
      revealSelected?.();
    }
    output.appendLine(
      `Opened ${doc.id} revision ${doc.revision}: ${panes(doc.layout).length} panes`,
    );
  }
  context.subscriptions.push(
    vscode.commands.registerCommand("vpsWorkspaces.hapi", async () => {
      try {
        const { stdout } = await execute(
          "/usr/bin/python3",
          [path.join(root, "app/workspace.py"), "hapi", "link"],
          { encoding: "utf8", timeout: 5000 },
        );
        const url = stdout.trim();
        await vscode.env.openExternal(vscode.Uri.parse(url));
      } catch (error) {
        report(error);
      }
    }),
  );
  if (fs.existsSync(path.join(root, "hapi/install.json"))) {
    const status = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      90,
    );
    status.text = "$(comment-discussion) HAPI Sessions";
    status.command = "vpsWorkspaces.hapi";
    status.tooltip = "Open the HAPI session app";
    status.show();
    context.subscriptions.push(status);
  }
  context.subscriptions.push(
    vscode.commands.registerCommand("vpsWorkspaces.open", () =>
      open().catch(report),
    ),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("vpsWorkspaces.share", async () => {
      try {
        const doc = load();
        const { stdout } = await execute(
          "/usr/bin/python3",
          [path.join(root, "app/remote.py"), "link", doc.id],
          { encoding: "utf8", timeout: 5000 },
        );
        const url: unknown = JSON.parse(stdout);
        if (typeof url !== "string")
          throw new Error("Invalid sharing link response");
        await vscode.env.clipboard.writeText(url);
        void vscode.window.showInformationMessage("Sharing link copied");
      } catch (error) {
        report(error);
      }
    }),
  );
  context.subscriptions.push({
    dispose: () => previews.splice(0).forEach((p) => p.dispose()),
  });
  if (name) await open().catch(report);
}
