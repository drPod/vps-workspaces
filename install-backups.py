#!/usr/bin/env python3
"""Configure unencrypted rsnapshot backups on the VPS or Mac."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['vps', 'mac'])
    parser.add_argument('--ssh-host', default='myvps')
    parser.add_argument('--remote-home', default='/home/ubuntu')
    a = parser.parse_args()
    os.umask(0o077)
    home = Path.home()
    root = home / '.local/state/vps-workspaces-backup'
    root.mkdir(parents=True, exist_ok=True)
    snapshots = home / ('Backups/vps-workspaces' if a.role == 'mac' else '.local/share/vps-workspaces-snapshots')
    snapshots.mkdir(parents=True, exist_ok=True)
    stage = root / 'sqlite'
    stage.mkdir(exist_ok=True)
    rsnapshot = shutil.which('rsnapshot')
    rsync = shutil.which('rsync')
    if a.role == 'mac':
        rsync = next((str(p) for p in (Path('/opt/homebrew/bin/rsync'), Path('/usr/local/bin/rsync')) if p.exists()), None)
    if not rsnapshot or not rsync:
        raise SystemExit('Install rsnapshot and rsync first (brew install rsnapshot rsync on Mac)')
    conf = root / 'rsnapshot.conf'
    excludes = root / 'exclude.txt'
    config = {'rsnapshot': rsnapshot, 'rsnapshot_config': str(conf), 'snapshot_root': str(snapshots),
              'sqlite_stage': str(stage), 'exclude_file': str(excludes),
              'excludes': ['node_modules', '.venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.next', '.turbo', '.cache', '*.sock', '.DS_Store', 'Cache', 'CachedData']}
    rows = [('config_version','1.2'), ('snapshot_root',str(snapshots)+'/'), ('no_create_root','1'),
            ('cmd_rsync',rsync), ('cmd_ssh','/usr/bin/ssh'), ('cmd_rm','/bin/rm'), ('cmd_du','/usr/bin/du'),
            ('retain','hourly\t24'), ('retain','daily\t7'), ('retain','weekly\t4'), ('retain','monthly\t6'),
            ('verbose','2'), ('loglevel','3'), ('logfile',str(root/'rsnapshot.log')), ('lockfile',str(root/'rsnapshot.pid')),
            ('sync_first','1'), ('link_dest','1'), ('rsync_short_args','-azH' if a.role == 'mac' else '-aH'),
            ('rsync_long_args','--delete --numeric-ids --relative --delete-excluded --no-specials --no-devices'),
            ('ssh_args','-o BatchMode=yes -o ConnectTimeout=15'), ('exclude_file',str(excludes))]
    if a.role == 'vps':
        bin_dir = home / '.local/bin'
        bin_dir.mkdir(parents=True, exist_ok=True)
        wrapper = bin_dir / 'vws-backup-rsync'
        wrapper.write_text('#!/bin/sh\nexec /usr/bin/flock -s ' + str(root / 'run.lock') + ' /usr/bin/rsync "$@"\n')
        wrapper.chmod(0o700)
        roots = [home/'Coding',home/'.codex',home/'.local/share/vps-workspaces',home/'.config/systemd/user',home/'deploy']
        config['sqlite_roots'] = [str(p) for p in roots if p.exists()]
        config['excludes'] += [str(home/'.codex/cache'), str(home/'.codex/tmp'), str(home/'.local/share/vps-workspaces/venv'), str(home/'.local/share/vps-workspaces/hapi/data/runtime')]
        for source in roots + [stage]:
            if source.exists(): rows.append(('backup',str(source)+'/\tvps/'))
        for source in [home/'.bashrc',home/'.profile',home/'.tmux.conf']:
            if source.exists():rows.append(('backup',str(source)+'\tvps/'))
    else:
        config.update(ssh_host=a.ssh_host, remote_ready=a.remote_home+'/.local/state/vps-workspaces-backup/last-success.json')
        # Pull the newest completed VPS snapshot; Mac rsnapshot keeps its own retention.
        rows.append(('backup',a.ssh_host+':'+a.remote_home+'/.local/share/vps-workspaces-snapshots/hourly.0/vps/./\tvps/\t+rsync_long_args=--rsync-path=' + a.remote_home + '/.local/bin/vws-backup-rsync'))
        roots = [home/'Coding',home/'.codex',home/'.local/state/vps-workspaces',home/'.local/share/vps-workspaces/hapi',home/'Library/Application Support/cmux']
        config['sqlite_roots'] = [str(p) for p in roots if p.exists()]
        config['excludes'] += [str(home/'.codex/cache'), str(home/'.codex/tmp')]
        for source in roots + [stage]:
            if source.exists():rows.append(('backup',str(source)+'/\tmac/'))
        for source in [home/'.zshrc',home/'.ssh/config']:
            if source.exists():rows.append(('backup',str(source)+'\tmac/'))
    excludes.write_text('\n'.join(config['excludes'])+'\n')
    conf.write_text('\n'.join(k+'\t'+v for k,v in rows)+'\n')
    (root/'config.json').write_text(json.dumps(config,indent=2))
    subprocess.run([rsnapshot,'-c',str(conf),'configtest'],check=True)
    script=Path(__file__).resolve().with_name('backup.py')
    if a.role=='vps':
        units=home/'.config/systemd/user'
        (units/'vps-workspaces-backup.service').write_text(f'''[Unit]
Description=Unencrypted workspace snapshots via rsnapshot
[Service]
Type=oneshot
UMask=0077
ExecStart=/usr/bin/python3 {script} --config {root}/config.json
Nice=10
IOSchedulingClass=idle
''')
        (units/'vps-workspaces-backup.timer').write_text('''[Unit]
Description=Hourly workspace snapshots
[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120
[Install]
WantedBy=timers.target
''')
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        subprocess.run(['systemctl','--user','enable','--now','vps-workspaces-backup.timer'],check=True)
    else:
        agents=home/'Library/LaunchAgents';agents.mkdir(exist_ok=True)
        label='com.drpod.vps-workspaces-backup'
        plist=agents/(label+'.plist')
        plist.write_bytes(plistlib.dumps({'Label':label,'ProgramArguments':[shutil.which('python3.14') or '/usr/bin/python3',str(script),'--config',str(root/'config.json')],
            'StartInterval':3600,'RunAtLoad':True,'StandardOutPath':str(root/'launch.log'),'StandardErrorPath':str(root/'launch.log'),
            'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'}}))
        subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}/{label}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(plist)],check=True)
    print('Backups configured:',snapshots)


if __name__=='__main__':main()
