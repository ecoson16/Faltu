import re
import sys
import time
import requests
from pathlib import Path
from urllib.parse import quote


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://api.minecraftservices.com"

CHECK_URL = (
    BASE_URL +
    "/minecraft/profile/name/{}/available"
)

TOKEN_TEST_URL = (
    BASE_URL +
    "/minecraft/profile/namechange"
)

INPUT_FILE = Path("Words.txt")

AVAILABLE_FILE = Path("available.txt")
TAKEN_FILE = Path("taken.txt")
NOT_ALLOWED_FILE = Path("not_allowed.txt")
INVALID_FORMAT_FILE = Path("invalid_format.txt")
ERROR_FILE = Path("errors.txt")

MIN_NAME_LENGTH = 3
MAX_NAME_LENGTH = 16

REQUESTS_PER_WINDOW = 20
WINDOW_SECONDS = 300

REQUEST_TIMEOUT = 20
MAX_RETRIES = 5

# Minecraft Java username character set.
VALID_NAME_RE = re.compile(
    rf"^[A-Za-z0-9_]{{{MIN_NAME_LENGTH},{MAX_NAME_LENGTH}}}$"
)


# ============================================================
# TOKEN
# ============================================================

TOKEN = input(
    "Minecraft Services access token: "
).strip()

if not TOKEN:
    raise SystemExit("No token entered.")


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "User-Agent": "MinecraftNameChecker/5.0",
})


# ============================================================
# TOKEN VALIDATION
# ============================================================

def validate_token():
    print(
        "Validating token...",
        end="",
        flush=True,
    )

    try:
        response = session.get(
            TOKEN_TEST_URL,
            timeout=REQUEST_TIMEOUT,
        )

    except requests.RequestException as exc:
        print(" FAILED")

        raise SystemExit(
            f"Could not contact Minecraft Services:\n{exc}"
        )

    if response.status_code == 200:
        print(" OK")
        return

    if response.status_code == 401:
        print(" INVALID")

        raise SystemExit(
            "Token is invalid or expired.\n"
            "No username checks were performed."
        )

    if response.status_code == 429:
        print(" RATE LIMITED")

        raise SystemExit(
            "Minecraft Services rate limited token validation.\n"
            "Wait and try again."
        )

    print(
        f" HTTP {response.status_code}"
    )

    raise SystemExit(
        "Unexpected response while validating token."
    )


# ============================================================
# LOAD INPUT
# ============================================================

def load_names():
    if not INPUT_FILE.exists():
        raise SystemExit(
            f"Input file not found: {INPUT_FILE}"
        )

    text = INPUT_FILE.read_text(
        encoding="utf-8"
    )

    # Spaces, newlines, tabs, etc. are separators.
    raw_names = text.split()

    # Remove exact duplicates first.
    unique_names = list(
        dict.fromkeys(raw_names)
    )

    valid_names = []
    invalid_names = []

    # Username uniqueness is effectively case-insensitive,
    # so avoid checking Eco / eco / ECO separately.
    seen_lower = set()

    for name in unique_names:

        if not VALID_NAME_RE.fullmatch(name):
            invalid_names.append(name)
            continue

        key = name.lower()

        if key in seen_lower:
            continue

        seen_lower.add(key)
        valid_names.append(name)

    # Save names that are syntactically impossible without
    # spending an API request.
    if invalid_names:
        with INVALID_FORMAT_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:

            for name in invalid_names:
                file.write(name + "\n")

    print(
        f"Input:          {len(raw_names):,}"
    )

    print(
        f"Unique:         {len(unique_names):,}"
    )

    print(
        f"Valid format:   {len(valid_names):,}"
    )

    print(
        f"Invalid format: {len(invalid_names):,}"
    )

    return valid_names


# ============================================================
# RESUME SUPPORT
# ============================================================

def load_checked_names():
    checked = set()

    for filename in (
        AVAILABLE_FILE,
        TAKEN_FILE,
        NOT_ALLOWED_FILE,
    ):
        if not filename.exists():
            continue

        for line in filename.read_text(
            encoding="utf-8"
        ).splitlines():

            name = line.strip()

            if name:
                checked.add(name.lower())

    return checked


# ============================================================
# RESULT WRITING
# ============================================================

def append_result(
    filename,
    name,
):
    with filename.open(
        "a",
        encoding="utf-8",
    ) as file:

        file.write(name + "\n")
        file.flush()


# ============================================================
# INLINE COUNTDOWN
# ============================================================

def countdown(seconds):
    end_time = (
        time.monotonic() +
        seconds
    )

    while True:

        remaining = (
            end_time -
            time.monotonic()
        )

        if remaining <= 0:
            break

        total = int(
            remaining
        )

        minutes, secs = divmod(
            total,
            60,
        )

        message = (
            f"[LIMIT] Next request in "
            f"{minutes:02d}:{secs:02d}"
        )

        sys.stdout.write(
            "\r" +
            message.ljust(60)
        )

        sys.stdout.flush()

        time.sleep(
            min(
                1.0,
                remaining,
            )
        )

    sys.stdout.write(
        "\r" +
        "[LIMIT] Sending next request...".ljust(60) +
        "\n"
    )

    sys.stdout.flush()


# ============================================================
# ROLLING RATE LIMITER
# ============================================================

