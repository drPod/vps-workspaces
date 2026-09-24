# Optional media services

This independent Compose stack reuses Radarr, Prowlarr, qBittorrent, Gluetun and Caddy.
It does not change workspace services or route the host through a VPN. IINA plays the
original files; Syncplay coordinates playback on participating computers.

## Deploy

Copy `deploy/media` to a private directory outside the synchronized source checkout.
The template targets this project's **rootless Docker** installation and existing `web`
network. PUID/PGID 0 inside the user namespace maps to the unprivileged host Docker owner;
do not use this identity configuration unchanged with a rootful daemon.

1. Copy `.env.example` to `.env` and choose an existing writable `MEDIA_ROOT`, outside Mutagen.
   Create `movies` and `torrents` beneath it on the same filesystem for hardlinks.
2. Start `docker compose up -d radarr prowlarr media-files`.
3. Configure application authentication before publishing the dashboards. The deployment
   uses Caddy basic authentication and Radarr/Prowlarr External authentication. Direct
   ports bind only to loopback; the shared Docker network must remain trusted.
4. Adapt `Caddyfile.example` into the existing proxy's sites directory. Generate a password
   hash with `caddy hash-password` and a separate random stream-path secret. Validate the
   complete Caddy configuration before reloading. Never commit the resulting private file.
5. Obtain NordVPN **service credentials**, put them in `nordvpn.env`, and chmod it to 600.
   This is not the Nord account password. Run `docker compose --profile vpn up -d` only
   after credentials are available. qBittorrent shares Gluetun's network namespace and
   waits for its health check. Gluetun supplies the firewall and kill switch.
6. Set a qBittorrent administrator password. Set its save path to `/data/torrents`, bind
   BitTorrent to `tun0`, and disable UPnP. In Radarr add qBittorrent at `gluetun:8080`,
   with a `radarr` category. Do not publish a BitTorrent port on the host. For the Caddy
   dashboard, enable qBittorrent reverse-proxy support and trust only Caddy's container IP.
   Preserve Origin/Referer and keep CSRF protection enabled. Update the trusted IP if Caddy
   is recreated with a different address.
7. Connect Prowlarr to Radarr using `http://radarr:7878`, Radarr's API key, and
   `http://prowlarr:9696` as the Prowlarr URL. Add and test sources you have access to.
   Installing Prowlarr does not supply private tracker memberships or indexer accounts.

The deployed Gluetun instance pins a tested Nord server after other randomly selected
servers failed connection/authentication. If that server retires, select and verify a new
server using upstream Gluetun/Nord configuration. Recreate both Gluetun and qBittorrent
when changing the network container; restarting Gluetun alone can leave its dependent
container attached to the previous namespace. Normal in-container VPN reconnects do not
require restarting qBittorrent.

Images are pinned by digest. Update them deliberately after reading upstream release notes.
No custom firewall, search scraper, download daemon or player is included.

## Storage and selection

Radarr's root folder is `/data/movies`. Enable hardlinks so seeding and library files
share disk blocks. Deleting one hardlink does not free blocks still used by another.

Use manual interactive searches, disable RSS/automatic searches in Prowlarr's app profile,
disable profile upgrades and proper/repack upgrades, and leave new movies unmonitored.
The deployment provides an unrestricted **Any quality — manual choice** profile, including
unknown qualities, low resolutions and remux/disc. A separate 1080p/2160p encoded profile
is optional. Global file-size limits are disabled; review the actual size before downloading.
Radarr groups 1440p release names into its 1080p category; playback keeps the actual resolution.

A 15 GiB import free-space reserve protects headroom, but it is **not a filesystem quota**
and does not stop every manual download. Approximately 35 GiB is a suggested library budget,
not an enforced limit. Check actual free space before starting downloads or moving files.

## Watch together

Open the private Caddy directory link, copy a movie URL, and open it in IINA.
For synchronized viewing, use upstream Syncplay's IINA adapter on both Macs, select
`/Applications/IINA.app/Contents/MacOS/iina-cli`, join the same room/server, and load the
same URL. The room synchronizes playback; the VPS serves the file separately to each viewer.

Anyone holding the stream-path secret can browse and play the library. Share it only with
viewing partners. Rotate the Caddy path if access needs revoking. No transcoding occurs.
Syncplay's macOS release may require an explicit owner decision in Gatekeeper; never
remove quarantine or weaken system security as part of an automated installation.

## Verify and recover

- Verify HTTPS dashboard requests return 401 without credentials and 200 with them.
- Verify stream requests support byte ranges (206), seeking and decoding on the Mac.
- Compare the torrent namespace's public IPv4 with the host's; verify IPv6 cannot bypass
  the tunnel. Interrupt VPN connectivity and check that traffic stops, then recovers.
- Check Radarr-to-qBittorrent and Prowlarr-to-Radarr connection tests, a permitted test
  download, import, hardlink identity, and a two-device Syncplay session.
- Back up Compose, private proxy configuration, credentials and application configuration.
  Use Radarr/Prowlarr native backup or SQLite's online backup API for running databases.
  Keep media outside the source and configuration snapshot roots to avoid duplication.
- Stop just this stack with `docker compose --profile vpn down`; it preserves bind-mounted
  configuration and media. Restore configuration snapshots and pinned images to roll back.

## Upstream documentation

- [NordVPN with Gluetun](https://support.nordvpn.com/hc/en-us/articles/47830508425745-How-to-set-up-an-OpenVPN-manual-connection-to-NordVPN-with-Gluetun)
- [Gluetun firewall](https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/firewall.md)
- [LinuxServer images](https://docs.linuxserver.io/)
- [Radarr quick start](https://github.com/Servarr/Wiki/blob/master/radarr/quick-start-guide.md)
- [Caddy file server](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [Syncplay installation](https://syncplay.pl/guide/install/)
