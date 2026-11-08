import time

import httpx


class Api:
    def __init__(self, url):
        self.c = httpx.Client(base_url=url, timeout=600)

    def call(self, m, path, **kw):
        for i in range(10):
            try:
                r = self.c.request(m, path, **kw)
                if r.status_code < 500:
                    return r
            except httpx.TransportError:
                pass
            time.sleep(min(2 ** i, 30))
        raise RuntimeError(f"{m} {path} keeps failing")

    def get(self, path, **kw):
        r = self.call("GET", path, **kw)
        r.raise_for_status()
        return r.json()

    def text(self, path):
        r = self.call("GET", path)
        r.raise_for_status()
        return r.text

    def post(self, path, body):
        return self.call("POST", path, json=body)

    def put(self, path, body):
        return self.call("PUT", path, json=body)
