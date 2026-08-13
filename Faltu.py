#!/usr/bin/env python3
"""
Utility toolkit: image recolor, mcskinart gen, mcsky gen, mojang lookups,
image compress, filebin upload, link shortener.
"""

import os
import sys
import json
import base64
import shutil
import random
import string
import webbrowser
import urllib.request
import urllib.error
from datetime import datetime

from PIL import Image

# ============================================================
#                    GLOBAL SESSION STATE
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FALTU_DIR = os.path.join(SCRIPT_DIR, "faltu")
BACKUP_DIR = os.path.join(FALTU_DIR, "backup")
INPUT_DIR = os.path.join(FALTU_DIR, "input")
OUTPUT_DIR = os.path.join(FALTU_DIR, "output")
CONFIG_DIR = os.path.join(FALTU_DIR, "config")
RESOURCES_DIR = os.path.join(CONFIG_DIR, "resources")
TEXT_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "text_output")
CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials.txt")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.txt")
TEMPLATE_PATH = os.path.join(RESOURCES_DIR, "skinTemplate.png")

# Text log files
USERNAME_LOG = os.path.join(TEXT_OUTPUT_DIR, "username.txt")
UUID_LOG = os.path.join(TEXT_OUTPUT_DIR, "uuid.txt")
BIN_LOG = os.path.join(TEXT_OUTPUT_DIR, "bin.txt")
LINK_LOG = os.path.join(TEXT_OUTPUT_DIR, "link.txt")
NAMEMC_LOG = os.path.join(TEXT_OUTPUT_DIR, "namemc.txt")

SESSION_ID = None
SESSION_BACKUP_DIR = None

# Public template URL (standard 64x64 Minecraft skin template).
# If download fails, a blank 64x64 RGBA template is generated instead.
TEMPLATE_URL = "https://github.com/ecoson16/Faltu/blob/main/skinTemplate.png"


def ensure_folders():
    """Create required folders and files only if they do not already exist."""
    for path in (
        FALTU_DIR,
        BACKUP_DIR,
        INPUT_DIR,
        OUTPUT_DIR,
        CONFIG_DIR,
        RESOURCES_DIR,
        TEXT_OUTPUT_DIR,
    ):
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)

    if not os.path.isfile(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            f.write("# API keys – remove the # before editing manually (Not from this line)\n")
            f.write("# tinify_api_key=\n")
            f.write("# tinyurl_api_key=\n")

    if not os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write("# Custom folders - remove the # before editing manually (Not from this line)\n")
            f.write("# input_folder=\n")
            f.write("# output_folder=\n")

    # Text output logs
    for log_path in (USERNAME_LOG, UUID_LOG, BIN_LOG, LINK_LOG, NAMEMC_LOG):
        if not os.path.isfile(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")

    # Skin template
    if not os.path.isfile(TEMPLATE_PATH):
        _download_or_create_template()


def _download_or_create_template():
    """Download the skin template; on failure create a blank 64x64 RGBA image."""
    try:
        req = urllib.request.Request(
            TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        with open(TEMPLATE_PATH, "wb") as f:
            f.write(data)
        # Validate it is a usable image
        with Image.open(TEMPLATE_PATH) as img:
            img.load()
        print(f"Downloaded skin template → {TEMPLATE_PATH}")
    except Exception as e:
        print(f"Template download failed ({e}); creating blank 64x64 template.")
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        img.save(TEMPLATE_PATH, "PNG")


def init_session():
    """Create a single session backup folder for this script run (lazy)."""
    global SESSION_ID, SESSION_BACKUP_DIR
    if SESSION_ID is not None:
        return
    SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
    SESSION_BACKUP_DIR = os.path.join(BACKUP_DIR, f"session_{SESSION_ID}")
    os.makedirs(SESSION_BACKUP_DIR, exist_ok=True)


def backup_file(src_path):
    """Copy a file into the current session backup folder. Only called after confirmation."""
    init_session()
    if not os.path.isfile(src_path):
        return
    name = os.path.basename(src_path)
    dest = os.path.join(SESSION_BACKUP_DIR, name)
    if os.path.exists(dest):
        base, ext = os.path.splitext(name)
        n = 1
        while os.path.exists(dest):
            dest = os.path.join(SESSION_BACKUP_DIR, f"{base}_{n}{ext}")
            n += 1
    try:
        shutil.copy2(src_path, dest)
    except Exception as e:
        print(f"Warning: backup failed for {name}: {e}")


def confirm(prompt="Continue?"):
    """Ask for yes/no confirmation. Returns True on yes."""
    ans = input(f"{prompt} [Y/n]: ").strip().lower()
    return ans in ("", "y", "yes")


def append_log(log_path, line):
    """Append a single line to a text log file."""
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except Exception as e:
        print(f"Warning: could not write log: {e}")


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
#                    CONFIG / CREDENTIALS
# ============================================================

def _parse_kv_file(path):
    data = {}
    if not os.path.isfile(path):
        return data
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


def _write_kv_file(path, data, header_lines=None):
    lines = []
    if header_lines:
        lines.extend(header_lines)
    for k, v in data.items():
        lines.append(f"{k}={v}")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"Warning: could not write {os.path.basename(path)}: {e}")


def load_credentials():
    return _parse_kv_file(CREDENTIALS_PATH)


def save_credential(key, value):
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


def load_settings():
    return _parse_kv_file(SETTINGS_PATH)


def save_setting(key, value):
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


def get_effective_input_dir():
    settings = load_settings()
    custom = settings.get("input_folder", "").strip()
    if custom and os.path.isdir(custom):
        return custom
    return INPUT_DIR


def get_effective_output_dir():
    settings = load_settings()
    custom = settings.get("output_folder", "").strip()
    if custom and os.path.isdir(custom):
        return custom
    return OUTPUT_DIR


# ============================================================
#                         HELPERS
# ============================================================

def list_images(folder):
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}
    if not os.path.isdir(folder):
        return []
    return sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in exts
    ])


