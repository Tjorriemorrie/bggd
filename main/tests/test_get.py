import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from django.test import SimpleTestCase

from main.errors import OffsiteRedirectError
from main.games import get


class _Shop(BaseHTTPRequestHandler):
    """A shop that turns /blocked away to another host and moves its shelf on its own host."""

    hits = []

    def _serve(self):
        self.hits.append(self.path)
        if self.path == '/blocked':
            self.send_response(302)
            self.send_header('Location', 'https://localhost/')
        elif self.path == '/shelf/page/1/':
            self.send_response(301)
            self.send_header('Location', '/shelf/')
        else:
            self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


_Shop.do_GET = _Shop._serve  # http.server dispatches GET to this name


class GetRedirectTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), _Shop)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def setUp(self):
        _Shop.hits.clear()
        patcher = patch('main.games.sleep')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_redirect_to_another_host_fails_at_once(self):
        with self.assertRaisesMessage(
            OffsiteRedirectError, f'{self.base}/blocked -> https://localhost/'
        ):
            get(f'{self.base}/blocked', redirect=True)
        assert _Shop.hits == ['/blocked']  # not followed, not retried

    def test_redirect_on_the_same_host_is_followed(self):
        res = get(f'{self.base}/shelf/page/1/', redirect=True)
        assert res.status_code == 200
        assert res.url == f'{self.base}/shelf/'
