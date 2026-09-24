// Adapted from lostintangent/workspace-layout; see LICENSE and ../../NOTICE.md.
import * as vscode from "vscode";
import { GalleryTerminal, GalleryTerminalGroup } from "./types";

const COLOR_PREFIX = "terminal.ansi";

function prepareTerminal(config: GalleryTerminal): vscode.TerminalOptions {
  const {color, icon, ...options} = config;
  return {
    ...options,
    color: color ? new vscode.ThemeColor(color.startsWith(COLOR_PREFIX)
      ? color : `${COLOR_PREFIX}${color.charAt(0).toUpperCase()}${color.slice(1)}`) : undefined,
    iconPath: icon ? new vscode.ThemeIcon(icon) : options.iconPath,
  };
}

function initializeTerminal(
  terminal: vscode.Terminal,
  config: GalleryTerminal
) {
  if (config.command) {
    terminal.sendText(config.command);
  }
}

async function createTerminal(config: GalleryTerminal) {

  const existing = vscode.window.terminals.find(t => t.name === config.name);
  if (existing) return existing;
  const terminal = vscode.window.createTerminal(prepareTerminal(config));
  initializeTerminal(terminal, config);

  return terminal;
}

export async function createTerminals(terminals: GalleryTerminalGroup[]) {
    // Preserve existing terminals; resetting layout must not close user work.

  let activeTerminal: vscode.Terminal | undefined;
  for (let terminalGroup of terminals) {
    if (Array.isArray(terminalGroup)) {
      terminalGroup.reverse();

      let terminal = terminalGroup.pop()!;
      if (typeof terminal === "string") {
        terminal = { command: terminal };
      }

      let parentTerminal = await createTerminal(terminal);
      if (!activeTerminal || terminal.active) {
        activeTerminal = parentTerminal;
      }

      let splitTerminal: GalleryTerminal | string | undefined;
      while ((splitTerminal = terminalGroup.pop())) {
        if (typeof splitTerminal === "string") {
          splitTerminal = {
            command: splitTerminal,
            location: { parentTerminal },
          };
        } else {
          splitTerminal.location = {
            parentTerminal,
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
