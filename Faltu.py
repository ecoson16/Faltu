#!/usr/bin/env python3
"""
Faltu – utility toolkit by Ecoson.

Features:
  • Image recolor (hue shift / tint)
  • Minecraft skin-art generator
  • Minecraft sky-pack generator
  • Mojang / NameMC lookups & skin download
  • Image compression (Tinify)
  • Filebin upload
  • TinyURL shortener
  • Recursive file-content replacer
"""

from __future__ import annotations

import base64
import json
import os
import random
import shutil
import string
import sys
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
FALTU_DIR = SCRIPT_DIR / "faltu"
BACKUP_DIR = FALTU_DIR / "backup"
INPUT_DIR = FALTU_DIR / "input"
OUTPUT_DIR = FALTU_DIR / "output"
CONFIG_DIR = FALTU_DIR / "config"
RESOURCES_DIR = CONFIG_DIR / "resources"
TEXT_OUTPUT_DIR = OUTPUT_DIR / "text_output"

CREDENTIALS_PATH = CONFIG_DIR / "credentials.txt"
SETTINGS_PATH = CONFIG_DIR / "settings.txt"
TEMPLATE_PATH = RESOURCES_DIR / "skinTemplate.png"

USERNAME_LOG = TEXT_OUTPUT_DIR / "username.txt"
UUID_LOG = TEXT_OUTPUT_DIR / "uuid.txt"
BIN_LOG = TEXT_OUTPUT_DIR / "bin.txt"
LINK_LOG = TEXT_OUTPUT_DIR / "link.txt"
NAMEMC_LOG = TEXT_OUTPUT_DIR / "namemc.txt"

# Raw GitHub URL (blob page would return HTML)
TEMPLATE_URL = (
    "https://raw.githubusercontent.com/ecoson16/Faltu/main/skinTemplate.png"
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}

SESSION_ID: Optional[str] = None
SESSION_BACKUP_DIR: Optional[Path] = None

SKY_ASSET_NAMES = (
    "skybox.png",
    "skybox2.png",
    "cloud1.png",
    "cloud2.png",
    "starfield01.png",
    "starfield02.png",
    "starfield03.png",
    "starfield.png",
)

# ---------------------------------------------------------------------------
# Folder / session helpers
# ---------------------------------------------------------------------------


def ensure_folders() -> None:
    """Create required folders and empty config/log files if missing."""
    for path in (
        FALTU_DIR,
        BACKUP_DIR,
        INPUT_DIR,
        OUTPUT_DIR,
        CONFIG_DIR,
        RESOURCES_DIR,
        TEXT_OUTPUT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)

    if not CREDENTIALS_PATH.is_file():
        CREDENTIALS_PATH.write_text(
            "# API keys – one key=value per line\n"
            "# tinify_api_key=\n"
            "# tinyurl_api_key=\n",
            encoding="utf-8",
        )

    if not SETTINGS_PATH.is_file():
        SETTINGS_PATH.write_text(
            "# Custom folders – one key=value per line\n"
            "# input_folder=\n"
            "# output_folder=\n",
            encoding="utf-8",
        )

    for log in (USERNAME_LOG, UUID_LOG, BIN_LOG, LINK_LOG, NAMEMC_LOG):
        if not log.is_file():
            log.write_text("", encoding="utf-8")

    if not TEMPLATE_PATH.is_file():
        _download_or_create_template()


