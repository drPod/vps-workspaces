import { createHash } from "node:crypto";
import { z } from "zod";

const identifier = z.string().regex(/^[a-z][a-z0-9-]{0,47}$/);
const surfaceBase = z.object({ id: identifier, title: z.string().optional() });
export const surfaceSchema = z.discriminatedUnion("type", [
  surfaceBase.extend({
    type: z.literal("terminal"),
    session: identifier,
    cwd: z.string().optional(),
    codex_thread: z.uuid().optional(),
    hapi_session: z.uuid().optional(),
  }),
  surfaceBase.extend({
    type: z.literal("browser"),
    url: z.literal("about:blank").or(
      z.url().refine((value) => {
        const url = new URL(value);
        return (
          ["http:", "https:"].includes(url.protocol) &&
          !url.username &&
          !url.password
        );
      }),
    ),
  }),
]);
export type Surface = z.infer<typeof surfaceSchema>;
export type BrowserSurface = Extract<Surface, { type: "browser" }>;
const paneSchema = z
  .object({
    surfaces: z.array(surfaceSchema).min(1).max(32),
    selected: z.number().int().min(0).default(0),
  })
  .refine(
    (pane) => pane.selected < pane.surfaces.length,
    "Selected tab is out of range",
  );
export type Pane = z.infer<typeof paneSchema>;
export type Direction = "horizontal" | "vertical";
export type Layout =
  | { pane: Pane }
  | { direction: Direction; split: number; children: [Layout, Layout] };
const layoutSchema: z.ZodType<Layout> = z.lazy(() =>
  z.union([
    z.object({ pane: paneSchema }),
    z.object({
      direction: z.enum(["horizontal", "vertical"]),
      split: z.number().min(0.1).max(0.9).default(0.5),
      children: z.tuple([layoutSchema, layoutSchema]),
    }),
  ]),
);
export const workspaceSchema = z.object({
  id: identifier,
  name: z.string().min(1).max(200),
  host: z.string().min(1),
  revision: z.number().int().nonnegative(),
  layout: layoutSchema,
});
export type Workspace = z.infer<typeof workspaceSchema>;
export interface EditorGroup {
  size: number;
  groups?: EditorGroup[];
}

export function panes(node: Layout): Pane[] {
  return "pane" in node ? [node.pane] : node.children.flatMap(panes);
}

// VS Code nested group orientations alternate; equal-direction splits must flatten.
export function groups(node: Layout, direction: Direction): EditorGroup[] {
  if ("pane" in node) return [{ size: 1 }];
  if (node.direction !== direction)
    return [{ size: 1, groups: groups(node, node.direction) }];
  return node.children.flatMap((child, index) =>
    groups(child, direction).map((group) => ({
      ...group,
      size: group.size * (index ? 1 - node.split : node.split),
    })),
  );
}

export function urlFor(
  doc: Pick<Workspace, "host">,
  surface: Pick<BrowserSurface, "url">,
): string {
  const url = new URL(surface.url);
  if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    // Preserve explicit default ports to match Python's origin hash.
    const match = surface.url.match(/^([^:]+):\/\/([^/?#]*)/);
    if (!match) throw new Error("Invalid browser URL");
    const origin = match[1].toLowerCase() + "://" + match[2];
    const hash = createHash("sha256").update(origin).digest("hex").slice(0, 10);
    return `https://b-${hash}.${doc.host}${url.pathname}${url.search}${url.hash}`;
  }
  return surface.url;
}
