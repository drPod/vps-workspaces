Standalone cmux settings editor from manaflow-ai/cmux, commit
f86239064370129a926a0828b2e1f0971f8cd19d:

- skills/cmux-settings/scripts/cmux-settings
- skills/cmux-settings/scripts/cmux_jsonc_edit.py

Copyright Manaflow, Inc. and contributors. GPL-3.0-or-later; see LICENSE.
One compatibility change: pass `--scope` only when the installed cmux validator supports it.

This is invoked as a separate command to preserve JSONC and use cmux's own validator.

https://github.com/manaflow-ai/cmux/tree/f86239064370129a926a0828b2e1f0971f8cd19d/skills/cmux-settings/scripts
