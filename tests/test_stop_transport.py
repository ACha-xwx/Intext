"""A local HTTP stream stalls until Stop actually disconnects it."""
from concurrent.futures import CancelledError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from urllib.request import Request

from promptsmith.api import ApiConfig, ChatCompletionsClient
from promptsmith.task_scope import TaskScope


def test_stop_interrupts_blocked_stream_read_without_waiting_for_next_chunk():
    ready, release, finished = Event(), Event(), Event()
    errors = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b": stream-ready\n\n")
            self.wfile.flush()
            ready.set()
            release.wait(3)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    service = Thread(target=server.serve_forever, daemon=True)
    service.start()
    scope = TaskScope()
    client = ChatCompletionsClient(ApiConfig(f"http://127.0.0.1:{server.server_port}", "fixture", "unused", timeout_seconds=4))

    def request():
        try:
            with scope.activate():
                client._send_json(Request(client.config.base_url), invalid_message="invalid")
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    worker = Thread(target=request, daemon=True)
    worker.start()
    try:
        assert ready.wait(1)
        scope.cancel()
        assert finished.wait(.7), "Stop must interrupt the blocked socket, not wait for more SSE"
        assert len(errors) == 1 and isinstance(errors[0], CancelledError)
    finally:
        release.set()
        worker.join(4)
        server.shutdown()
        server.server_close()
