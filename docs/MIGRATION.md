# Moving or retiring a VPS

A synchronized source checkout is not a complete server backup. Keep installation-specific
inventories, credentials and recovery archives outside this repository; record their paths
in the private operations runbook referenced by `AGENTS.md`.

## Inventory and preserve

- Inspect mounted filesystems before selecting backup roots. A root-filesystem archive can
  omit a separately mounted home directory or attached data volume.
- Include user homes and hidden state, external research jobs, deployment directories,
  systemd units, timers, SSH configuration, temporary worktrees and application storage.
- Preserve agent histories separately from source synchronization. Do not merge live SQLite
  files through Mutagen or overwrite newer conversations with an older machine's database.
- Export PostgreSQL with its native tools and prepare SQLite copies with the backup API.
  Preserve Docker images, volume data and relevant writable container filesystems.
- Record exclusions and errors. Virtual kernel filesystems and live sockets cannot be restored
  as saved application data. File archives are not bootable disk images.
- Verify archive checksums and readability, test database restores, and retain copies outside
  the machine being retired. Keep backups unencrypted unless the operator requests otherwise.

## Cut over and verify

1. Compare application data against the migration snapshot and the new server. Preserve old
   changes before resolving differences; do not overwrite the new server's newer state.
2. Check deployed frontend bundles, external hosting rewrites, environment variables, DNS,
   SSH aliases and tunnels for dependencies on the old host. Updating source alone does not
   update an existing deployment. IP-based hostnames and ephemeral tunnel URLs may change.
3. Stop old ingress and application writers, then take final consistent database exports and
   a final file backup. Avoid running duplicate agents or message-sending workers.
4. Pause the old synchronization session and verify the new one has no unresolved conflicts.
5. Shut down the old host before permanently deleting it. Check public routes, native SSH,
   workspace links, previews, HAPI session continuity and application services with it offline.
6. Record observed results and pre-existing failures. An active service or HTTP 200 alone does
   not prove every workflow works; verify the content and important user actions too.

Keep the original backup together with any final incremental archive, record exact recovery
paths and rollback steps, and distinguish restored services from material preserved only for
recovery. Provider cancellation is separate from operating-system shutdown; retain the
archives after cancellation.
