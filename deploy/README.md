# Deployment assets

`systemd/` contains the gateway, per-workspace IDE and backup unit templates.
The installers fill `.in` templates with Python's standard `string.Template`.
Do not put credentials or rendered machine-specific configuration here.

Use `python3 workspace.py install <component>` rather than editing installed units
without updating their source. HAPI and preview socket units are generated alongside
their upstream application's configuration. See [installation](../docs/INSTALL.md).
