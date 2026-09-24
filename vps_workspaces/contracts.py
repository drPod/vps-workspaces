from __future__ import annotations

from typing import Any, Literal, TypedDict

JsonObject = dict[str, Any]


class SurfaceRequired(TypedDict):
    id: str
    type: Literal["terminal", "browser"]


class Surface(SurfaceRequired, total=False):
    title: str
    session: str
    cwd: str
    hapi_session: str
    url: str
    web_url: str


class Pane(TypedDict):
    surfaces: list[Surface]
    selected: int


class Layout(TypedDict, total=False):
    pane: Pane
    direction: Literal["horizontal", "vertical"]
    split: float
    children: list[Layout]


class WorkspaceRequired(TypedDict):
    id: str
    name: str
    layout: Layout


class Workspace(WorkspaceRequired, total=False):
    host: str
    revision: int
    saved_at: int
    ide_url: str


class NativeState(TypedDict):
    workspace: str
    revision: int
    bindings: dict[str, str]
    doc: Workspace


class Instance(NativeState, total=False):
    registry_name: str
    pending_surfaces: dict[str, Surface]
    autosave_error: str


class Access(TypedDict):
    key: str


class HapiMetadata(TypedDict, total=False):
    codexSessionId: str
    flavor: str
    name: str
    path: str
    host: str


class HapiSession(TypedDict):
    id: str
    active: bool
    metadata: HapiMetadata | None


class HapiConfig(TypedDict):
    host: str
    port: int
    token: str
    api_url: str


class BackupEntry(TypedDict, total=False):
    source: str
    snapshot: str
    error: str
    raw_files_preserved: bool


class BackupRequired(TypedDict):
    rsnapshot: str
    rsnapshot_config: str
    snapshot_root: str
    sqlite_stage: str
    exclude_file: str
    excludes: list[str]
    sqlite_roots: list[str]


class BackupConfig(BackupRequired, total=False):
    ssh_host: str
    remote_ready: str
