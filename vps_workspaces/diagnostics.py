from __future__ import annotations

import json
import pathlib
import subprocess


def main() -> None:

    cli = "/Applications/cmux.app/Contents/Resources/bin/cmux"
    results = {}
    for name, args in [
        ("version", ["version"]),
        ("capabilities", ["capabilities"]),
        ("tree", ["tree", "--all"]),
    ]:
        p = subprocess.run([cli, "--json", "--id-format", "uuids", *args], check=False, capture_output=True, text=True)
        try:
            value = json.loads(p.stdout)
        except ValueError:
            value = p.stdout
        results[name] = {"code": p.returncode, "data": value, "error": p.stderr}
    path = pathlib.Path.home() / ".local/state/vps-workspaces/cmux-diagnostic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2))
    path.chmod(0o600)
    print("Diagnostic saved:", path)


if __name__ == "__main__":
    main()
