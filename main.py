"""Provide AUTHORIZATION, then run: python main.py."""

import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parent


def ensure_dependencies() -> None:
    """Install once into this project, including pip when the system lacks it."""
    packages = ROOT / ".packages"
    sys.path.insert(0, str(packages))
    os.environ["PYTHONPATH"] = str(packages) + os.pathsep + os.environ.get("PYTHONPATH", "")
    requirements = ROOT / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes() + sys.version.encode()).hexdigest()
    marker = packages / ".requirements.sha256"
    if marker.exists() and marker.read_text() == fingerprint:
        return
    packages.mkdir(exist_ok=True)
    flags = ["--target", str(packages), "--no-warn-script-location", "--disable-pip-version-check"]
    print("Preparing project dependencies...", flush=True)
    if importlib.util.find_spec("pip") is None:
        with tempfile.TemporaryDirectory() as temporary:
            installer = Path(temporary) / "get-pip.py"
            with urllib.request.urlopen("https://bootstrap.pypa.io/get-pip.py", timeout=60) as response:
                installer.write_bytes(response.read())
            subprocess.run([sys.executable, str(installer), *flags], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", *flags,
                    "-r", str(requirements)], check=True)
    marker.write_text(fingerprint)
    importlib.invalidate_caches()


def normalize_authorization(value: str) -> str:
    value = value.strip()
    if value.lower() == "bearer":
        value = ""
    elif value.lower().startswith("bearer "):
        value = value[7:].strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError("Authorization must be a Token or 'Bearer <Token>'")
    return "Bearer " + value


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")
    ensure_dependencies()
    from dotenv import load_dotenv
    from mcpo import app

    load_dotenv(ROOT / ".env")
    authorization = os.environ.get("AUTHORIZATION") or getpass.getpass("mxchip Authorization: ")
    os.environ["AUTHORIZATION"] = normalize_authorization(authorization)
    host, port = os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")

    # Only the stdio command is temporary; Authorization is inherited via environment.
    config = {"mcpServers": {"dehumidifier": {
        "command": sys.executable, "args": [str(ROOT / "dehumidifier_mcp.py")],
    }}}
    with tempfile.TemporaryDirectory(prefix="dehumidifier-") as temporary:
        config_path = Path(temporary) / "config.json"
        config_path.write_text(json.dumps(config))
        arguments = ["--host", host, "--port", str(port), "--config", str(config_path)]
        if os.environ.get("API_KEY"):
            arguments += ["--api-key", os.environ["API_KEY"]]
        print(f"HTTP API: http://{host}:{port}/dehumidifier/docs", flush=True)
        app(args=arguments)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, EOFError) as error:
        raise SystemExit(str(error)) from None
