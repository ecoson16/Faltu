#!/usr/bin/env python3

from __future__ import annotations
import base64
import codecs
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urlparse

from PIL import Image

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

TEMPLATE_URL = "https://raw.githubusercontent.com/ecoson16/Faltu/main/skinTemplate.png"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}

SESSION_ID: Optional[str] = None
SESSION_BACKUP_DIR: Optional[Path] = None

DOWNLOAD_DIR = SCRIPT_DIR / "downloads"
THUMBNAIL_DIR = DOWNLOAD_DIR / "thumbnails"


def ensure_folders() -> None:
    for path in (
        FALTU_DIR,
        BACKUP_DIR,
        INPUT_DIR,
        OUTPUT_DIR,
        CONFIG_DIR,
        RESOURCES_DIR,
        TEXT_OUTPUT_DIR,
        DOWNLOAD_DIR,
        THUMBNAIL_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)

    if not CREDENTIALS_PATH.is_file():
        CREDENTIALS_PATH.write_text(
            "# API keys – one key=value per line\n"
            "# tinify_api_key=\n",
            encoding="utf-8",
        )

    if not SETTINGS_PATH.is_file():
        SETTINGS_PATH.write_text(
            "# Custom folders – one key=value per line\n"
            "# input_folder=\n"
            "# output_folder=\n",
            encoding="utf-8",
        )

    for log in (USERNAME_LOG, UUID_LOG, BIN_LOG):
        if not log.is_file():
            log.write_text("", encoding="utf-8")

    if not TEMPLATE_PATH.is_file():
        _download_or_create_template()


def _download_or_create_template() -> None:
    try:
        req = urllib.request.Request(TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"})
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
    global SESSION_ID, SESSION_BACKUP_DIR
    if SESSION_ID is not None:
        return
    SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
    SESSION_BACKUP_DIR = BACKUP_DIR / f"session_{SESSION_ID}"
    SESSION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_file(src: Path | str) -> bool:
    init_session()
    src = Path(src)
    if not src.is_file() or SESSION_BACKUP_DIR is None:
        return False
    dest = SESSION_BACKUP_DIR / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        n = 1
        while dest.exists():
            dest = SESSION_BACKUP_DIR / f"{stem}_{n}{suffix}"
            n += 1
    try:
        shutil.copy2(src, dest)
        return True
    except Exception as exc:
        print(f"Warning: backup failed for {src.name}: {exc}")
        return False


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


def _write_kv_file(path: Path, data: dict[str, str], header_lines: Optional[list[str]] = None) -> None:
    lines = list(header_lines or [])
    lines.extend(f"{k}={v}" for k, v in data.items())
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"Warning: could not write {path.name}: {exc}")


def _set_private_permissions(path: Path) -> None:
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass


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
        ],
    )
    _set_private_permissions(CREDENTIALS_PATH)


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


def _is_valid_path(p: Path, root: Path) -> bool:
    if not p.is_file():
        return False
    if FALTU_DIR in p.parents:
        return False
    if any(part.startswith('.') for part in p.relative_to(root).parts[:-1]):
        return False
    return True


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if _is_valid_path(p, folder) and p.suffix.lower() in IMAGE_EXTS)


def list_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if _is_valid_path(p, folder))


