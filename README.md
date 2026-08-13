# Faltu

A Python utility toolkit that does silly stuff.  
**Vibe coded by Ecoson.** 🐈

Faltu is a small interactive command line toolkit for image processing, Minecraft utilities, file sharing, link shortening, and general file operations.

It is designed to be simple: start the script, choose an option from the menu, and follow the prompts.

## Features

### 🖼️ Image tools

- **Recolor images**
  - Hue shift
  - Tint with a custom hexadecimal color
  - Supports PNG, JPG, JPEG, BMP, WEBP, TIFF, and TIF
  - Can overwrite the original or save a copy to the output folder

- **Compress images with Tinify**
  - Uses the Tinify API
  - Requires a Tinify API key
  - Supports batch image compression
  - Creates backups before modifying files

- **Generate Minecraft Skin Art**
  - Uses a 64×64 Minecraft skin template
  - Takes an image and turns it into multiple skin textures
  - Lets you choose top, center, or bottom image alignment
  - Creates a separate output folder for the generated skins

- **Generate Minecraft Sky**
  - Uses an input panorama/image
  - Supports horizontal and vertical flipping
  - Resizes the image to a selected maximum edge size
  - Generates the required sky asset filenames

### ⛏️ Minecraft tools

- **Username → UUID**
  - Looks up a Minecraft username using Mojang’s API

- **UUID → Username**
  - Looks up the current Minecraft username from a UUID

- **Download skin / cape**
  - Accepts a Minecraft username or UUID
  - Downloads the player’s skin and cape when available

- **NameMC profile**
  - Opens the player’s NameMC profile in your browser
  - Saves the generated profile URL to a log

### 🔗 Sharing & links

- **Filebin upload**
  - Uploads one or more files to Filebin
  - Lets you choose a custom bin name or generate one automatically
  - Saves generated links to a log

- **TinyURL**
  - Shortens one or multiple URLs
  - Supports a custom domain
  - Supports a custom alias for single URLs
  - Requires a TinyURL API key

### 🛠️ Utilities

- **Replace file contents**
  - Reads replacement text from a `.txt` file
  - Replaces the contents of selected files
  - Optional file extension filtering
  - Automatically avoids replacing the source `.txt` file itself
  - Creates backups before replacing files

- **Settings**
  - Set a custom input folder
  - Set a custom output folder
  - Reset either folder back to the defaults

## Requirements

You need:

- **Python 3**
- **Pillow**
- An internet connection for features that use online APIs or downloads

The Tinify feature additionally requires:

- **tinify**

TinyURL and Tinify features also require their respective API keys.

## Installation

You can run Faltu directly from its source code. No compilation is required.

### Windows

1. Install Python from the official Python website.
2. During installation, enable **Add Python to PATH**.
3. Open PowerShell or Command Prompt.
4. Go to the folder containing `Faltu.py`.

```powershell
cd "C:\path\to\Faltu"
```

5. Install the required package:

```powershell
py -m pip install Pillow
```

For Tinify support:

```powershell
py -m pip install tinify
```

6. Start Faltu:

```powershell
py Faltu.py
```

If `py` is unavailable, try:

```powershell
python Faltu.py
```

### Linux

1. Make sure Python 3 and pip are installed.

On Debian/Ubuntu based systems:

```bash
sudo apt update
sudo apt install python3 python3-pip
```

2. Install Pillow:

```bash
python3 -m pip install Pillow
```

If your Linux distribution uses an externally managed Python environment, use a virtual environment instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Pillow
```

For Tinify:

```bash
python -m pip install tinify
```

3. Run Faltu:

```bash
python3 Faltu.py
```

You can also make the script executable:

```bash
chmod +x Faltu.py
./Faltu.py
```

The script already has a Python 3 shebang.

### macOS

1. Install Python 3.
2. Open Terminal.
3. Go to the Faltu folder:

```bash
cd "/path/to/Faltu"
```

4. Install Pillow:

```bash
python3 -m pip install Pillow
```

For Tinify:

```bash
python3 -m pip install tinify
```

5. Run:

```bash
python3 Faltu.py
```

If your Python installation prevents global package installation, use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Pillow
```

## First Run

On the first launch, Faltu automatically creates its working folders and configuration files.

The default structure looks like this:

```text
Faltu/
├── Faltu.py
└── faltu/
    ├── backup/
    ├── input/
    ├── output/
    │   └── text_output/
    └── config/
        ├── credentials.txt
        ├── settings.txt
        └── resources/
            └── skinTemplate.png
```