def list_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ])


def ask_files(images_only=False):
    """
    Prompt for files:
      1. All in input folder
      2. All in script folder
      3. Specific path(s) separated by , or |
    Returns list of paths, or None if user cancels / goes back.
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
        paths = input("Path(s) separated by , or | : ").strip()
        # Support both , and | as separators (no required spaces)
        parts = []
        for sep in (",", "|"):
            if sep in paths:
                parts = [p.strip() for p in paths.split(sep) if p.strip()]
                break
        if not parts:
            parts = [paths] if paths else []
        items = [p for p in parts if os.path.isfile(p)]
        if images_only:
            exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}
            items = [p for p in items if os.path.splitext(p)[1].lower() in exts]
        if not items:
            print(f"No valid {label}.")
            return None
        return items

    print("Invalid.")
    return None


def ask_output_mode():
    """
    Returns "overwrite", "output", or None (back).
    """
    out_dir = get_effective_output_dir()
    print("\n1. Overwrite original files")
    print(f"2. Save to output folder ({out_dir})")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return None
    return "overwrite" if choice == "1" else "output"


def resolve_output_path(src_path, mode, suffix=""):
    if mode == "overwrite":
        if not suffix:
            return src_path
        base, ext = os.path.splitext(src_path)
        return f"{base}{suffix}{ext}"

    out_dir = get_effective_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(src_path)
    if suffix:
        base, ext = os.path.splitext(name)
        name = f"{base}{suffix}{ext}"
    return os.path.join(out_dir, name)


def hex_to_rgb(hex_color):
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError("Invalid hex")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def normalize_uuid(u):
    u = u.strip().replace("-", "").lower()
    if len(u) != 32:
        raise ValueError("Invalid UUID")
    return u


def format_uuid(u):
    u = normalize_uuid(u)
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def http_get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def http_post_json(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    hdrs = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Content-Length": str(len(data)),
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def random_bin(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def pixel_data(img):
    if hasattr(img, "get_flattened_data"):
        return img.get_flattened_data()
    return img.getdata()


def open_preview(path):
    """Open an image with the system default viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            # Linux / other
            for cmd in ("xdg-open", "gio", "gnome-open", "kde-open"):
                if shutil.which(cmd):
                    os.system(f'{cmd} "{path}" >/dev/null 2>&1 &')
                    return
            # Fallback: try PIL show (may open via ImageMagick / display)
            with Image.open(path) as im:
                im.show()
    except Exception as e:
        print(f"Could not open preview: {e}")


# ============================================================
#                    MOJANG / NAMEMC
# ============================================================

def username_to_uuid(name):
    data = http_get(f"https://api.mojang.com/users/profiles/minecraft/{name.strip()}")
    return data["id"], data["name"]


