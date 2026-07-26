"""Serve the real desktop UI against a recovered deterministic plan turn."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import uvicorn

from runtime.control_plane import create_control_plane_app
from runtime.control_plane.server import ServerConfig, build_services
from runtime.policy import ToolCall
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient

TOKEN = "plan-ui-e2e-token-with-at-least-32-characters"
SESSION_ID = "plan-ui-e2e"


class RecoveryProvider(ProviderClient):
    def __init__(self):
        self.calls = 0

    def complete(self, *, messages, model, **_kwargs):
        candidate = any(
            message.get("role") == "user"
            and "Verification:" in str(message.get("content", ""))
            for message in messages
        )
        if candidate:
            if not any(
                message.get("role") == "tool"
                for message in messages
            ):
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            f"write-{model.rsplit(':', 1)[-1]}",
                            "write_file",
                            {
                                "path": "runtime/candidate.txt",
                                "content": f"{model}\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text=f"{model} candidate complete")
        self.calls += 1
        if self.calls == 1:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "provider/plan-ui-e2e",
                        "propose_plan",
                        {
                            "plan": "Implement and document",
                            "tasks": [
                                {
                                    "id": "implement",
                                    "title": "Implement feature",
                                    "verification": (
                                        "Focused suite passes"
                                    ),
                                },
                                {
                                    "id": "docs",
                                    "title": "Update documentation",
                                    "verification": (
                                        "Documentation contract passes"
                                    ),
                                },
                            ],
                        },
                    )
                ]
            )
        return AssistantTurn(text="Selected plan task is ready to execute")

    def capabilities(self, _model):
        return ModelCapabilities()


class UIHandler(SimpleHTTPRequestHandler):
    ui_root: Path
    control_port: int

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(self.ui_root),
            **kwargs,
        )

    def do_GET(self):
        if self.path not in {"/", "/index.html"}:
            return super().do_GET()
        html = (self.ui_root / "index.html").read_text(encoding="utf-8")
        bootstrap = (
            "<script>"
            f"window.__CODINAL_HTTP__='http://127.0.0.1:{self.control_port}';"
            f"window.__CODINAL_WS__='ws://127.0.0.1:{self.control_port}';"
            f"window.__CODINAL_TOKEN__={json.dumps(TOKEN)};"
            "</script>"
        )
        payload = html.replace(
            '<script src="./startup.js"></script>',
            bootstrap + '<script src="./startup.js"></script>',
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ui-root", type=Path, required=True)
    parser.add_argument("--control-port", type=int, default=43124)
    parser.add_argument("--ui-port", type=int, default=1420)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.workspace.mkdir(parents=True, exist_ok=True)
    if not (args.workspace / ".git").exists():
        subprocess.run(
            ["git", "init", "-q", str(args.workspace)],
            check=True,
        )
        (args.workspace / "runtime").mkdir()
        (args.workspace / "runtime" / "candidate.txt").write_text(
            "base\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(args.workspace), "add", "."],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(args.workspace),
                "-c",
                "user.name=Codinal UI",
                "-c",
                "user.email=ui@example.test",
                "commit",
                "-qm",
                "initial",
            ],
            check=True,
        )
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=args.control_port,
            data_dir=args.data_dir,
            default_model="openai:gpt-test",
        ),
        provider=RecoveryProvider(),
    )
    app = create_control_plane_app(token=TOKEN, services=services)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=args.control_port,
            log_level="warning",
        )
    )
    control_thread = threading.Thread(target=server.run, daemon=True)
    control_thread.start()
    UIHandler.ui_root = args.ui_root.resolve()
    UIHandler.control_port = args.control_port
    with ThreadingHTTPServer(("127.0.0.1", args.ui_port), UIHandler) as ui:
        print(
            f"ready http://127.0.0.1:{args.ui_port}",
            flush=True,
        )
        try:
            try:
                ui.serve_forever()
            except KeyboardInterrupt:
                pass
        finally:
            server.should_exit = True
            control_thread.join(timeout=5)


if __name__ == "__main__":
    main()