The skin template is automatically downloaded when it is missing. If the download fails, Faltu creates a blank 64×64 template instead.

## How to Use

Start the program:

```bash
python Faltu.py
```

You will see the main menu:

```text
-------- Faltu by Ecoson --------
--- Image tools ---
1.  Recolor image(s)
2.  Compress image(s) (Tinify)
3.  Generate Minecraft Skin Art
4.  Generate Minecraft Sky
--- Minecraft lookups ---
5.  Username → UUID
6.  UUID → Username
7.  Download skin / cape
8.  NameMC profile
--- Sharing & links ---
9.  Share files (Filebin)
10. Shorten link (TinyURL)
--- Utilities ---
11. Replace file contents
12. Settings
0.  Exit
```

Enter the number of the tool you want and follow the prompts.

### Selecting files

Most file based tools give you three choices:

```text
1. All files in input folder
2. All files in script folder
3. Enter full path(s)
0. Back
```

For explicit paths, multiple files can be separated with:

```text
,
```

or:

```text
|
```

Example:

```text
/home/user/image1.png,/home/user/image2.png
```

Windows example:

```text
C:\Users\You\Pictures\a.png,C:\Users\You\Pictures\b.png
```

### Output modes

Many image tools let you choose:

```text
1. Overwrite original files
2. Save to output folder
```

Faltu creates backups before operations that can modify files.

## API Keys

API credentials are stored in:

```text
faltu/config/credentials.txt
```

The file uses simple `key=value` lines.

Example:

```text
tinify_api_key=YOUR_TINIFY_KEY
tinyurl_api_key=YOUR_TINYURL_KEY
```

### Tinify

Get a Tinify API key from:

```text
https://tinify.com/developers
```

Then either enter it when Faltu asks, or save it in `credentials.txt`.

### TinyURL

Get a TinyURL API key from:

```text
https://tinyurl.com/app/dev
```

Then enter it when prompted or save it in `credentials.txt`.

**Do not publish `credentials.txt` or commit real API keys to Git.**

## Custom Input and Output Folders

Faltu normally uses:

```text
faltu/input/
faltu/output/
```

You can change these from:

```text
12. Settings
```

The custom folder must already exist.

You can reset either folder back to the default location from the same menu.

## Logs

Text based results are stored in:

```text
faltu/output/text_output/
```

Current logs include:

```text
username.txt
uuid.txt
bin.txt
link.txt
namemc.txt
```

These contain timestamps and the results of relevant operations.

## Backups

Before changing files, Faltu creates a session backup inside:

```text
faltu/backup/
```

Each run that changes files can create a folder similar to:

```text
session_20260813_221500/
```

This helps keep the original files safe before destructive operations.

## Notes

- Faltu is an interactive terminal application, not a graphical application.
- Most tools work without an API key.
- Tinify requires the `tinify` Python package and a valid Tinify API key.
- TinyURL requires a valid TinyURL API key.
- Minecraft lookup and download features require an internet connection.
- Filebin uploads require an internet connection.
- The generated Minecraft sky tool is intentionally simplified. It copies/resizes the processed panorama into the expected sky asset filenames rather than building a full six-faced cubemap.
- Faltu stores configuration relative to the script directory, so you can normally move the whole project together.

## Troubleshooting

### `ModuleNotFoundError: No module named 'PIL'`

Install Pillow:

```bash
python -m pip install Pillow
```

or on systems where `python3` is required:

```bash
python3 -m pip install Pillow
```

### `tinify not installed`

Install the optional Tinify package:

```bash
python -m pip install tinify
```

### Python command not found

Try the platform specific commands:

```text
Windows: py
macOS/Linux: python3
```

### Permission errors

Make sure you have permission to read and write the files and folders you selected. Using the default `faltu/input` and `faltu/output` directories is usually the easiest option.

### API or network errors

Check that:

- Your internet connection is working.
- The requested service is available.
- Your API key is valid when one is required.
- The username, UUID, URL, or file path you entered is correct.

## License

See the repository's license file for licensing information.

## Disclaimer

Faltu is a personal, experimental utility toolkit. Features depend on external services such as Mojang APIs, NameMC, Tinify, TinyURL, and Filebin, so those features may stop working or change if the external services change.

---

Made with Python, questionable ideas, and a little too much free time. 🐈