def _download_or_create_template() -> None:
    """Fetch the 64×64 skin template; fall back to a blank RGBA image."""
    try:
        req = urllib.request.Request(
            TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        TEMPLATE_PATH.write_bytes(data)
        with Image.open(TEMPLATE_PATH) as img:
            img.load()
        print(f"Downloaded skin template → {TEMPLATE_PATH}")
    except Exception as exc:
        print(f"Template download failed ({exc}); creating blank 64×64 template.")
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(TEMPLATE_PATH, "PNG")


def init_session() -> None:
    """Lazily create a session backup folder for this run."""
    global SESSION_ID, SESSION_BACKUP_DIR
    if SESSION_ID is not None:
        return
    SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
    SESSION_BACKUP_DIR = BACKUP_DIR / f"session_{SESSION_ID}"
    SESSION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_file(src: Path | str) -> None:
    """Copy a file into the current session backup folder."""
    init_session()
    src = Path(src)
    if not src.is_file() or SESSION_BACKUP_DIR is None:
        return
    dest = SESSION_BACKUP_DIR / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        n = 1
        while dest.exists():
            dest = SESSION_BACKUP_DIR / f"{stem}_{n}{suffix}"
            n += 1
    try:
        shutil.copy2(src, dest)
    except Exception as exc:
        print(f"Warning: backup failed for {src.name}: {exc}")


def confirm(prompt: str = "Continue?") -> bool:
    ans = input(f"{prompt} [Y/n]: ").strip().lower()
    return ans in ("", "y", "yes")


def append_log(log_path: Path, line: str) -> None:
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")
    except Exception as exc:
        print(f"Warning: could not write log: {exc}")


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Config / credentials
# ---------------------------------------------------------------------------


def _parse_kv_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    except Exception:
        pass
    return data


def _write_kv_file(
    path: Path,
    data: dict[str, str],
    header_lines: Optional[list[str]] = None,
) -> None:
    lines = list(header_lines or [])
    lines.extend(f"{k}={v}" for k, v in data.items())
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"Warning: could not write {path.name}: {exc}")


def load_credentials() -> dict[str, str]:
    return _parse_kv_file(CREDENTIALS_PATH)


def save_credential(key: str, value: str) -> None:
    data = load_credentials()
    data[key] = value
    _write_kv_file(
        CREDENTIALS_PATH,
        data,
        header_lines=[
            "# API keys – one key=value per line",
            "# tinify_api_key=",
            "# tinyurl_api_key=",
        ],
    )


def load_settings() -> dict[str, str]:
    return _parse_kv_file(SETTINGS_PATH)


def save_setting(key: str, value: str) -> None:
    data = load_settings()
    data[key] = value
    _write_kv_file(
        SETTINGS_PATH,
        data,
        header_lines=[
            "# Custom folders – one key=value per line",
            "# input_folder=",
            "# output_folder=",
        ],
    )


def get_effective_input_dir() -> Path:
    custom = load_settings().get("input_folder", "").strip()
    if custom and Path(custom).is_dir():
        return Path(custom)
    return INPUT_DIR


def get_effective_output_dir() -> Path:
    custom = load_settings().get("output_folder", "").strip()
    if custom and Path(custom).is_dir():
        return Path(custom)
    return OUTPUT_DIR


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def list_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file())


def ask_files(images_only: bool = False) -> Optional[list[Path]]:
    """
    Unified 3-option file picker used by every file-based tool.

      1. All in input folder
      2. All in script folder
      3. Explicit path(s) (comma or pipe separated)

    Returns a list of Path objects, or None if the user backs out.
    """
    label = "images" if images_only else "files"
    input_dir = get_effective_input_dir()

    print(f"\n1. All {label} in input folder ({input_dir})")
    print(f"2. All {label} in script folder ({SCRIPT_DIR})")
    print("3. Enter full path(s)")
    print("0. Back")
    choice = input("Choice: ").strip()

    if choice == "0":
        return None

    if choice == "1":
        items = list_images(input_dir) if images_only else list_files(input_dir)
        if not items:
            print(f"No {label} found in input folder.")
            return None
        print(f"Found {len(items)} {label}.")
        return items

    if choice == "2":
        items = list_images(SCRIPT_DIR) if images_only else list_files(SCRIPT_DIR)
        if not items:
            print(f"No {label} found in script folder.")
            return None
        print(f"Found {len(items)} {label}.")
        return items

    if choice == "3":
        raw = input("Path(s) separated by , or | : ").strip()
        parts: list[str] = []
        for sep in (",", "|"):
            if sep in raw:
                parts = [p.strip() for p in raw.split(sep) if p.strip()]
                break
        if not parts and raw:
            parts = [raw]

        items = [Path(p).expanduser() for p in parts if Path(p).expanduser().is_file()]
        if images_only:
            items = [p for p in items if p.suffix.lower() in IMAGE_EXTS]
        if not items:
            print(f"No valid {label}.")
            return None
        return items

    print("Invalid.")
    return None


