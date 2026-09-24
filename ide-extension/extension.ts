import * as vscode from 'vscode';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import {execFileSync} from 'node:child_process';
import {createHmac} from 'node:crypto';
import {createTerminals} from './vendor/workspace-layout/terminals';
import {SimpleBrowserView} from './vendor/simple-browser/src/simpleBrowserView';

const {panes, groups, urlFor} = require('./layout');

const root = path.join(os.homedir(), '.local/share/vps-workspaces');
const name = process.env.VWS_WORKSPACE;
const previews: SimpleBrowserView[] = [];
const ownedClients = new Map<number, string>();
// VS Code may retain remote PTYs after the extension host disconnects.
// Detach only this viewer's known tmux clients; never stop the shared session.
export function deactivate() {
  if (!ownedClients.size) return;
  try {
    const lines = execFileSync('/usr/bin/tmux', ['-L', 'vps-workspaces', 'list-clients', '-F', '#{client_pid}\t#{session_name}\t#{client_name}'], {encoding: 'utf8', timeout: 2000});
    for (const line of lines.trim().split('\n')) {
      const [pid, session, client] = line.split('\t');
      if (client && ownedClients.get(Number(pid)) === session) {
        execFileSync('/usr/bin/tmux', ['-L', 'vps-workspaces', 'detach-client', '-t', client], {timeout: 2000});
      }
    }
  } catch { /* The tmux client may already have disconnected. */ }
  ownedClients.clear();
}
function load() {
  if (!name || !/^[a-z][a-z0-9-]{0,47}$/.test(name)) throw Error('No VPS workspace configured');
  return JSON.parse(fs.readFileSync(path.join(root, name + '.json'), 'utf8'));
}
export async function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('VPS Workspaces');
  context.subscriptions.push(output);
  const report = (error: any) => {output.appendLine(String(error.stack || error)); vscode.window.showErrorMessage(String(error.message || error));};
  async function open() {
    const doc = load();
    if (!vscode.workspace.isTrusted) return;
    await vscode.commands.executeCommand('workbench.action.closeAuxiliaryBar');
    const direction = doc.layout.direction || 'horizontal';
    await vscode.commands.executeCommand('vscode.setEditorLayout', {
      orientation: direction === 'horizontal' ? 0 : 1,
      groups: groups(doc.layout, direction)
    });
    for (const p of previews.splice(0)) p.dispose();
    for (const [index, pane] of panes(doc.layout).entries()) {
      const ordered = pane.surfaces.filter((_: any, i: number) => i !== (pane.selected || 0));
      ordered.push(pane.surfaces[pane.selected || 0]);
      for (const surface of ordered) {
        const column = index + 1;
        if (surface.type === 'terminal') {
          const title = `${doc.name}: ${surface.id}`;
          const existing = new Set(vscode.window.terminals);
          await createTerminals([{
            name: title, shellPath: '/usr/bin/tmux',
            shellArgs: ['-L', 'vps-workspaces', '-u', 'attach-session', '-t', '=' + surface.session],
            location: {viewColumn: column, preserveFocus: true}, isTransient: true
          }]);
          for (const terminal of vscode.window.terminals) {
            if (!existing.has(terminal)) {
              context.subscriptions.push(terminal);
              terminal.processId.then(pid => {if (pid) ownedClients.set(pid, surface.session);});
            }
          }
        } else {
          const preview = SimpleBrowserView.create(context.extensionUri, urlFor(doc, surface), {viewColumn: column, preserveFocus: true});
          preview.setTitle(surface.title || surface.id);
          previews.push(preview);
        }
      }
    }
    output.appendLine(`Opened ${doc.id} revision ${doc.revision}: ${panes(doc.layout).length} panes`);
  }
  context.subscriptions.push(vscode.commands.registerCommand('vpsWorkspaces.open', () => open().catch(report)));
  context.subscriptions.push(vscode.commands.registerCommand('vpsWorkspaces.share', async () => {
    const doc = load();
    const access = JSON.parse(fs.readFileSync(path.join(root, 'access.json'), 'utf8'));
    const key = createHmac('sha256', access.key).update('share-link:' + doc.id).digest('hex');
    await vscode.env.clipboard.writeText(`https://${doc.host}/#key=${key}`);
    vscode.window.showInformationMessage('Sharing link copied');
  }));
  context.subscriptions.push({dispose: () => previews.splice(0).forEach(p => p.dispose())});
  if (name) await open().catch(report);
}