class RateLimiter:

    def __init__(
        self,
        maximum,
        window_seconds,
    ):
        self.maximum = maximum
        self.window_seconds = window_seconds
        self.timestamps = []

    def cleanup(self):

        now = time.monotonic()

        self.timestamps = [
            timestamp
            for timestamp in self.timestamps
            if (
                now - timestamp
            ) < self.window_seconds
        ]

    def wait_for_slot(self):

        while True:

            self.cleanup()

            if (
                len(self.timestamps)
                < self.maximum
            ):
                return

            now = time.monotonic()

            wait_time = (
                self.window_seconds
                - (
                    now -
                    self.timestamps[0]
                )
                + 0.1
            )

            countdown(
                max(
                    0.1,
                    wait_time,
                )
            )

    def record(self):
        self.timestamps.append(
            time.monotonic()
        )


# ============================================================
# CHECK ONE USERNAME
# ============================================================

def check_name(
    name,
    limiter,
):
    encoded_name = quote(
        name,
        safe="",
    )

    url = CHECK_URL.format(
        encoded_name
    )

    retries = 0

    while True:

        # Every actual API request passes through the limiter.
        limiter.wait_for_slot()
        limiter.record()

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.RequestException as exc:

            retries += 1

            if retries >= MAX_RETRIES:

                return (
                    None,
                    f"NETWORK_ERROR: {exc}",
                )

            delay = min(
                2 ** retries,
                30,
            )

            print(
                f"\n[NETWORK] "
                f"Retrying {name} "
                f"in {delay}s...",
                flush=True,
            )

            time.sleep(delay)
            continue

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            try:
                data = response.json()

            except ValueError:

                return (
                    None,
                    "INVALID_JSON",
                )

            status = data.get(
                "status"
            )

            if status in {
                "AVAILABLE",
                "DUPLICATE",
                "NOT_ALLOWED",
            }:
                return (
                    status,
                    None,
                )

            return (
                None,
                f"UNKNOWN_STATUS: {data}",
            )

        # ----------------------------------------------------
        # INVALID / EXPIRED TOKEN
        # ----------------------------------------------------

        if response.status_code == 401:

            raise SystemExit(
                "\nToken became invalid or expired.\n"
                "Stopping immediately."
            )

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if response.status_code == 429:

            retry_after = (
                response.headers.get(
                    "Retry-After"
                )
            )

            try:
                wait_seconds = float(
                    retry_after
                )

            except (
                TypeError,
                ValueError,
            ):
                wait_seconds = (
                    WINDOW_SECONDS
                )

            countdown(
                max(
                    1,
                    wait_seconds,
                )
            )

            continue

        # ----------------------------------------------------
        # SERVER ERRORS
        # ----------------------------------------------------

        if response.status_code in {
            500,
            502,
            503,
            504,
        }:

            retries += 1

            if retries >= MAX_RETRIES:

                return (
                    None,
                    (
                        "SERVER_ERROR_HTTP_"
                        f"{response.status_code}"
                    ),
                )

            delay = min(
                2 ** retries,
                30,
            )

            print(
                f"\n[SERVER {response.status_code}] "
                f"Retrying {name} "
                f"in {delay}s...",
                flush=True,
            )

            time.sleep(delay)
            continue

        # ----------------------------------------------------
        # OTHER HTTP ERRORS
        # ----------------------------------------------------

        body = (
            response.text[:200]
            .replace("\n", " ")
            .replace("\r", " ")
        )

        return (
            None,
            f"HTTP_{response.status_code}: {body}",
        )


# ============================================================
# MAIN
# ============================================================

def main():

    validate_token()

    names = load_names()

    checked = load_checked_names()

    remaining = [
        name
        for name in names
        if (
            name.lower()
            not in checked
        )
    ]

    print(
        f"Previously checked: "
        f"{len(checked):,}"
    )

    print(
        f"Remaining:         "
        f"{len(remaining):,}"
    )

    print()

    if not remaining:
        print(
            "Nothing left to check."
        )
        return

    limiter = RateLimiter(
        REQUESTS_PER_WINDOW,
        WINDOW_SECONDS,
    )

    available = 0
    taken = 0
    not_allowed = 0
    errors = 0

    try:

        for index, name in enumerate(
            remaining,
            start=1,
        ):

            print(
                f"[{index}/{len(remaining)}] "
                f"Checking {name} ... ",
                end="",
                flush=True,
            )

            status, error = check_name(
                name,
                limiter,
            )

            if status == "AVAILABLE":

                print("AVAILABLE")

                append_result(
                    AVAILABLE_FILE,
                    name,
                )

                available += 1

            elif status == "DUPLICATE":

                print("TAKEN")

                append_result(
                    TAKEN_FILE,
                    name,
                )

                taken += 1

            elif status == "NOT_ALLOWED":

                print("NOT_ALLOWED")

                append_result(
                    NOT_ALLOWED_FILE,
                    name,
                )

                not_allowed += 1

            else:

                print(
                    f"ERROR: {error}"
                )

                append_result(
                    ERROR_FILE,
                    f"{name}\t{error}",
                )

                errors += 1

    except KeyboardInterrupt:

        print(
            "\n\nStopped by user."
        )

    print()
    print("Finished.")
    print(
        f"Available:   {available}"
    )
    print(
        f"Taken:       {taken}"
    )
    print(
        f"Not allowed: {not_allowed}"
    )
    print(
        f"Errors:      {errors}"
    )


if __name__ == "__main__":
    main()