def ask_output_mode() -> Optional[str]:
    """Return 'overwrite', 'output', or None (back)."""
    out_dir = get_effective_output_dir()
    print("\n1. Overwrite original files")
    print(f"2. Save to output folder ({out_dir})")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return None
    return "overwrite" if choice == "1" else "output"


def resolve_output_path(src: Path, mode: str, suffix: str = "") -> Path:
    if mode == "overwrite":
        if not suffix:
            return src
        return src.with_name(f"{src.stem}{suffix}{src.suffix}")

    out_dir = get_effective_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{src.stem}{suffix}{src.suffix}" if suffix else src.name
    return out_dir / name


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError("Invalid hex")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def normalize_uuid(u: str) -> str:
    u = u.strip().replace("-", "").lower()
    if len(u) != 32:
        raise ValueError("Invalid UUID")
    return u


def format_uuid(u: str) -> str:
    u = normalize_uuid(u)
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def http_get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def http_post_json(
    url: str, payload: dict, headers: Optional[dict] = None
) -> dict:
    data = json.dumps(payload).encode("utf-8")
    hdrs = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Content-Length": str(len(data)),
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def random_bin(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def open_preview(path: Path | str) -> None:
    """Open an image with the system default viewer."""
    path = str(path)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            for cmd in ("xdg-open", "gio", "gnome-open", "kde-open"):
                if shutil.which(cmd):
                    os.system(f'{cmd} "{path}" >/dev/null 2>&1 &')
                    return
            with Image.open(path) as im:
                im.show()
    except Exception as exc:
        print(f"Could not open preview: {exc}")


# ---------------------------------------------------------------------------
# Mojang / NameMC
# ---------------------------------------------------------------------------


def username_to_uuid(name: str) -> tuple[str, str]:
    data = http_get(f"https://api.mojang.com/users/profiles/minecraft/{name.strip()}")
    return data["id"], data["name"]


def uuid_to_username(uuid: str) -> tuple[str, str]:
    uuid = normalize_uuid(uuid)
    data = http_get(
        f"https://api.minecraftservices.com/minecraft/profile/lookup/{uuid}"
    )
    return data["id"], data["name"]


def get_textures(uuid: str) -> tuple[dict, str]:
    uuid = normalize_uuid(uuid)
    data = http_get(
        f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
    )
    for prop in data.get("properties", []):
        if prop["name"] == "textures":
            decoded = json.loads(base64.b64decode(prop["value"]).decode())
            return decoded.get("textures", {}), data.get("name", "unknown")
    return {}, data.get("name", "unknown")


def download_skin(identifier: str) -> None:
    identifier = identifier.strip()
    try:
        if len(identifier.replace("-", "")) == 32:
            uuid, name = uuid_to_username(identifier)
        else:
            uuid, name = username_to_uuid(identifier)
    except Exception as exc:
        print(f"Lookup failed: {exc}")
        return

    print(f"{name} → {format_uuid(uuid)}")
    if not confirm("Download skin/cape?"):
        return

    try:
        textures, _ = get_textures(uuid)
    except Exception as exc:
        print(f"Texture fetch failed: {exc}")
        return

    out_dir = get_effective_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if "SKIN" in textures:
        path = out_dir / f"{name}_skin.png"
        path.write_bytes(http_get_bytes(textures["SKIN"]["url"]))
        print(f"Skin: {path}")
    else:
        print("No custom skin.")

    if "CAPE" in textures:
        path = out_dir / f"{name}_cape.png"
        path.write_bytes(http_get_bytes(textures["CAPE"]["url"]))
        print(f"Cape: {path}")


def open_namemc(identifier: str) -> None:
    identifier = identifier.strip()
    try:
        if len(identifier.replace("-", "")) == 32:
            _, name = uuid_to_username(identifier)
        else:
            _, name = username_to_uuid(identifier)
    except Exception as exc:
        print(f"Lookup failed: {exc}")
        return

    url = f"https://namemc.com/profile/{name}"
    print(url)
    if confirm("Open in browser and log?"):
        webbrowser.open(url)
        append_log(NAMEMC_LOG, f"{now_stamp()} - {identifier} -> {url}")


def run_username_to_uuid() -> None:
    name = input("Username (or 0 to go back): ").strip()
    if name in ("0", ""):
        return
    if not confirm(f"Look up UUID for '{name}'?"):
        return
    try:
        uuid, official = username_to_uuid(name)
        formatted = format_uuid(uuid)
        print(f"{official} → {formatted}")
        print(f"Raw: {uuid}")
        append_log(USERNAME_LOG, f"{now_stamp()} - {name} -> {formatted}")
        print(f"Logged to {USERNAME_LOG}")
    except Exception as exc:
        print(f"Failed: {exc}")


def run_uuid_to_username() -> None:
    uuid = input("UUID (or 0 to go back): ").strip()
    if uuid in ("0", ""):
        return
    if not confirm(f"Look up username for '{uuid}'?"):
        return
    try:
        raw, name = uuid_to_username(uuid)
        formatted = format_uuid(raw)
        print(f"{formatted} → {name}")
        append_log(UUID_LOG, f"{now_stamp()} - {uuid} -> {name}")
        print(f"Logged to {UUID_LOG}")
    except Exception as exc:
        print(f"Failed: {exc}")


def run_download_skin() -> None:
    ident = input("Username or UUID (or 0 to go back): ").strip()
    if ident in ("0", ""):
        return
    download_skin(ident)


def run_namemc() -> None:
    ident = input("Username or UUID (or 0 to go back): ").strip()
    if ident in ("0", ""):
        return
    open_namemc(ident)


# ---------------------------------------------------------------------------
# Tinify
# ---------------------------------------------------------------------------


def run_tinify() -> None:
    try:
        import tinify
    except ImportError:
        print("tinify not installed. Run: pip install tinify")
        return

    creds = load_credentials()
    key = creds.get("tinify_api_key", "").strip()

    if key:
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
        print(f"Using saved Tinify API key: {masked}")
        if input("Use saved key? [Y/n]: ").strip().lower() in ("n", "no"):
            key = ""

    if not key:
        key = input(
            "Tinify API key (https://tinify.com/developers) (or 0 to go back): "
        ).strip()
        if key in ("0", ""):
            return
        if confirm("Save this API key?"):
            save_credential("tinify_api_key", key)
            print("API key saved to credentials.txt")

    tinify.key = key
    try:
        tinify.validate()
    except Exception as exc:
        print(f"Invalid key or connection error: {exc}")
        return

    images = ask_files(images_only=True)
    if images is None:
        return
    mode = ask_output_mode()
    if mode is None:
        return
    if not confirm(f"Compress {len(images)} image(s)?"):
        return

    for path in images:
        backup_file(path)
        try:
            source = tinify.from_file(str(path))
            out = resolve_output_path(
                path, mode, suffix="_compressed" if mode == "output" else ""
            )
            if mode == "overwrite":
                out = path
            source.to_file(str(out))
            print(f"Compressed: {out.name}")
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")

    try:
        print(f"Compressions this month: {tinify.compression_count}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# TinyURL
# ---------------------------------------------------------------------------


def create_tinyurl(
    long_url: str,
    api_key: str,
    domain: str = "tinyurl.com",
    alias: Optional[str] = None,
) -> dict:
    payload: dict = {"url": long_url, "domain": domain}
    if alias:
        payload["alias"] = alias
    return http_post_json(
        "https://api.tinyurl.com/create",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )


def run_tinyurl() -> None:
    creds = load_credentials()
    key = creds.get("tinyurl_api_key", "").strip()

    if key:
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
        print(f"Using saved TinyURL API key: {masked}")
        if input("Use saved key? [Y/n]: ").strip().lower() in ("n", "no"):
            key = ""

    if not key:
        key = input(
            "TinyURL API key (https://tinyurl.com/app/dev) (or 0 to go back): "
        ).strip()
        if key in ("0", ""):
            return
        if confirm("Save this API key?"):
            save_credential("tinyurl_api_key", key)
            print("API key saved to credentials.txt")

    print("\n1. Shorten a single URL")
    print("2. Shorten multiple URLs (one per line, empty line to finish)")
    print("0. Back")
    mode = input("Choice: ").strip()
    if mode == "0":
        return

    urls: list[str] = []
    if mode == "2":
        print("Enter URLs (empty line to finish):")
        while True:
            line = input().strip()
            if not line:
                break
            urls.append(line)
    else:
        url = input("Long URL: ").strip()
        if url:
            urls.append(url)

    if not urls:
        print("No URLs provided.")
        return

    domain = input("Domain [tinyurl.com]: ").strip() or "tinyurl.com"
    alias = None
    if len(urls) == 1:
        a = input("Custom alias (optional, leave empty): ").strip()
        if a:
            alias = a

    if not confirm(f"Shorten {len(urls)} URL(s)?"):
        return

    print()
    for long_url in urls:
        try:
            result = create_tinyurl(
                long_url,
                key,
                domain=domain,
                alias=alias if len(urls) == 1 else None,
            )
            data = result.get("data", {})
            short = data.get("tiny_url") or data.get("url")
            if short:
                print(f"{long_url}")
                print(f"  → {short}")
                append_log(LINK_LOG, f"{now_stamp()} - {long_url} -> {short}")
            else:
                print(f"Unexpected response for {long_url}: {result}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:300] if exc.fp else ""
            print(f"Failed {long_url}: HTTP {exc.code} - {body}")
        except Exception as exc:
            print(f"Failed {long_url}: {exc}")
    print(f"Logged to {LINK_LOG}")


# ---------------------------------------------------------------------------
# Filebin
# ---------------------------------------------------------------------------


def upload_to_filebin(filepath: Path, bin_name: str) -> dict:
    url = f"https://filebin.net/{bin_name}/{filepath.name}"
    data = filepath.read_bytes()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream",
            "User-Agent": "Mozilla/5.0",
            "Content-Length": str(len(data)),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def run_filebin() -> None:
    bin_name = input("Bin name (leave empty for random, 0 to go back): ").strip()
    if bin_name == "0":
        return
    if not bin_name:
        bin_name = random_bin()
        print(f"Using bin: {bin_name}")

    files = ask_files(images_only=False)
    if files is None:
        return
    if not confirm(f"Upload {len(files)} file(s) to bin '{bin_name}'?"):
        return

    print()
    for path in files:
        backup_file(path)
        try:
            upload_to_filebin(path, bin_name)
            out_url = f"https://filebin.net/{bin_name}/{path.name}"
            print(f"Uploaded: {out_url}")
            append_log(BIN_LOG, f"{now_stamp()} - {path} -> {out_url}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:100] if exc.fp else ""
            print(f"Failed {path.name}: HTTP {exc.code} - {body}")
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")
    print(f"\nBin URL: https://filebin.net/{bin_name}")
    print(f"Logged to {BIN_LOG}")


# ---------------------------------------------------------------------------
# Recolor
# ---------------------------------------------------------------------------


def get_hue(r: int, g: int, b: int) -> int:
    mn, mx = min(r, g, b), max(r, g, b)
    if mn == mx:
        return 0
    if mx == r:
        h = (g - b) / (mx - mn)
    elif mx == g:
        h = 2.0 + (b - r) / (mx - mn)
    else:
        h = 4.0 + (r - g) / (mx - mn)
    h *= 60
    if h < 0:
        h += 360
    return round(h)


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    df = mx - mn
    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60 * ((g - b) / df) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / df) + 120) % 360
    else:
        h = (60 * ((r - g) / df) + 240) % 360
    s = 0.0 if mx == 0 else df / mx
    return h / 360.0, s, mx


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    if s == 0.0:
        val = int(v * 255)
        return val, val, val
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def tint(img: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    cr, cg, cb = color
    img = img.convert("RGBA").copy()
    pixels = [
        ((r + cr) // 2, (g + cg) // 2, (b + cb) // 2, a)
        for r, g, b, a in img.getdata()
    ]
    img.putdata(pixels)
    return img


def hue_shift(img: Image.Image, i_hue: int) -> Image.Image:
    hue = i_hue / 360.0
    img = img.convert("RGBA")
    new_pixels = []
    for r, g, b, a in img.getdata():
        if ((r << 16) | (g << 8) | b) != 0x00FFFFFF:
            h, s, v = _rgb_to_hsv(r, g, b)
            nr, ng, nb = _hsv_to_rgb(hue, s, v)
            new_pixels.append((nr, ng, nb, a))
        else:
            new_pixels.append((r, g, b, a))
    out = Image.new("RGBA", img.size)
    out.putdata(new_pixels)
    return out


def run_recolor() -> None:
    print("\n1. Hue Shift")
    print("2. Tint")
    print("0. Back")
    mode = input("Choice: ").strip()
    if mode == "0":
        return
    if mode not in ("1", "2"):
        print("Invalid.")
        return

    try:
        color = hex_to_rgb(input("Hex color: ").strip())
    except ValueError:
        print("Invalid hex.")
        return

    images = ask_files(images_only=True)
    if images is None:
        return
    out_mode = ask_output_mode()
    if out_mode is None:
        return
    if not confirm(f"Recolor {len(images)} image(s)?"):
        return

    for path in images:
        backup_file(path)
        try:
            with Image.open(path) as img:
                result = (
                    hue_shift(img, get_hue(*color))
                    if mode == "1"
                    else tint(img, color)
                )
                out_path = resolve_output_path(path, out_mode)
                if out_path.suffix.lower() in (".jpg", ".jpeg"):
                    result = result.convert("RGB")
                    result.save(out_path, quality=95)
                else:
                    result.save(out_path)
                print(f"Done: {out_path.name}")
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")


# ---------------------------------------------------------------------------
# Skin art
# ---------------------------------------------------------------------------


def _crop_for_skinart(image: Image.Image, align: str) -> Image.Image:
    """Return a 72×24 resized crop (1=top, 2=center, 3=bottom)."""
    ow, oh = image.size
    tw, th = 72, 24
    target_aspect = tw / th
    original_aspect = ow / oh

    if original_aspect > target_aspect:
        nw = int(oh * target_aspect)
        nh = oh
        left = (ow - nw) // 2
        top = 0
    else:
        nw = ow
        nh = int(ow / target_aspect)
        left = 0
        if align == "1":
            top = 0
        elif align == "3":
            top = oh - nh
        else:
            top = (oh - nh) // 2

    cropped = image.crop((left, top, left + nw, top + nh))
    return cropped.resize((tw, th), Image.Resampling.NEAREST)


def run_skinart() -> None:
    images = ask_files(images_only=True)
    if images is None:
        return
    path = images[0]
    if len(images) > 1:
        print("Using first image only.")

    if not TEMPLATE_PATH.is_file():
        print(f"Template missing: {TEMPLATE_PATH}")
        _download_or_create_template()
        if not TEMPLATE_PATH.is_file():
            print("Could not obtain template.")
            return

    align = "2"
    preview_path: Optional[Path] = None
    try:
        image = Image.open(path).convert("RGBA")
        while True:
            print("\n1. Top\n2. Center\n3. Bottom\n0. Back")
            choice = input(f"Align [{align}]: ").strip() or align
            if choice == "0":
                return
            if choice not in ("1", "2", "3"):
                print("Invalid.")
                continue
            align = choice
            preview = _crop_for_skinart(image, align)
            preview_path = (
                get_effective_output_dir() / f"_preview_skinart_{os.getpid()}.png"
            )
            preview.save(preview_path)
            print(f"Preview saved: {preview_path}")
            open_preview(preview_path)
            if confirm("Use this alignment?"):
                break
    except Exception as exc:
        print(f"Preview failed: {exc}")
        return
    finally:
        if preview_path and preview_path.is_file():
            try:
                preview_path.unlink()
            except Exception:
                pass

    out_mode = ask_output_mode()
    if out_mode is None:
        return

    if out_mode == "output":
        base_out = get_effective_output_dir()
        folder_name = input("Output subfolder name [skinart]: ").strip() or "skinart"
        output_folder = base_out / folder_name
    else:
        folder_name = input("Output folder name (relative to script): ").strip()
        if not folder_name:
            print("No folder name.")
            return
        output_folder = SCRIPT_DIR / folder_name

    if output_folder.exists():
        print("Folder already exists.")
        return
    if not confirm(f"Generate skin art into '{output_folder}'?"):
        return

    backup_file(path)
    output_folder.mkdir(parents=True)

    resized = _crop_for_skinart(image, align)
    template = Image.open(TEMPLATE_PATH).convert("RGBA")

    chunk = 8
    n = 1
    for y in range(24 - chunk, -1, -chunk):
        for x in range(72 - chunk, -1, -chunk):
            part = resized.crop((x, y, x + chunk, y + chunk))
            skin = template.copy()
            skin.paste(part, (8, 8), part if part.mode == "RGBA" else None)
            skin.save(output_folder / f"skin{n}.png")
            n += 1
    print(f"Saved {n - 1} skins → {output_folder}")


# ---------------------------------------------------------------------------
# Sky maker (simplified)
# ---------------------------------------------------------------------------


def run_sky() -> None:
    images = ask_files(images_only=True)
    if images is None:
        return

    while True:
        print("\n--- Sky options ---")
        print("These settings are kept for compatibility; the simplified")
        print("sky maker only copies/resizes the panorama into the asset files.")
        res_in = input("Target max edge size for assets [2048] (0=back): ").strip()
        if res_in == "0":
            return
        face_size = int(res_in) if res_in.isdigit() and int(res_in) > 0 else 2048

        h_flip = input("Horizontal flip? [y/N]: ").strip().lower() in ("y", "yes")
        v_flip = input("Vertical flip? [y/N]: ").strip().lower() in ("y", "yes")

        try:
            preview = Image.open(images[0]).convert("RGB")
            if h_flip:
                preview = preview.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if v_flip:
                preview = preview.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            max_prev = 1024
            w, h = preview.size
            if max(w, h) > max_prev:
                scale = max_prev / max(w, h)
                preview = preview.resize(
                    (int(w * scale), int(h * scale)), Image.Resampling.LANCZOS
                )
            preview_path = (
                get_effective_output_dir() / f"_preview_sky_{os.getpid()}.png"
            )
            preview.save(preview_path)
            print(f"Preview: {preview_path}")
            open_preview(preview_path)
            ok = confirm("Use these settings?")
            try:
                preview_path.unlink()
            except Exception:
                pass
            if ok:
                break
        except Exception as exc:
            print(f"Preview failed: {exc}")
            if not confirm("Continue without preview?"):
                return
            break

    out_mode = ask_output_mode()
    if out_mode is None:
        return

    out_base = (
        get_effective_output_dir()
        if out_mode == "output"
        else images[0].parent
    )

    if not confirm(f"Generate sky packs for {len(images)} image(s)?"):
        return

    for path in images:
        backup_file(path)
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sky_dir = out_base / f"sky_{stamp}"
            n = 1
            while sky_dir.exists():
                sky_dir = out_base / f"sky_{stamp}_{n}"
                n += 1
            sky_dir.mkdir(parents=True)

            img = Image.open(path).convert("RGB")
            if h_flip:
                img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if v_flip:
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            w, h = img.size
            longest = max(w, h)
            if longest > face_size:
                scale = face_size / longest
                img = img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS,
                )

            for name in SKY_ASSET_NAMES:
                img.save(sky_dir / name, "PNG")
            print(f"Created {sky_dir} ({len(SKY_ASSET_NAMES)} assets)")
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")


# ---------------------------------------------------------------------------
# File content replacer
# ---------------------------------------------------------------------------


def run_file_content_replacer() -> None:
    """
    Replace the content of selected files with the text from a source .txt.

    Target selection uses the same 3-option picker as every other file tool.
    An optional extension filter can further narrow the list.
    """
    print("\n--- File Content Replacer ---")
    print("Provide a .txt file containing the replacement content.")
    print("Then select the target files (same 3 input types as other tools).")
    print("0. Back")

    source_raw = input("Source .txt file path: ").strip()
    if source_raw in ("0", ""):
        return

    source_path = Path(source_raw).expanduser().resolve()
    if not source_path.is_file():
        print(f"File not found: {source_path}")
        return

    try:
        replacement_content = source_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Could not read source file: {exc}")
        return

    print("\nSelect target files:")
    targets = ask_files(images_only=False)
    if targets is None:
        return

    # Optional extension filter
    ext_filter = input(
        "Optional extension filter (e.g. .license, leave empty for all): "
    ).strip()
    if ext_filter == "0":
        return
    if ext_filter:
        if not ext_filter.startswith("."):
            ext_filter = "." + ext_filter
        if any(c in ext_filter for c in "*?/\\"):
            print("Invalid file extension.")
            return
        targets = [p for p in targets if p.suffix.lower() == ext_filter.lower()]
        if not targets:
            print(f"No files matching extension '{ext_filter}'.")
            return

    # Never overwrite the source itself
    targets = [p for p in targets if p.resolve() != source_path]

    if not targets:
        print("No target files remaining.")
        return

    print(f"\nFound {len(targets)} file(s):")
    for p in targets:
        print(f"  {p}")

    if not confirm(
        f"Replace the content of {len(targets)} file(s) "
        f"with '{source_path.name}'?"
    ):
        return

    print()
    success = failed = 0
    for path in targets:
        try:
            backup_file(path)
            path.write_text(replacement_content, encoding="utf-8")
            print(f"Updated: {path}")
            success += 1
        except Exception as exc:
            print(f"Failed: {path} -> {exc}")
            failed += 1

    print(f"\nCompleted: {success} updated, {failed} failed.")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def run_settings() -> None:
    while True:
        settings = load_settings()
        print("\nCurrent settings:")
        print(f"  input_folder  = {settings.get('input_folder') or INPUT_DIR}")
        print(f"  output_folder = {settings.get('output_folder') or OUTPUT_DIR}")
        print("\n1. Set custom input folder")
        print("2. Set custom output folder")
        print("3. Reset input folder to default")
        print("4. Reset output folder to default")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "0":
            return
        if choice == "1":
            path = input("New input folder path: ").strip()
            if path and Path(path).is_dir():
                if confirm("Save this input folder?"):
                    save_setting("input_folder", path)
                    print("Saved.")
            else:
                print("Invalid or missing directory.")
        elif choice == "2":
            path = input("New output folder path: ").strip()
            if path and Path(path).is_dir():
                if confirm("Save this output folder?"):
                    save_setting("output_folder", path)
                    print("Saved.")
            else:
                print("Invalid or missing directory.")
        elif choice == "3":
            if confirm("Reset input folder to default?"):
                data = load_settings()
                data.pop("input_folder", None)
                _write_kv_file(
                    SETTINGS_PATH,
                    data,
                    header_lines=[
                        "# Custom folders – one key=value per line",
                        "# input_folder=",
                        "# output_folder=",
                    ],
                )
                print("Input folder reset to default.")
        elif choice == "4":
            if confirm("Reset output folder to default?"):
                data = load_settings()
                data.pop("output_folder", None)
                _write_kv_file(
                    SETTINGS_PATH,
                    data,
                    header_lines=[
                        "# Custom folders – one key=value per line",
                        "# input_folder=",
                        "# output_folder=",
                    ],
                )
                print("Output folder reset to default.")
        else:
            print("Invalid.")


# ---------------------------------------------------------------------------
# Main menu (sorted by category)
# ---------------------------------------------------------------------------


def main() -> None:
    ensure_folders()

    while True:
        print("\n-------- Faltu by Ecoson --------")
        print("1. Recolor image(s)")
        print("2. Compress image(s) (Tinify)")
        print("3. Generate Minecraft Skin Art")
        print("4. Generate Minecraft Sky")
        print("5. Username -> UUID")
        print("6. UUID -> Username")
        print("7. Download Minecraft skin and cape")
        print("8. NameMC profile")
        print("9. Share files (Filebin)")
        print("10. Shorten link (TinyURL)")
        print("11. Replace file contents")
        print("12. Settings")
        print("0. Exit")
        choice = input("Choice: ").strip()

        if choice == "0":
            print("Bye.")
            break
        elif choice == "1":
            run_recolor()
        elif choice == "2":
            run_tinify()
        elif choice == "3":
            run_skinart()
        elif choice == "4":
            run_sky()
        elif choice == "5":
            run_username_to_uuid()
        elif choice == "6":
            run_uuid_to_username()
        elif choice == "7":
            run_download_skin()
        elif choice == "8":
            run_namemc()
        elif choice == "9":
            run_filebin()
        elif choice == "10":
            run_tinyurl()
        elif choice == "11":
            run_file_content_replacer()
        elif choice == "12":
            run_settings()
        else:
            print("Invalid.")


if __name__ == "__main__":
    main()
