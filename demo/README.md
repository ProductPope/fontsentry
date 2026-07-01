# FontSentry demo dataset

A self-contained, offline dataset so anyone can clone the repo and get a
meaningful report with **no internet access and no private data**.

```bash
uv run fontsentry scan --demo
```

This scans two synthetic domains served from `sites/` by an in-process transport
(no server, no network), using the demo registry in `registry/licenses.yaml` and
the default rules in `config/rules.example.yaml`.

## What's here

- `sites/example-demo.test/` and `sites/example-shop.test/` — static HTML + CSS
  with a mix of self-hosted fonts (TTF and WOFF2).
- `registry/licenses.yaml` — a synthetic owned-license registry.
- `_generate_assets.py` — rebuilds the font binaries (crafted name tables).
  Run with `uv run python demo/_generate_assets.py` after editing font metadata.

## Expected findings (illustrates every behaviour)

| Font | Owner | Outcome | Why |
| --- | --- | --- | --- |
| Atlas Grotesk Private | Meridian Letterworks | **High, open** | TTF on web, self-host prohibited, on 2 domains but licensed for 1 (max_domains) |
| Acme Display | Acme Type | **Open** | Commercial, no registry entry, stripped copyright |
| Expired Face | Old Foundry | **Open** | Matching license has expired |
| Harbor Serif | Northwind Type | **Resolved** | Valid multi-domain license covers it |
| Public Glyphs Sans | Public Glyphs Foundation | **Low** | Open (OFL) font from a known-free foundry |

All names, foundries, and domains are invented. This dataset is brand neutral.
