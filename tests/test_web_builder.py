import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from urllib.error import HTTPError

from sharkbyte_alpha.web import WebProjectError, build_project, parse_project
from sharkbyte_alpha.cli import main
from http.server import ThreadingHTTPServer
from sharkbyte_alpha.web import PreviewHandler
from sharkbyte_studio import Studio, WebPreviewHandler
from functools import partial

ROOT=Path(__file__).resolve().parents[1]

class WebProjectTests(unittest.TestCase):
    def project(self, **updates):
        data={"schema":"sharkbyte.web/v1","type":"website","name":"Test","home":"home","pages":[{"id":"home","title":"Home","sections":[{"kind":"text","text":"safe"}]}]}
        data.update(updates)
        return json.dumps(data)

    def test_rejects_bad_schema_duplicate_keys_and_bad_pages(self):
        for src in ('{}', '{"schema":"sharkbyte.web/v1","schema":"bad"}'):
            with self.assertRaises(WebProjectError): parse_project(src)
        with self.assertRaises(WebProjectError): parse_project(self.project(pages=[{"id":"../bad","title":"x"}]))
        with self.assertRaises(WebProjectError): parse_project(self.project(home=["home"]))
        with self.assertRaises(WebProjectError): parse_project(self.project(pages=[{"id":"home","title":"x","sections":[{"kind":[]}]}]))
        with self.assertRaises(WebProjectError): parse_project('{"schema":"sharkbyte.web/v1","name":"\ud800"}')
        with self.assertRaises(WebProjectError): parse_project(self.project(pages=[{"id":"home","title":"x","sections":[{"kind":"image","src":"../secret.png"}]}]))

    def test_rejects_script_urls_and_injection_is_escaped(self):
        bad=self.project(pages=[{"id":"home","title":"Home","sections":[{"kind":"link","href":"javascript:alert(1)","text":"x"}]}])
        with self.assertRaises(WebProjectError): parse_project(bad)
        source=self.project(pages=[{"id":"home","title":"<script>alert(1)</script>","sections":[{"kind":"text","text":"<img src=x onerror=alert(1)>"}]}])
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);(project/'sharkbyte.web.json').write_text(source,encoding='utf8')
            build_project(project/'sharkbyte.web.json',project)
            page=(project/'dist'/'home.html').read_text(encoding='utf8')
            self.assertIn('&lt;script&gt;',page);self.assertIn('&lt;img src=x onerror=alert(1)&gt;',page)
            self.assertNotIn('<script>alert(1)</script>',page)

    def test_deterministic_multpage_and_pwa_build(self):
        source=ROOT/'examples/web/task-app/sharkbyte.web.json'
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);(project/'assets').mkdir();(project/'sharkbyte.web.json').write_bytes(source.read_bytes())
            build_project(project/'sharkbyte.web.json',project)
            first={p.relative_to(project/'dist').as_posix():p.read_bytes() for p in (project/'dist').rglob('*') if p.is_file() and p.name!='.sharkbyte-build.json'}
            build_project(project/'sharkbyte.web.json',project)
            second={p.relative_to(project/'dist').as_posix():p.read_bytes() for p in (project/'dist').rglob('*') if p.is_file() and p.name!='.sharkbyte-build.json'}
            self.assertEqual(first,second)
            self.assertTrue((project/'dist/manifest.webmanifest').is_file())
            self.assertTrue((project/'dist/service-worker.js').is_file())
            self.assertIn('task_form',source.read_text(encoding='utf8'))
            self.assertIn('serviceWorker', (project/'dist/assets/app.js').read_text(encoding='utf8'))

    def test_asset_copy_and_traversal_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);(project/'assets').mkdir();(project/'assets/p.png').write_bytes(b'PNG')
            source=self.project(pages=[{"id":"home","title":"Home","sections":[{"kind":"image","src":"p.png","alt":"x"}]}])
            (project/'sharkbyte.web.json').write_text(source,encoding='utf8')
            build_project(project/'sharkbyte.web.json',project)
            self.assertEqual((project/'dist/assets/p.png').read_bytes(),b'PNG')
            (project/'sharkbyte.web.json').write_text(self.project(pages=[{"id":"home","title":"Home","sections":[{"kind":"image","src":"..\\secret.png"}]}]),encoding='utf8')
            with self.assertRaises(WebProjectError): parse_project((project/'sharkbyte.web.json').read_text())

    def test_refuses_to_delete_files_added_to_output(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);source=ROOT/'examples/web/interactive-dashboard/sharkbyte.web.json'
            (project/'sharkbyte.web.json').write_bytes(source.read_bytes())
            build_project(project/'sharkbyte.web.json',project)
            (project/'dist/keep-me.txt').write_text('user data')
            with self.assertRaises(WebProjectError): build_project(project/'sharkbyte.web.json',project)
            self.assertEqual((project/'dist/keep-me.txt').read_text(),'user data')

    def test_untrusted_build_marker_cannot_delete_outside_output(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);source=ROOT/'examples/web/interactive-dashboard/sharkbyte.web.json'
            (project/'sharkbyte.web.json').write_bytes(source.read_bytes())
            output=project/'dist';output.mkdir()
            victim=project/'keep.txt';victim.write_text('preserve')
            (output/'.sharkbyte-build.json').write_text(json.dumps({'schema':'sharkbyte.web/v1','files':['../keep.txt']}))
            with self.assertRaises(WebProjectError): build_project(project/'sharkbyte.web.json',project)
            self.assertEqual(victim.read_text(),'preserve')

    def test_cli_new_build_and_app_alias(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path.cwd()
            try:
                import os;os.chdir(td)
                out=io.StringIO()
                with contextlib.redirect_stdout(out): self.assertEqual(main(['web','new','hello-site']),0)
                self.assertTrue(Path('hello-site/sharkbyte.web.json').is_file())
                with contextlib.redirect_stdout(out): self.assertEqual(main(['web','build','hello-site']),0)
                self.assertTrue(Path('hello-site/dist/index.html').is_file())
                with contextlib.redirect_stdout(out): self.assertEqual(main(['app','new','hello-app']),0)
                data=json.loads(Path('hello-app/sharkbyte.web.json').read_text());self.assertTrue(data['pwa'])
            finally: os.chdir(old)

    def test_studio_web_build_preview_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td)
            server=ThreadingHTTPServer(('127.0.0.1',0),Studio)
            server.receipt_dir=temp;server.web_builds={};server.receipts={}
            preview_server=ThreadingHTTPServer(('127.0.0.1',0),WebPreviewHandler)
            preview_server.preview_builds={};preview_server.studio_origin=f'http://127.0.0.1:{server.server_port}'
            server.preview_server=preview_server
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            preview_thread=threading.Thread(target=preview_server.serve_forever,daemon=True);preview_thread.start()
            base=f'http://127.0.0.1:{server.server_port}/'
            try:
                examples=json.loads(urlopen(urljoin(base,'web/examples')).read())
                self.assertIn('tasks',examples)
                req=Request(urljoin(base,'web/build'),data=json.dumps({'example':'tasks','source':examples['tasks']}).encode(),headers={'Content-Type':'application/json'},method='POST')
                built=json.loads(urlopen(req).read());self.assertEqual(built['status'],'BUILT')
                self.assertNotEqual(built['preview_url'].split(':')[2].split('/')[0],str(server.server_port))
                page=urlopen(built['preview_url'])
                self.assertIn(b'My tasks',page.read())
                self.assertIn("connect-src 'none'",page.headers['Content-Security-Policy'])
                archive=urlopen(urljoin(base,built['export_url'])).read()
                from zipfile import ZipFile
                from io import BytesIO
                with ZipFile(BytesIO(archive)) as z:
                    self.assertIn('manifest.webmanifest',z.namelist());self.assertIn('service-worker.js',z.namelist())
                bad=Request(urljoin(base,'web/build'),data=b'{"example":"tasks","source":"{}"}',headers={'Content-Type':'application/json'},method='POST')
                with self.assertRaises(HTTPError) as err: urlopen(bad)
                self.assertEqual(err.exception.code,422)
            finally: server.shutdown();server.server_close();thread.join();preview_server.shutdown();preview_server.server_close();preview_thread.join()

    def test_preview_is_local_and_sends_security_headers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'.sharkbyte-build.json').write_text('{"files":["index.html"]}')
            (root/'index.html').write_text('hello')
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(PreviewHandler,directory=str(root)))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/') as response:
                    self.assertEqual(response.read(),b'hello')
                    self.assertIn("connect-src 'none'",response.headers['Content-Security-Policy'])
                    self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
            finally: server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
