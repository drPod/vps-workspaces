# Media services moved to Watch Link

The full media stack and invitation launcher now live in
[drPod/watch-link](https://github.com/drPod/watch-link).

- [Server setup](https://github.com/drPod/watch-link/blob/main/docs/SERVER.md)
- [Playback invitations](https://github.com/drPod/watch-link/blob/main/docs/INVITATIONS.md)
- [Operations and backups](https://github.com/drPod/watch-link/blob/main/docs/OPERATIONS.md)
- [Agent instructions](https://github.com/drPod/watch-link/blob/main/AGENTS.md)

This installation still uses VPS Workspaces' existing unencrypted rsnapshot jobs on the
VPS and Mac for configuration backups. Media bytes are excluded. The private runtime remains
`~/deploy/media-stack`; its location did not change when the source moved.
