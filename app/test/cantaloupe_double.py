"""
Test double for the Cantaloupe image server.

The app only ever asks Cantaloupe for '<base>/iiif/2/<dir>%2F<image>/info.json'
(through 'requests' and through the 'urlopen' of iiif-prezi), so a tiny HTTP server
answering that route is enough, and it works for any HTTP client.

The images are the 6 pictures of the sample dataset (setup/app/input_sample).
Only 2 sizes come from a real Cantaloupe (N9354201 and N0062500, see the fixtures),
the others are made up: nothing depends on them but the canvas sizes in the manifests.
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import unquote

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
INFO_TEMPLATE = "test_check_cantaloupe_expected_results.json"

IIIF_PATH = re.compile(r"^/iiif/2/(?P<quoted_id>[^/]+)/info\.json$")


def default_images() -> Dict[str, Tuple[int, int]]:
    """
    :return: image identifier => (width, height)
    """
    return {
        "test_dataset/N9354201": (2000, 2654),
        "test_dataset/N9354200": (1800, 2400),
        "test_dataset/N9354202": (1800, 2400),
        "test_dataset/N9354203": (1800, 2400),
        "test_dataset/L0202100": (2400, 1800),
        "test_dataset/N0062500": (2000, 3604),
    }


class CantaloupeDouble:
    """
    Serves IIIF Image API 2 'info.json' documents on a local port.
    'images' can be edited by a test (e.g. to make an image unavailable),
    'requests' lists the paths asked for, in order.
    """

    def __init__(self):
        self.images = default_images()
        self.requests: List[str] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """
        :return: what the app expects in API_IMAGE_BACKEND (with the trailing slash)
        """
        return f"http://127.0.0.1:{self._server.server_address[1]}/"

    def start(self) -> "CantaloupeDouble":
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

    def info_json(self, image_id: str, width: int, height: int) -> Dict:
        """
        Same document as the one a real Cantaloupe returns for 'test_dataset/N9354201'
        (see the 'check_cantaloupe' fixture), with the id and the size of the image asked for.
        """
        template = (FIXTURES_DIR / INFO_TEMPLATE).read_text(encoding="utf8")
        iiif_root = f"{self.base_url}iiif/2/"
        info = json.loads(template.replace("<API_IIIF_IMAGE>", iiif_root))
        info["@id"] = f"{iiif_root}{image_id.replace('/', '%2F')}"
        info["width"] = width
        info["height"] = height
        return info

    def _handler(self):
        double = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # pylint: disable=invalid-name
                double.requests.append(self.path)
                match = IIIF_PATH.match(self.path)
                image = (
                    double.images.get(unquote(match["quoted_id"])) if match else None
                )
                if image is None:
                    self._reply(404, {"error": "not found"})
                else:
                    image_id = unquote(match["quoted_id"])
                    self._reply(200, double.info_json(image_id, *image))

            def _reply(self, status, body):
                payload = json.dumps(body).encode("utf8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # keep the test output clean
                pass

        return Handler
