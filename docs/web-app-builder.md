# SharkByte Web and App Builder (alpha)

The first vertical slice uses a strict declarative source format named `sharkbyte.web.json`. It is parsed and validated by `sharkbyte_alpha.web`, then compiled deterministically to ordinary HTML, CSS, and JavaScript. It is deliberately separate from the SharkVM compiler and quantum simulator: web projects cannot invoke either execution engine.

## Quick start

From a repository checkout (Python 3.10+, no extra package dependencies):

```sh
python -m sharkbyte_alpha web new my-website
python -m sharkbyte_alpha web build my-website
python -m sharkbyte_alpha web serve my-website
```

For a Progressive Web App template:

```sh
python -m sharkbyte_alpha app new my-tasks
python -m sharkbyte_alpha app build my-tasks
python -m sharkbyte_alpha app serve my-tasks
```

`web` and `app` accept the same source language. `app new` enables PWA output by default. The generated site is written to `<project>/dist`; `--output DIR` can select another build directory. The preview binds to `127.0.0.1` and defaults to port 8121 (override with `--port`). Stop the server with Ctrl+C. The `sharkbyte` installed command has the same subcommands.

## Source format

The project root is a JSON object with `schema: "sharkbyte.web/v1"`, `type: "website" | "app"`, `name`, `pages`, optional `home`, `theme`, scalar `state`, and `pwa`. A page has a unique lowercase `id`, `title`, and a list of sections. Supported section kinds are `heading`, `text`, `image`, `link`, `list`, `card`, `stat`, `button`, `range`, `chart`, and `task_form`. Example projects are the canonical complete source examples:

- [`examples/web/research-portfolio/sharkbyte.web.json`](../examples/web/research-portfolio/sharkbyte.web.json)
- [`examples/web/interactive-dashboard/sharkbyte.web.json`](../examples/web/interactive-dashboard/sharkbyte.web.json)
- [`examples/web/task-app/sharkbyte.web.json`](../examples/web/task-app/sharkbyte.web.json)

Image files belong under `<project>/assets/`; only relative POSIX asset paths and PNG/JPEG/GIF/WebP images up to 10 MiB are accepted. Generated builds copy referenced assets. Theme keys are restricted to hex colors. Text is escaped, links are limited to HTTPS/mailto, same-project HTML pages, or fragment links. Unsupported fields are ignored only where explicitly described; unknown section kinds fail closed.

## Interactions and PWA behavior

Buttons support `increment` and `toggle` state actions. Range controls update a named numeric state value. The task form supports add, completion, and delete; tasks persist in browser local storage. The dashboard chart is a static SVG generated from source values. When `pwa: true`, build emits `manifest.webmanifest`, a generated SVG icon, and a service worker that pre-caches the generated site and assets for offline reload after the first successful visit. This produces a browser-installable web app, not native Android/iOS packages.

## Studio

Run `python -B sharkbyte_studio.py`. Choose **Web / App**, pick a bundled example, edit its DSL source, then select **Build & preview**. The preview iframe is sandboxed without same-origin privileges; generated assets are served from a fixed allow-list with a restrictive Content Security Policy, no network connections, and no Studio execution endpoints. **Export ZIP** downloads the generated files. The editor currently loads one of the bundled projects; arbitrary user-selected filesystem projects and visual editing are not implemented.

## Boundaries and limits

The compiler executes no user-authored Python or JavaScript. Components are limited to the declarative kinds above. Arbitrary scripts, API integrations, server-side backends, authentication, databases, native mobile/desktop packaging, AI generation, and quantum visualizations are not implemented. Browser local storage is local to a browser profile and is not encrypted or synchronized. A local preview server is a development convenience, not a production host or general security sandbox.

## Verification

Run focused tests with `python -m unittest tests.test_web_builder -v`; run the repository suite with `python -m unittest discover -s tests -v`. The focused suite checks parsing, deterministic output, escaping, asset handling, traversal rejection, safe rebuild behavior, PWA files, localhost preview headers, and Studio preview/export. No interactive browser automation or real-world offline browser test is claimed yet.
