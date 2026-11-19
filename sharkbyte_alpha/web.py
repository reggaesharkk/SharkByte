from __future__ import annotations

"""Strict declarative SharkByte web project compiler (no arbitrary code execution)."""
import html
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial

SCHEMA = "sharkbyte.web/v1"
MAX_PROJECT_BYTES = 1_000_000
MAX_ASSET_BYTES = 10 * 1024 * 1024
SLUG = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ALLOWED = {"heading", "text", "image", "link", "list", "card", "stat", "button", "range", "chart", "task_form"}

class WebProjectError(ValueError):
    pass

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WebProjectError(f"duplicate JSON key: {key}")
        out[key] = value
    return out

def _safe_file(value):
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise WebProjectError("asset paths must be relative POSIX paths")
    parts = value.split("/")
    if any(p in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise WebProjectError("asset path contains an unsafe component")
    return value

def parse_project(source):
    if isinstance(source, bytes):
        if len(source) > MAX_PROJECT_BYTES: raise WebProjectError("project exceeds 1,000,000 bytes")
        try: source = source.decode("utf-8")
        except UnicodeDecodeError as exc: raise WebProjectError("project must be valid UTF-8") from exc
    if not isinstance(source, str):
        raise WebProjectError("project must be UTF-8 text up to 1,000,000 bytes")
    try: encoded_source = source.encode("utf-8")
    except UnicodeEncodeError as exc: raise WebProjectError("project contains invalid Unicode") from exc
    if len(encoded_source) > MAX_PROJECT_BYTES: raise WebProjectError("project exceeds 1,000,000 bytes")
    try: data = json.loads(source, object_pairs_hook=_pairs, parse_constant=lambda x: (_ for _ in ()).throw(WebProjectError("non-finite JSON number")))
    except (json.JSONDecodeError, RecursionError) as exc: raise WebProjectError(f"invalid project JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA: raise WebProjectError(f"expected schema {SCHEMA}")
    if data.get("type") not in ("website", "app"): raise WebProjectError("type must be website or app")
    if not isinstance(data.get("name"), str) or not 1 <= len(data["name"]) <= 100: raise WebProjectError("name must contain 1–100 characters")
    pages = data.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 32: raise WebProjectError("pages must be a list of 1–32 pages")
    ids = set()
    for page in pages:
        if not isinstance(page, dict) or not SLUG.fullmatch(str(page.get("id", ""))): raise WebProjectError("each page needs a lowercase slug id")
        if page["id"] in ids: raise WebProjectError("page ids must be unique")
        ids.add(page["id"])
        if not isinstance(page.get("title"), str) or len(page["title"]) > 120: raise WebProjectError("page title must be at most 120 characters")
        sections = page.get("sections", [])
        if not isinstance(sections, list) or len(sections) > 200: raise WebProjectError("sections must be a list of at most 200 items")
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get("kind"), str) or section["kind"] not in ALLOWED: raise WebProjectError("section kind is missing or unsupported")
            for key in ("text", "title", "label", "value", "caption"):
                if key in section and (not isinstance(section[key], (str, int, float)) or len(str(section[key])) > 4000): raise WebProjectError(f"section {key} must be short text")
            if "href" in section and (not isinstance(section["href"], str) or not (section["href"].startswith("#") or section["href"].startswith("https://") or section["href"].startswith("mailto:") or bool(re.fullmatch(r"[a-z][a-z0-9-]{0,39}\.html", section["href"])))): raise WebProjectError("links must use #, https, or mailto URLs")
            if section["kind"] == "image": section["src"] = _safe_file(section.get("src"))
            if "items" in section and (not isinstance(section["items"], list) or len(section["items"]) > 100 or any(not isinstance(x, str) for x in section["items"])): raise WebProjectError("items must be a list of text")
            if section["kind"] == "range":
                for k in ("min", "max", "value"):
                    if type(section.get(k)) not in (int, float) or not math.isfinite(section[k]): raise WebProjectError("range min, max and value must be finite numbers")
                if not section["min"] <= section["value"] <= section["max"]: raise WebProjectError("range value must be within min and max")
                if not SLUG.fullmatch(str(section.get("target", "value"))): raise WebProjectError("range target must be a lowercase slug")
            if section["kind"] == "button":
                if section.get("action", "increment") not in ("increment", "toggle"): raise WebProjectError("button action must be increment or toggle")
                if not SLUG.fullmatch(str(section.get("target", "count"))): raise WebProjectError("button target must be a lowercase slug")
            if section["kind"] == "chart":
                if not isinstance(section.get("values"), list) or not 1 <= len(section["values"]) <= 24 or any(type(x) not in (int, float) or abs(x) > 1e12 for x in section["values"]): raise WebProjectError("chart values must be 1–24 finite numbers")
    if not isinstance(data.get("home", pages[0]["id"]), str) or data.get("home", pages[0]["id"]) not in ids: raise WebProjectError("home must name an existing page")
    theme = data.get("theme", {})
    if not isinstance(theme, dict): raise WebProjectError("theme must be an object")
    for key, value in theme.items():
        if key not in ("primary", "background", "surface", "text") or not isinstance(value, str) or not HEX.fullmatch(value): raise WebProjectError("theme supports only primary/background/surface/text hex colors")
    state = data.get("state", {})
    if not isinstance(state, dict) or len(state) > 32 or any(not SLUG.fullmatch(k) or type(v) not in (str, int, float, bool) or isinstance(v,float) and not math.isfinite(v) for k,v in state.items()): raise WebProjectError("state must map short slug keys to finite scalar values")
    if type(data.get("pwa", False)) is not bool: raise WebProjectError("pwa must be boolean")
    return data

def _e(x): return html.escape(str(x), quote=True)

def _section(s):
    k=s["kind"]; title=_e(s.get("title", "")); text=_e(s.get("text", s.get("value", "")))
    if k == "heading":
        level=s.get("level",2); level=level if type(level) is int and level in (1,2,3,4) else 2
        return f"<h{level}>{_e(s.get('text',''))}</h{level}>"
    if k == "text": return f"<p>{_e(s.get('text',''))}</p>"
    if k == "image": return f'<figure><img loading="lazy" src="{_e(s["src"])}" alt="{_e(s.get("alt",""))}"><figcaption>{_e(s.get("caption",""))}</figcaption></figure>'
    if k == "link": return f'<p><a href="{_e(s.get("href","#"))}">{_e(s.get("text","Open"))}</a></p>'
    if k == "list": return "<ul>"+"".join(f"<li>{_e(x)}</li>" for x in s.get("items",[]))+"</ul>"
    if k == "card": return f'<article class="card"><h3>{title}</h3><p>{_e(s.get("text",""))}</p></article>'
    if k == "stat": return f'<article class="card stat"><strong>{text}</strong><span>{_e(s.get("label",""))}</span></article>'
    if k == "button": return f'<button type="button" data-action="{_e(s.get("action","increment"))}" data-target="{_e(s.get("target","count"))}" data-label="{_e(s.get("label","Update"))}">{_e(s.get("label","Update"))}</button>'
    if k == "range": return f'<label>{_e(s.get("label","Value"))}<output data-output="{_e(s.get("target","value"))}">{_e(s["value"])}</output><input type="range" min="{s["min"]}" max="{s["max"]}" value="{s["value"]}" data-range="{_e(s.get("target","value"))}"></label>'
    if k == "chart": return _chart(s)
    if k == "task_form": return '<form data-task-form><label>New task <input name="task" maxlength="160" required></label><button>Add task</button></form><ul data-task-list></ul>'
    return ""

def _chart(s):
    vals=s["values"]; maximum=max([abs(x) for x in vals]+[1]); bars=[]
    for i,v in enumerate(vals):
        x=12+i*26; height=100*abs(v)/maximum; y=112-height
        bars.append(f'<rect x="{x}" y="{y:.2f}" width="18" height="{height:.2f}" rx="3"><title>{_e(v)}</title></rect>')
    return f'<svg class="chart" viewBox="0 0 {24+len(vals)*26} 120" role="img" aria-label="{_e(s.get("title","Chart"))}">{"".join(bars)}</svg>'

def _render(data, assets):
    nav=" ".join(f'<a href="{p["id"]}.html">{_e(p["title"])}</a>' for p in data["pages"])
    theme=data.get("theme",{}); css=f""":root{{--primary:{theme.get('primary','#216e64')};--bg:{theme.get('background','#f4f7f6')};--surface:{theme.get('surface','#ffffff')};--text:{theme.get('text','#182421')}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}}header,main,footer{{width:min(1100px,92%);margin:auto}}header{{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:1rem 0;flex-wrap:wrap}}nav{{display:flex;gap:1rem;flex-wrap:wrap}}a{{color:var(--primary)}}main{{padding:2rem 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:1rem}}main>h1,main>h2,main>h3,main>p,main>ul,main>figure,main>form,main>.chart{{grid-column:1/-1}}.card,form,figure{{background:var(--surface);padding:1rem;border-radius:1rem}}img{{max-width:100%;height:auto;border-radius:.7rem}}button{{padding:.65rem 1rem;background:var(--primary);color:white;border:0;border-radius:.5rem;cursor:pointer}}input{{padding:.6rem;max-width:100%}}.stat strong,.stat span{{display:block}}.chart rect{{fill:var(--primary)}}footer{{padding:2rem 0}}@media(max-width:520px){{header{{align-items:flex-start}}nav{{width:100%}}}}"""
    js="""(()=>{const seed=JSON.parse(document.querySelector('main').dataset.state);const state={...seed,...JSON.parse(localStorage.getItem('sharkbyte-state')||'{}')};const save=()=>localStorage.setItem('sharkbyte-state',JSON.stringify(state));document.querySelectorAll('[data-range]').forEach(x=>{const k=x.dataset.range;if(k in state)x.value=state[k];x.addEventListener('input',()=>{state[k]=Number(x.value);const o=document.querySelector('[data-output="'+CSS.escape(k)+'"]');if(o)o.value=x.value;save()})});document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{const k=b.dataset.target;state[k]=b.dataset.action==='toggle'?!state[k]:(Number(state[k]||0)+1);const label=b.dataset.label||b.textContent;b.textContent=label.includes('{value}')?label.replace('{value}',String(state[k])):label+' '+String(state[k]);save()}));const form=document.querySelector('[data-task-form]');if(form){let tasks=JSON.parse(localStorage.getItem('sharkbyte-tasks')||'[]');const list=form.parentElement.querySelector('[data-task-list]');const draw=()=>{list.replaceChildren();tasks.forEach((t,i)=>{const li=document.createElement('li');const label=document.createElement('label');const c=document.createElement('input');c.type='checkbox';c.checked=t.done;c.addEventListener('change',()=>{tasks[i].done=c.checked;persist()});label.append(c,document.createTextNode(' '+t.text+' '));const d=document.createElement('button');d.type='button';d.textContent='Delete';d.addEventListener('click',()=>{tasks.splice(i,1);persist()});li.append(label,d);list.append(li)})};const persist=()=>{localStorage.setItem('sharkbyte-tasks',JSON.stringify(tasks));draw()};form.addEventListener('submit',e=>{e.preventDefault();const input=form.elements.task;const text=input.value.trim();if(text){tasks.push({text,done:false});input.value='';persist()}});draw()}})();"""
    files={"assets/style.css":css,"assets/app.js":js}
    for page in data["pages"]:
        content="".join(_section(s) for s in page.get("sections",[]))
        pageid=page["id"]
        state=json.dumps(data.get("state",{}),ensure_ascii=True,separators=(",",":" )).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
        manifest='<link rel="manifest" href="manifest.webmanifest">' if data.get("pwa") else ""
        files[pageid+".html"]=f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{_e(data["name"])}"><title>{_e(page["title"])}</title>{manifest}<link rel="stylesheet" href="assets/style.css"></head><body><header><strong>{_e(data["name"])}</strong><nav>{nav}</nav></header><main data-state="{_e(state)}"><h1>{_e(page["title"])}</h1>{content}</main><footer>Built with SharkByte</footer><script defer src="assets/app.js"></script></body></html>'
    files["index.html"]=files.get(data.get("home",data["pages"][0]["id"])+".html",next(iter(files.values())))
    if data.get("pwa"):
        files["manifest.webmanifest"]=json.dumps({"name":data["name"],"short_name":data["name"][:12],"start_url":"./index.html","display":"standalone","background_color":theme.get("background","#f4f7f6"),"theme_color":theme.get("primary","#216e64"),"icons":[{"src":"assets/icon.svg","sizes":"any","type":"image/svg+xml","purpose":"any maskable"}]},ensure_ascii=False,indent=2)
        files["assets/icon.svg"]='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="'+theme.get("primary","#216e64")+'"/><path d="M18 34h28M32 18v28" stroke="white" stroke-width="7" stroke-linecap="round"/></svg>'
        precache=list(files)+["service-worker.js"]
        files["service-worker.js"]="const CACHE='sharkbyte-v1';const FILES="+json.dumps(precache)+";self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES))));self.addEventListener('fetch',e=>e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))));"
        for name,content in assets.items(): files["assets/"+name]=content
        files["assets/app.js"] += '\nif("serviceWorker" in navigator)navigator.serviceWorker.register("service-worker.js");\n'
    else:
        for name,content in assets.items(): files["assets/"+name]=content
    return files

def build_project(source, project_dir, output_dir=None):
    if isinstance(source, Path):
        with source.open("rb") as stream: source = stream.read(MAX_PROJECT_BYTES + 1)
    elif isinstance(source, str) and not source.lstrip().startswith("{"):
        candidate = Path(source)
        if candidate.is_file():
            with candidate.open("rb") as stream: source = stream.read(MAX_PROJECT_BYTES + 1)
    data=parse_project(source)
    root=Path(project_dir).resolve(); assets={}
    assets_dir=root/"assets"
    for page in data["pages"]:
        for sec in page.get("sections",[]):
            if sec["kind"]=="image":
                rel=_safe_file(sec["src"]); p=(assets_dir/rel).resolve()
                if not p.is_relative_to(assets_dir.resolve()) or not p.is_file(): raise WebProjectError("image asset is missing or escapes assets directory")
                if p.stat().st_size>MAX_ASSET_BYTES: raise WebProjectError("image asset exceeds 10 MiB")
                if p.suffix.lower() not in (".png",".jpg",".jpeg",".gif",".webp"): raise WebProjectError("only PNG, JPEG, GIF and WebP image assets are supported")
                assets[rel]=p.read_bytes()
    files=_render(data,assets)
    target=Path(output_dir).resolve() if output_dir else root/"dist"
    if target==root or root in target.parents and target==root/"assets": raise WebProjectError("output cannot overwrite project source")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sharkbyte-web-", dir=target.parent) as td:
        stage=Path(td)/"site"; stage.mkdir()
        for name,content in files.items():
            p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content if isinstance(content,bytes) else content.encode("utf-8"))
        marker={"schema":SCHEMA,"files":sorted(files)}
        (stage/".sharkbyte-build.json").write_text(json.dumps(marker,indent=2),encoding="utf-8")
        backup=None
        if target.exists():
            marker_path = target / ".sharkbyte-build.json"
            try:
                if marker_path.is_symlink(): raise ValueError("build marker must not be a symlink")
                previous=json.loads(marker_path.read_text(encoding="utf-8"))
                if previous.get("schema") != SCHEMA or not isinstance(previous.get("files"), list): raise ValueError("invalid build marker")
                allowed={_safe_file(name) for name in previous["files"]}|{".sharkbyte-build.json"}
            except Exception: raise WebProjectError("refusing to replace output without a SharkByte build marker")
            actual={p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
            if actual-allowed: raise WebProjectError("output contains untracked files; move them before rebuilding")
            for rel in allowed:
                old = target / rel
                if old.exists() or old.is_symlink():
                    if not old.resolve().is_relative_to(target): raise WebProjectError("build output contains a symlink that escapes the output directory")
            for rel in allowed:
                old=target/rel
                if old.is_file(): old.unlink()
            for parent in sorted((x for x in target.rglob("*") if x.is_dir()),key=lambda x:len(x.parts),reverse=True):
                try: parent.rmdir()
                except OSError: pass
            try: (target/".sharkbyte-build.json").unlink()
            except FileNotFoundError: pass
            backup=target.with_name(target.name+".sharkbyte-old-"+uuid4().hex)
            target.rename(backup)
        os.replace(stage,target)
        if backup and backup.exists(): shutil.rmtree(backup)
    return {"status":"BUILT","output":str(target),"files":sorted(files),"pwa":data.get("pwa",False)}

def new_project(name, directory, app=False):
    slug=re.sub(r"[^a-z0-9-]+","-",name.lower()).strip("-")[:40] or "my-app"
    target=Path(directory);target.mkdir(parents=True,exist_ok=False);(target/"assets").mkdir()
    data={"schema":SCHEMA,"type":"app" if app else "website","name":name,"home":"home","pwa":bool(app),"theme":{"primary":"#216e64"},"state":{"count":0},"pages":[{"id":"home","title":"Welcome","sections":[{"kind":"heading","level":2,"text":"Your SharkByte project"},{"kind":"text","text":"Edit sharkbyte.web.json, then build this project."},{"kind":"button","label":"Count: {value}","action":"increment","target":"count"}]}]}
    (target/"sharkbyte.web.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    return {"status":"CREATED","project":str(target.resolve()),"source":str((target/"sharkbyte.web.json").resolve()),"slug":slug}

class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff");self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()
    def log_message(self,*a): pass

def serve_output(directory, port=8121):
    root=Path(directory).resolve()
    if not root.is_dir() or not (root/".sharkbyte-build.json").is_file(): raise WebProjectError("build the project before serving")
    server=ThreadingHTTPServer(("127.0.0.1",port),partial(PreviewHandler,directory=str(root)))
    print(f"SharkByte preview http://127.0.0.1:{server.server_port}/",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