def uuid_to_username(uuid):
    uuid = normalize_uuid(uuid)
    data = http_get(f"https://api.minecraftservices.com/minecraft/profile/lookup/{uuid}")
    return data["id"], data["name"]


def get_textures(uuid):
    uuid = normalize_uuid(uuid)
    data = http_get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}")
    for prop in data.get("properties", []):
        if prop["name"] == "textures":
            decoded = json.loads(base64.b64decode(prop["value"]).decode())
            return decoded.get("textures", {}), data.get("name", "unknown")
    return {}, data.get("name", "unknown")


def download_skin(identifier):
    identifier = identifier.strip()
    try:
        if len(identifier.replace("-", "")) == 32:
            uuid, name = uuid_to_username(identifier)
        else:
            uuid, name = username_to_uuid(identifier)
    except Exception as e:
        print(f"Lookup failed: {e}")
        return
    print(f"{name} → {format_uuid(uuid)}")
    if not confirm("Download skin/cape?"):
        return
    try:
        textures, _ = get_textures(uuid)
    except Exception as e:
        print(f"Texture fetch failed: {e}")
        return
    out_dir = get_effective_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    if "SKIN" in textures:
        path = os.path.join(out_dir, f"{name}_skin.png")
        with open(path, "wb") as f:
            f.write(http_get_bytes(textures["SKIN"]["url"]))
        print(f"Skin: {path}")
    else:
        print("No custom skin.")
    if "CAPE" in textures:
        path = os.path.join(out_dir, f"{name}_cape.png")
        with open(path, "wb") as f:
            f.write(http_get_bytes(textures["CAPE"]["url"]))
        print(f"Cape: {path}")


def open_namemc(identifier):
    identifier = identifier.strip()
    try:
        if len(identifier.replace("-", "")) == 32:
            _, name = uuid_to_username(identifier)
        else:
            _, name = username_to_uuid(identifier)
    except Exception as e:
        print(f"Lookup failed: {e}")
        return
    url = f"https://namemc.com/profile/{name}"
    print(url)
    if confirm("Open in browser and log?"):
        webbrowser.open(url)
        append_log(
            NAMEMC_LOG,
            f"{now_stamp()} - {identifier} -> {url}",
        )


def run_username_to_uuid():
    name = input("Username (or 0 to go back): ").strip()
    if name == "0" or not name:
        return
    if not confirm(f"Look up UUID for '{name}'?"):
        return
    try:
        uuid, official = username_to_uuid(name)
        formatted = format_uuid(uuid)
        print(f"{official} → {formatted}")
        print(f"Raw: {uuid}")
        append_log(
            USERNAME_LOG,
            f"{now_stamp()} - {name} -> {formatted}",
        )
        print(f"Logged to {USERNAME_LOG}")
    except Exception as e:
        print(f"Failed: {e}")


def run_uuid_to_username():
    uuid = input("UUID (or 0 to go back): ").strip()
    if uuid == "0" or not uuid:
        return
    if not confirm(f"Look up username for '{uuid}'?"):
        return
    try:
        raw, name = uuid_to_username(uuid)
        formatted = format_uuid(raw)
        print(f"{formatted} → {name}")
        append_log(
            UUID_LOG,
            f"{now_stamp()} - {uuid} -> {name}",
        )
        print(f"Logged to {UUID_LOG}")
    except Exception as e:
        print(f"Failed: {e}")


def run_download_skin():
    ident = input("Username or UUID (or 0 to go back): ").strip()
    if ident == "0" or not ident:
        return
    download_skin(ident)


def run_namemc():
    ident = input("Username or UUID (or 0 to go back): ").strip()
    if ident == "0" or not ident:
        return
    open_namemc(ident)


# ============================================================
#                         TINIFY
# ============================================================

def run_tinify():
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
        use_saved = input("Use saved key? [Y/n]: ").strip().lower()
        if use_saved in ("n", "no"):
            key = ""

    if not key:
        key = input("Tinify API key (https://tinify.com/developers) (or 0 to go back): ").strip()
        if key == "0" or not key:
            return
        if confirm("Save this API key?"):
            save_credential("tinify_api_key", key)
            print("API key saved to credentials.txt")

    tinify.key = key
    try:
        tinify.validate()
    except Exception as e:
        print(f"Invalid key or connection error: {e}")
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
            source = tinify.from_file(path)
            out = resolve_output_path(
                path, mode, suffix="_compressed" if mode == "output" else ""
            )
            if mode == "overwrite":
                out = path
            source.to_file(out)
            print(f"Compressed: {os.path.basename(out)}")
        except Exception as e:
            print(f"Failed {os.path.basename(path)}: {e}")

    try:
        print(f"Compressions this month: {tinify.compression_count}")
    except Exception:
        pass


