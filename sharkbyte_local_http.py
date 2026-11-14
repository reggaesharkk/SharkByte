"""HTTP transport for local model requests."""

from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_url(endpoint):
    url = urlsplit(endpoint)
    if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or url.username is not None or url.password is not None or url.fragment):
        raise ValueError("Use a loopback HTTP URL without credentials or a fragment.")
    port = url.port
    host = "[::1]" if url.hostname == "::1" else "127.0.0.1"
    return urlunsplit(("http", f"{host}:{port}" if port is not None else host,
                       url.path, url.query, ""))


def open_local(endpoint, *, data, timeout):
    request = Request(local_url(endpoint), data=data,
                      headers={"Content-Type": "application/json"})
    return build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout)