def ask_files(images_only: bool = False) -> Optional[list[Path]]:
    label = "images" if images_only else "files"
    input_dir = get_effective_input_dir()

    print(f"\n1. All {label} in input folder ({input_dir})")
    print(f"2. All {label} in current folder ({SCRIPT_DIR})")
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
            print(f"No {label} found in current folder.")
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
    out_dir = get_effective_output_dir()
    while True:
        print("\n1. Overwrite original files")
        print(f"2. Save to output folder ({out_dir})")
        print("0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return None
        if choice == "1":
            return "overwrite"
        if choice == "2":
            return "output"
        print("Invalid.")


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
    if not re.fullmatch(r"[0-9a-f]{32}", u):
        raise ValueError("Invalid UUID")
    return u


def format_uuid(u: str) -> str:
    u = normalize_uuid(u)
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


def http_get(url: str, timeout: int = 15, retries: int = 2) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Faltu/1.0 (+https://github.com/ecoson16/Faltu)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = min(float(retry_after), 10.0) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            time.sleep(delay)
    raise last_error or RuntimeError("HTTP request failed")


def http_get_bytes(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Faltu/1.0 (+https://github.com/ecoson16/Faltu)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def random_bin(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def open_preview(path: Path | str) -> None:
    path = str(Path(path).resolve())
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for cmd in ("xdg-open", "gio", "gnome-open", "kde-open"):
                if shutil.which(cmd):
                    subprocess.Popen([cmd, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            with Image.open(path) as im:
                im.show()
    except Exception as exc:
        print(f"Could not open preview: {exc}")


def username_to_uuid(name: str) -> tuple[str, str]:
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", name):
        raise ValueError("Invalid Minecraft username")
    encoded = quote(name, safe="")
    data = http_get(f"https://api.minecraftservices.com/minecraft/profile/lookup/name/{encoded}")
    return data["id"], data["name"]


def uuid_to_username(uuid: str) -> tuple[str, str]:
    uuid = normalize_uuid(uuid)
    data = http_get(f"https://api.minecraftservices.com/minecraft/profile/lookup/{uuid}")
    return data["id"], data["name"]


def get_textures(uuid: str) -> tuple[dict, str]:
    uuid = normalize_uuid(uuid)
    data = http_get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}")
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
    if not confirm("Download Minecraft skin?"):
        return

    try:
        textures, _ = get_textures(uuid)
    except Exception as exc:
        print(f"Texture fetch failed: {exc}")
        return

    out_dir = get_effective_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if "SKIN" in textures:
        safe_name = sanitize_filename(name)
        path = out_dir / f"{safe_name}_skin.png"
        path.write_bytes(http_get_bytes(textures["SKIN"]["url"]))
        print(f"Skin: {path}")
    else:
        print("No custom skin.")


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
        key = input("Tinify API key (https://tinify.com/developers) (or 0 to go back): ").strip()
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
        if mode == "overwrite" and not backup_file(path):
            print(f"Skipped {path.name}: could not create a backup.")
            continue
        try:
            source = tinify.from_file(str(path))
            out = resolve_output_path(path, mode, suffix="_compressed" if mode == "output" else "")
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


def upload_to_filebin(filepath: Path, bin_name: str) -> dict:
    import requests

    if not filepath.is_file():
        raise FileNotFoundError(filepath)

    url = f"https://filebin.net/{quote(bin_name, safe='')}/{quote(filepath.name, safe='')}"
    size = filepath.stat().st_size
    headers = {
        "Content-Type": "application/octet-stream",
        "User-Agent": "Faltu/1.0 (+https://github.com/ecoson16/Faltu)",
        "Content-Length": str(size),
    }
    with filepath.open("rb") as fh:
        response = requests.post(url, data=fh, headers=headers, timeout=(15, 300))
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status": response.status_code, "response": response.text[:500]}


def run_filebin() -> None:
    bin_name = input("Bin name (leave empty for random, 0 to go back): ").strip()
    if bin_name == "0":
        return
    if not bin_name:
        bin_name = random_bin()
        print(f"Using bin: {bin_name}")
    elif not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", bin_name):
        print("Invalid bin name. Use 1–64 letters, numbers, _ or - only.")
        return

    files = ask_files(images_only=False)
    if files is None:
        return
    if not confirm(f"Upload {len(files)} file(s) to bin '{bin_name}'?"):
        return

    print()
    uploaded = 0
    for path in files:
        try:
            upload_to_filebin(path, bin_name)
            out_url = f"https://filebin.net/{quote(bin_name, safe='')}/{quote(path.name, safe='')}"
            print(f"Uploaded: {out_url}")
            append_log(BIN_LOG, f"{now_stamp()} - {path} -> {out_url}")
            uploaded += 1
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")

    if uploaded:
        print(f"\nShareable Link: https://filebin.net/{quote(bin_name, safe='')}")
        print("Files are automatically deleted by Filebin after 6 days.")
    else:
        print("\nNo files were uploaded.")
    print(f"Logged to {BIN_LOG}")


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


def _pixels(img: Image.Image):
    get_flattened_data = getattr(img, "get_flattened_data", None)
    return get_flattened_data() if get_flattened_data is not None else img.getdata()


def tint(img: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    cr, cg, cb = color
    img = img.convert("RGBA").copy()
    pixels = [
        ((r + cr) // 2, (g + cg) // 2, (b + cb) // 2, a)
        for r, g, b, a in _pixels(img)
    ]
    img.putdata(pixels)
    return img


def hue_shift(img: Image.Image, i_hue: int) -> Image.Image:
    shift = (i_hue % 360) / 360.0
    img = img.convert("RGBA")
    new_pixels = []
    for r, g, b, a in _pixels(img):
        if ((r << 16) | (g << 8) | b) != 0x00FFFFFF:
            h, s, v = _rgb_to_hsv(r, g, b)
            shifted_hue = (h + shift) % 1.0
            nr, ng, nb = _hsv_to_rgb(shifted_hue, s, v)
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
        if out_mode == "overwrite" and not backup_file(path):
            print(f"Skipped {path.name}: could not create a backup.")
            continue
        try:
            with Image.open(path) as img:
                result = hue_shift(img, get_hue(*color)) if mode == "1" else tint(img, color)
                out_path = resolve_output_path(path, out_mode)
                if out_path.suffix.lower() in (".jpg", ".jpeg"):
                    result = result.convert("RGB")
                    result.save(out_path, quality=95)
                else:
                    result.save(out_path)
                print(f"Done: {out_path.name}")
        except Exception as exc:
            print(f"Failed {path.name}: {exc}")


def _crop_for_skinart(image: Image.Image, align: str) -> Image.Image:
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


def _safe_child_path(base: Path, name: str) -> Path | None:
    name = name.strip()
    if not name or Path(name).is_absolute():
        return None
    candidate = (base / name).resolve()
    base_resolved = base.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None
    return candidate


def _is_text_file(path: Path) -> bool:
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                if b"\x00" in chunk:
                    return False
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        return True
    except (OSError, UnicodeDecodeError):
        return False


def _atomic_write_text(path: Path, content: str) -> None:
    temp = path.with_name(f".{path.name}.faltu-tmp")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


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
            preview_path = get_effective_output_dir() / f"_preview_skinart_{os.getpid()}.png"
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
        output_folder = _safe_child_path(base_out, folder_name)
    else:
        folder_name = input("Output folder name (relative to current folder): ").strip()
        output_folder = _safe_child_path(SCRIPT_DIR, folder_name)

    if output_folder is None:
        print("Invalid folder name. Use a relative path inside the selected base folder.")
        return

    if output_folder.exists():
        print("Folder already exists.")
        return
    if not confirm(f"Generate skin art into '{output_folder}'?"):
        return

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


def run_file_content_replacer() -> None:
    print("\n--- File Content Replacer ---")
    print("Provide a .txt file containing the replacement content.")
    print("Then select the target files.")
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

    inc_raw = input("Extensions to include (comma-separated, e.g. .txt,.md, empty for all): ").strip()
    if inc_raw and inc_raw != "0":
        inc_exts = {ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}" for ext in inc_raw.split(",")}
        targets = [p for p in targets if p.suffix.lower() in inc_exts]

    exc_raw = input("Extensions to exclude (comma-separated, e.g. .json,.exe, empty for none): ").strip()
    if exc_raw and exc_raw != "0":
        exc_exts = {ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}" for ext in exc_raw.split(",")}
        targets = [p for p in targets if p.suffix.lower() not in exc_exts]

    targets = [p for p in targets if p.resolve() != source_path]
    unsafe_targets = [p for p in targets if not _is_text_file(p)]
    if unsafe_targets:
        print("Skipping non-UTF-8/binary targets:")
        for p in unsafe_targets:
            print(f"  {p}")
        targets = [p for p in targets if p not in unsafe_targets]

    if not targets:
        print("No text targets remaining.")
        return

    print(f"\nFound {len(targets)} file(s):")
    for p in targets:
        print(f"  {p}")

    if not confirm(f"Replace the content of {len(targets)} file(s) with '{source_path.name}'?"):
        return

    print()
    success = failed = 0
    for path in targets:
        try:
            if not backup_file(path):
                print(f"Failed: {path} -> backup could not be created")
                failed += 1
                continue
            _atomic_write_text(path, replacement_content)
            print(f"Updated: {path}")
            success += 1
        except Exception as exc:
            print(f"Failed: {path} -> {exc}")
            failed += 1

    print(f"\nCompleted: {success} updated, {failed} failed.")


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


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "youtube_video"


def get_video_id(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None

    host = parsed.netloc.lower().split(":", 1)[0]
    if host in {"youtu.be", "www.youtu.be"}:
        match = re.match(r"/([A-Za-z0-9_-]{11})(?:/|$)", parsed.path)
        return match.group(1) if match else None

    if host not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
    }:
        return None

    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", query_id):
        return query_id

    match = re.match(r"^/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})(?:/|$)", parsed.path)
    return match.group(1) if match else None


def format_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


def _get_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Run: python -m pip install yt-dlp") from exc
    return yt_dlp


class QuietLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(f"\nError: {msg}")


class Progress:
    def __init__(self):
        self.start_time = None
        self.last_update = 0

    def hook(self, data):
        if data["status"] == "downloading":
            if self.start_time is None:
                self.start_time = time.monotonic()

            now = time.monotonic()
            if now - self.last_update < 0.5:
                return

            self.last_update = now
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            speed = data.get("speed") or 0

            if total:
                progress = f"{downloaded / total * 100:6.2f}%"
            else:
                progress = f"{downloaded / 1024 / 1024:.1f} MB"

            if speed:
                speed_text = f"{speed / 1024 / 1024:.2f} MB/s"
            else:
                speed_text = "-- MB/s"

            elapsed = format_time(time.monotonic() - self.start_time)

            print(
                f"\rDownloading  {progress}  {speed_text}  Elapsed {elapsed}",
                end="",
                flush=True,
            )

        elif data["status"] == "finished":
            print("\rDownload complete.                              ")


def get_info(url: str):
    yt_dlp = _get_yt_dlp()
    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": QuietLogger(),
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def download_thumbnail(video_id: str, title: str) -> Path | None:
    import requests
    from io import BytesIO

    resolutions = (
        "maxresdefault.jpg",
        "sddefault.jpg",
        "hqdefault.jpg",
        "mqdefault.jpg",
        "default.jpg",
    )

    filename = f"{sanitize_filename(title)} [{video_id}].jpg"
    path = THUMBNAIL_DIR / filename
    session = requests.Session()
    session.headers["User-Agent"] = "Faltu/1.0"

    for resolution in resolutions:
        url = f"https://img.youtube.com/vi/{video_id}/{resolution}"
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("image/"):
                continue
            with Image.open(BytesIO(response.content)) as image:
                image.verify()
            path.write_bytes(response.content)
            return path
        except (requests.RequestException, OSError):
            continue

    return None


def download_video(url: str, title: str, video_id: str) -> bool:
    yt_dlp = _get_yt_dlp()
    progress = Progress()
    safe_title = sanitize_filename(title)
    outtmpl = str(DOWNLOAD_DIR / f"{safe_title} [{video_id}].%(ext)s")
    options = {
        "format": "bestvideo+bestaudio/best",
        "format_sort": ["res", "fps", "vcodec", "acodec", "br"],
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": QuietLogger(),
        "progress_hooks": [progress.hook],
        "skip_unavailable_fragments": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.download([url])
        if result not in (None, 0):
            return False
        matches = list(DOWNLOAD_DIR.glob(f"{safe_title} [{video_id}].*"))
        matches = [p for p in matches if not p.name.endswith((".part", ".ytdl"))]
        if not matches:
            print("\nDownload finished without a final output file.")
            return False
        return True
    except KeyboardInterrupt:
        print("\nDownload stopped.")
        return False
    except Exception as e:
        print(f"\nDownload failed: {e}")
        return False


def run_youtube_downloader() -> None:
    url = input("YouTube URL (or 0 to go back): ").strip()
    if url == "0":
        return
    if not url:
        print("No URL provided.")
        return

    video_id = get_video_id(url)
    if not video_id:
        print("Invalid YouTube URL.")
        return

    try:
        info = get_info(url)
    except Exception as e:
        print(f"Could not retrieve video information: {e}")
        return

    if info.get("is_live"):
        print("Live streams are not supported.")
        return

    title = info.get("title") or "youtube_video"
    print(f"\nTitle: {title}")
    print("Type: VIDEO")

    print("\nWhat do you want to download?")
    print("[1] Video")
    print("[2] Thumbnail")
    print("[3] Both")
    print("[0] Back")

    choice = input("\nChoose 1, 2, or 3 (or 0 to go back): ").strip()
    if choice == "0":
        return
    if choice not in {"1", "2", "3"}:
        print("Invalid choice.")
        return

    if choice in {"2", "3"}:
        print("\nDownloading thumbnail...")
        thumbnail = download_thumbnail(video_id, title)
        if thumbnail:
            print(f"Thumbnail saved: {thumbnail}")
        else:
            print("Thumbnail unavailable.")

    if choice in {"1", "3"}:
        print("\nStarting video download...")
        video_ok = download_video(url, title, video_id)
        print("Video saved successfully." if video_ok else "Video download failed.")

    print("\nDone.")


def main() -> None:
    ensure_folders()

    while True:
        print("\n-------- Faltu by Ecoson --------")
        print("1. Recolor image(s)")
        print("2. Compress image(s)")
        print("3. Generate Minecraft Skin Art")
        print("4. Minecraft Username → UUID")
        print("5. Minecraft UUID → Username")
        print("6. Download Minecraft skin")
        print("7. Share file(s)")
        print("8. Replace file contents")
        print("9. Settings")
        print("10. Download YouTube Video/Thumbnail")
        print("0. Exit")
        choice = input("Choice: ").strip()

        if choice == "0":
            print("Meow!")
            break
        elif choice == "1":
            run_recolor()
        elif choice == "2":
            run_tinify()
        elif choice == "3":
            run_skinart()
        elif choice == "4":
            run_username_to_uuid()
        elif choice == "5":
            run_uuid_to_username()
        elif choice == "6":
            run_download_skin()
        elif choice == "7":
            run_filebin()
        elif choice == "8":
            run_file_content_replacer()
        elif choice == "9":
            run_settings()
        elif choice == "10":
            run_youtube_downloader()
        else:
            print("Invalid.")


if __name__ == "__main__":
    main()