# ============================================================
#                         TINYURL
# ============================================================

def create_tinyurl(long_url, api_key, domain="tinyurl.com", alias=None):
    payload = {"url": long_url, "domain": domain}
    if alias:
        payload["alias"] = alias
    headers = {"Authorization": f"Bearer {api_key}"}
    return http_post_json("https://api.tinyurl.com/create", payload, headers=headers)


def run_tinyurl():
    creds = load_credentials()
    key = creds.get("tinyurl_api_key", "").strip()

    if key:
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
        print(f"Using saved TinyURL API key: {masked}")
        use_saved = input("Use saved key? [Y/n]: ").strip().lower()
        if use_saved in ("n", "no"):
            key = ""

    if not key:
        key = input("TinyURL API key (https://tinyurl.com/app/dev) (or 0 to go back): ").strip()
        if key == "0" or not key:
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

    urls = []
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
                long_url, key, domain=domain,
                alias=alias if len(urls) == 1 else None,
            )
            data = result.get("data", {})
            short = data.get("tiny_url") or data.get("url")
            if short:
                print(f"{long_url}")
                print(f"  → {short}")
                append_log(
                    LINK_LOG,
                    f"{now_stamp()} - {long_url} -> {short}",
                )
            else:
                print(f"Unexpected response for {long_url}: {result}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300] if e.fp else ""
            print(f"Failed {long_url}: HTTP {e.code} - {body}")
        except Exception as e:
            print(f"Failed {long_url}: {e}")
    print(f"Logged to {LINK_LOG}")


# ============================================================
#                         FILEBIN
# ============================================================

def upload_to_filebin(filepath, bin_name):
    filename = os.path.basename(filepath)
    url = f"https://filebin.net/{bin_name}/{filename}"
    with open(filepath, "rb") as f:
        data = f.read()
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


def run_filebin():
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
            filename = os.path.basename(path)
            out_url = f"https://filebin.net/{bin_name}/{filename}"
            print(f"Uploaded: {out_url}")
            append_log(
                BIN_LOG,
                f"{now_stamp()} - {path} -> {out_url}",
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:100] if e.fp else ""
            print(f"Failed {os.path.basename(path)}: HTTP {e.code} - {body}")
        except Exception as e:
            print(f"Failed {os.path.basename(path)}: {e}")
    print(f"\nBin URL: https://filebin.net/{bin_name}")
    print(f"Logged to {BIN_LOG}")


# ============================================================
#                         RECOLOR
# ============================================================

def get_hue(r, g, b):
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


def _rgb_to_hsv(r, g, b):
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


def _hsv_to_rgb(h, s, v):
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


def tint(img, color):
    cr, cg, cb = color
    img = img.convert("RGBA").copy()
    pixels = [
        ((r + cr) // 2, (g + cg) // 2, (b + cb) // 2, a)
        for r, g, b, a in pixel_data(img)
    ]
    img.putdata(pixels)
    return img


def hue_shift(img, i_hue):
    hue = i_hue / 360.0
    img = img.convert("RGBA")
    new_pixels = []
    for r, g, b, a in pixel_data(img):
        if ((r << 16) | (g << 8) | b) != 0x00FFFFFF:
            h, s, v = _rgb_to_hsv(r, g, b)
            nr, ng, nb = _hsv_to_rgb(hue, s, v)
            new_pixels.append((nr, ng, nb, a))
        else:
            new_pixels.append((r, g, b, a))
    out = Image.new("RGBA", img.size)
    out.putdata(new_pixels)
    return out


def run_recolor():
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
                if out_path.lower().endswith((".jpg", ".jpeg")):
                    result = result.convert("RGB")
                    result.save(out_path, quality=95)
                else:
                    result.save(out_path)
                print(f"Done: {os.path.basename(out_path)}")
        except Exception as e:
            print(f"Failed {os.path.basename(path)}: {e}")


# ============================================================
#                         SKINART
# ============================================================

def _crop_for_skinart(image, align):
    """Return the 72x24 resized crop according to align (1=top, 2=center, 3=bottom)."""
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


def run_skinart():
    images = ask_files(images_only=True)
    if images is None:
        return
    path = images[0]
    if len(images) > 1:
        print("Using first image only.")

    if not os.path.isfile(TEMPLATE_PATH):
        print(f"Template missing: {TEMPLATE_PATH}")
        _download_or_create_template()
        if not os.path.isfile(TEMPLATE_PATH):
            print("Could not obtain template.")
            return

    # Interactive alignment with preview
    align = "2"
    preview_path = None
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
            # Save temp preview
            preview_path = os.path.join(
                get_effective_output_dir(), f"_preview_skinart_{os.getpid()}.png"
            )
            preview.save(preview_path)
            print(f"Preview saved: {preview_path}")
            open_preview(preview_path)
            if confirm("Use this alignment?"):
                break
            # Allow changing again
    except Exception as e:
        print(f"Preview failed: {e}")
        return
    finally:
        if preview_path and os.path.isfile(preview_path):
            try:
                os.remove(preview_path)
            except Exception:
                pass

    out_mode = ask_output_mode()
    if out_mode is None:
        return

    if out_mode == "output":
        base_out = get_effective_output_dir()
        folder_name = input("Output subfolder name [skinart]: ").strip() or "skinart"
        output_folder = os.path.join(base_out, folder_name)
    else:
        output_folder = input("Output folder name (relative to script): ").strip()
        if not output_folder:
            print("No folder name.")
            return
        output_folder = os.path.join(SCRIPT_DIR, output_folder)

    if os.path.exists(output_folder):
        print("Folder already exists.")
        return

    if not confirm(f"Generate skin art into '{output_folder}'?"):
        return

    backup_file(path)
    os.makedirs(output_folder)

    resized = _crop_for_skinart(image, align)
    template = Image.open(TEMPLATE_PATH).convert("RGBA")

    chunk = 8
    n = 1
    for y in range(24 - chunk, -1, -chunk):
        for x in range(72 - chunk, -1, -chunk):
            part = resized.crop((x, y, x + chunk, y + chunk))
            skin = template.copy()
            skin.paste(part, (8, 8), part if part.mode == "RGBA" else None)
            skin.save(os.path.join(output_folder, f"skin{n}.png"))
            n += 1
    print(f"Saved {n - 1} skins → {output_folder}")


# ============================================================
#                         SKYMAKER (simplified)
# ============================================================

SKY_ASSET_NAMES = [
    "skybox.png",
    "skybox2.png",
    "cloud1.png",
    "cloud2.png",
    "starfield01.png",
    "starfield02.png",
    "starfield03.png",
    "starfield.png",
]


def run_sky():
    images = ask_files(images_only=True)
    if images is None:
        return

    # Simple options with optional preview of the source (user can re-pick)
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

        # Preview first image with current flips
        try:
            preview = Image.open(images[0]).convert("RGB")
            if h_flip:
                preview = preview.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if v_flip:
                preview = preview.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            # Downscale for quick preview if huge
            max_prev = 1024
            w, h = preview.size
            if max(w, h) > max_prev:
                scale = max_prev / max(w, h)
                preview = preview.resize(
                    (int(w * scale), int(h * scale)), Image.Resampling.LANCZOS
                )
            preview_path = os.path.join(
                get_effective_output_dir(), f"_preview_sky_{os.getpid()}.png"
            )
            preview.save(preview_path)
            print(f"Preview: {preview_path}")
            open_preview(preview_path)
            ok = confirm("Use these settings?")
            try:
                os.remove(preview_path)
            except Exception:
                pass
            if ok:
                break
        except Exception as e:
            print(f"Preview failed: {e}")
            if not confirm("Continue without preview?"):
                return
            break

    out_mode = ask_output_mode()
    if out_mode is None:
        return

    if out_mode == "output":
        out_base = get_effective_output_dir()
    else:
        out_base = os.path.dirname(os.path.abspath(images[0]))

    if not confirm(f"Generate sky packs for {len(images)} image(s)?"):
        return

    for path in images:
        backup_file(path)
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sky_dir = os.path.join(out_base, f"sky_{stamp}")
            # Avoid collision if multiple images processed in the same second
            n = 1
            while os.path.exists(sky_dir):
                sky_dir = os.path.join(out_base, f"sky_{stamp}_{n}")
                n += 1
            os.makedirs(sky_dir)

            img = Image.open(path).convert("RGB")
            if h_flip:
                img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if v_flip:
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Optionally downscale so longest edge == face_size
            w, h = img.size
            longest = max(w, h)
            if longest > face_size:
                scale = face_size / longest
                img = img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS,
                )

            for name in SKY_ASSET_NAMES:
                dest = os.path.join(sky_dir, name)
                img.save(dest, "PNG")
            print(f"Created {sky_dir} ({len(SKY_ASSET_NAMES)} assets)")
        except Exception as e:
            print(f"Failed {os.path.basename(path)}: {e}")


# ============================================================
#                     FILE CONTENT REPLACER
# ============================================================

def run_file_content_replacer():
    """Replace the content of recursively found files using a user-provided text file."""
    print("\n--- File Content Replacer ---")
    print("Provide a .txt file containing the replacement content.")
    print("Then choose the file extension whose contents should be replaced.")
    print("Example extension: .license or license")
    print("0. Back")

    source_path = input("Source .txt file path: ").strip()

    if source_path == "0":
        return

    if not source_path:
        print("No source file provided.")
        return

    source_path = os.path.abspath(os.path.expanduser(source_path))

    if not os.path.isfile(source_path):
        print(f"File not found: {source_path}")
        return

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            replacement_content = f.read()
    except Exception as e:
        print(f"Could not read source file: {e}")
        return

    extension = input("Target file extension (e.g. .license): ").strip()

    if extension == "0":
        return

    if not extension:
        print("No extension provided.")
        return

    if not extension.startswith("."):
        extension = "." + extension

    # Prevent accidental wildcard-like input.
    if any(char in extension for char in "*?/\\"):
        print("Invalid file extension.")
        return

    matches = []
    for path in Path(".").rglob(f"*{extension}"):
        if path.is_file():
            # Never overwrite the source text file if it happens to match.
            if os.path.abspath(str(path)) != source_path:
                matches.append(path)

    if not matches:
        print(f"No files with extension '{extension}' found.")
        return

    print(f"\nFound {len(matches)} file(s):")
    for path in matches:
        print(f"  {path}")

    if not confirm(f"Replace the content of {len(matches)} file(s) with '{os.path.basename(source_path)}'?"):
        return

    print()

    success = 0
    failed = 0

    for path in matches:
        try:
            backup_file(str(path))
            path.write_text(replacement_content, encoding="utf-8")
            print(f"Updated: {path}")
            success += 1
        except Exception as e:
            print(f"Failed: {path} -> {e}")
            failed += 1

    print(f"\nCompleted: {success} updated, {failed} failed.")


# ============================================================
#                    SETTINGS MENU
# ============================================================

def run_settings():
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
            if path and os.path.isdir(path):
                if confirm("Save this input folder?"):
                    save_setting("input_folder", path)
                    print("Saved.")
            else:
                print("Invalid or missing directory.")
        elif choice == "2":
            path = input("New output folder path: ").strip()
            if path and os.path.isdir(path):
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


# ============================================================
#                         MAIN
# ============================================================

def main():
    ensure_folders()
    # Session/backup folder is created lazily only when backup_file is first called

    while True:
        print("\n-------- Faltu by Ecoson --------")
        print("1.  Recolor image(s)")
        print("2.  Generate Minecraft Skin Art")
        print("3.  Generate Minecraft Sky")
        print("4.  Minecraft Username -> UUID")
        print("5.  Minecraft UUID -> Username")
        print("6.  Download Minecraft Skin")
        print("7.  NameMC Profile")
        print("8.  Compress image(s)")
        print("9.  Share files (Filebin)")
        print("10. Shorten link")
        print("11. Settings")
        print("12. Replace file contents")
        print("0.  Exit")
        choice = input("Choice: ").strip()

        if choice == "0":
            print("Bye.")
            break
        elif choice == "1":
            run_recolor()
        elif choice == "2":
            run_skinart()
        elif choice == "3":
            run_sky()
        elif choice == "4":
            run_username_to_uuid()
        elif choice == "5":
            run_uuid_to_username()
        elif choice == "6":
            run_download_skin()
        elif choice == "7":
            run_namemc()
        elif choice == "8":
            run_tinify()
        elif choice == "9":
            run_filebin()
        elif choice == "10":
            run_tinyurl()
        elif choice == "11":
            run_settings()
        elif choice == "12":
            run_file_content_replacer()
        else:
            print("Invalid.")


if __name__ == "__main__":
    main()
