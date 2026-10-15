"""Local network/share settings. Passwords are stored as salted hashes only."""

from __future__ import annotations

import errno
import hashlib
import hmac
import json
import secrets
from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parent / "network_settings.json"
MODES = {"local", "lan", "public"}
HASH_ITERATIONS = 600_000


def default_settings() -> dict:
    return {"version": 1, "mode": "local", "username": "", "salt": "", "digest": ""}


def install_upload_disconnect_handling():
    """Fail an interrupted image/audio upload cleanly and finish its progress."""
    import logging
    from functools import wraps
    from fastapi import HTTPException
    from starlette.requests import ClientDisconnect
    from gradio.route_utils import GradioMultiPartParser

    original = GradioMultiPartParser.parse
    if getattr(original, "_spokesman_disconnect_safe", False):
        return

    @wraps(original)
    async def parse_upload(parser):
        try:
            return await original(parser)
        except ClientDisconnect:
            for file in parser._files_to_close_on_error:
                file.close()
            if parser.upload_id and parser.upload_progress is not None:
                parser.upload_progress.set_done(parser.upload_id)
            logging.getLogger(__name__).warning(
                "Upload interrupted: the client disconnected. Upload the image or audio again."
            )
            raise HTTPException(
                status_code=400,
                detail="Upload interrupted. Upload the image or audio again and wait for its preview before generating.",
            ) from None

    parse_upload._spokesman_disconnect_safe = True
    GradioMultiPartParser.parse = parse_upload


def read_settings() -> dict:
    if not SETTINGS_PATH.is_file():
        return default_settings()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if data.get("version") != 1 or data.get("mode") not in MODES:
            raise ValueError("Unsupported network settings format or mode.")
        for field in ("username", "salt", "digest"):
            if not isinstance(data.get(field), str):
                raise ValueError(f"Network settings field {field!r} is invalid.")
        if bool(data["salt"]) != bool(data["digest"]) or (data["digest"] and not data["username"]):
            raise ValueError("Network login settings are incomplete.")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"Network settings could not be read: {error}") from error


def password_hash(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), HASH_ITERATIONS,
    ).hex()


def verify_login(username: str, password: str, settings: dict) -> bool:
    if not username or not password or not settings.get("salt") or not settings.get("digest"):
        return False
    try:
        user_matches = hmac.compare_digest(username.encode("utf-8"), settings["username"].encode("utf-8"))
        digest_matches = hmac.compare_digest(password_hash(password, settings["salt"]), settings["digest"])
        return user_matches and digest_matches
    except (TypeError, ValueError):
        return False


def save_settings(mode: str, username: str, password: str) -> dict:
    if mode not in MODES:
        raise ValueError("Choose Local only, Local network, or Temporary public link.")
    username = (username or "").strip()
    password = password or ""
    result = default_settings()
    result["mode"] = mode
    # Saving a blank password explicitly turns login off; it never keeps an old hash.
    if mode != "local" and password:
        result["username"] = username or "ggf"
        result["salt"] = secrets.token_hex(16)
        result["digest"] = password_hash(password, result["salt"])
    SETTINGS_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def launch_with_port_fallback(demo, *, preferred_port: int, attempts: int = 100, **kwargs):
    """Let Gradio bind each candidate, retrying only occupied-port errors."""
    if not 1 <= preferred_port <= 65535 or attempts < 1:
        raise ValueError("Choose a port between 1 and 65535 and at least one attempt.")
    last_error = None
    for port in range(preferred_port, min(65536, preferred_port + attempts)):
        try:
            return demo.launch(server_port=port, **kwargs)
        except OSError as error:
            occupied = (
                "Cannot find empty port in range:" in str(error)
                or error.errno == errno.EADDRINUSE
                or getattr(error, "winerror", None) == 10048
            )
            if not occupied:
                raise
            last_error = error
            print(f"Port {port} is occupied; trying the next available port.", flush=True)
    raise OSError(
        f"No available port from {preferred_port} to "
        f"{min(65535, preferred_port + attempts - 1)}."
    ) from last_error


def launch_access_servers(build_demo, *, mode, preferred_port, auth=None,
                          inbrowser=False, **kwargs):
    """Separate trusted loopback access from the optional authenticated remote UI.

    Both views call the same process-wide inference backend; only the UI/server
    objects are separate. Never share or LAN-bind the unauthenticated local UI.
    """
    if mode not in MODES:
        raise ValueError("Unknown network access mode.")
    options = dict(kwargs)
    options["prevent_thread_lock"] = True
    local_demo = build_demo()
    _, local_url, _ = launch_with_port_fallback(
        local_demo, preferred_port=preferred_port, server_name="127.0.0.1",
        share=False, auth=None, inbrowser=inbrowser, **options,
    )
    print(f"Local app (no login): {local_url}", flush=True)
    if mode == "local":
        return local_demo, None, local_url, None

    remote_demo = None
    try:
        # Separate default ranges also keep Headliner and Spokesman apart.
        remote_port = preferred_port + 1000 if preferred_port <= 64535 else preferred_port - 1000
        remote_demo = build_demo()
        _, remote_local_url, public_url = launch_with_port_fallback(
            remote_demo, preferred_port=remote_port,
            server_name="0.0.0.0" if mode == "lan" else "127.0.0.1",
            share=mode == "public", auth=auth, inbrowser=False, **options,
        )
        if mode == "public" and not public_url:
            raise RuntimeError("The public link could not be created.")
        remote_url = public_url if mode == "public" else remote_local_url
        print(f"Remote app: {remote_url}", flush=True)
        return local_demo, remote_demo, local_url, remote_url
    except Exception as error:
        if remote_demo is not None:
            remote_demo.close()
        print(f"Remote access failed: {error}. Local access remains available at {local_url}", flush=True)
        return local_demo, None, local_url, None
