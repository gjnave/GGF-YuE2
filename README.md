![YuE2 Music Studio — Get Going Fast](assets/yue2.png)

# YuE2 Music Studio (Low VRAM)

## A Get Going Fast Application

### [Quick Setup Helper → GetGoingFast.pro/tools/yue2](https://getgoingfast.pro/tools/yue2/)

The guided Windows installer is a separate member download. This public repository contains source and manual setup instructions, not a quick installer or model weights.

Create songs from lyrics and a musical style, make instrumentals with an optional adapter, and edit ABC compositions. Windows / NVIDIA / native audio.cpp GGUF inference. No ComfyUI, PyTorch installation or CUDA compilation is used by this app.

## Manual installation from source

Use Windows 64-bit with a current NVIDIA driver. Install [Git for Windows](https://git-scm.com/download/win) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then open **Command Prompt** in a writable folder on an internal drive:

1. Clone the source and create its private Python 3.12 environment:

   ```bat
   git clone https://codeberg.org/Cognibuild/GGF-YuE2.git
   cd GGF-YuE2
   uv venv --managed-python --python 3.12 .venv-3.12
   ```

2. Install dependencies and the pinned official audio.cpp 0.8.2 Windows CUDA 12.4 runtime:

   ```bat
   uv pip install --python .venv-3.12\Scripts\python.exe -r requirements.txt
   uv pip check --python .venv-3.12\Scripts\python.exe
   .venv-3.12\Scripts\python.exe setup_runtime.py
   ```

3. Download and verify a pinned model (Q8 is the default; Q4 uses less VRAM):

   ```bat
   .venv-3.12\Scripts\python.exe yue2_gguf_gui.py --download q8
   .venv-3.12\Scripts\python.exe yue2_gguf_gui.py --check
   ```

   Use `--download q4` as well if you want that variant. The optional instrumental LoRA can be downloaded in Settings.

4. Double-click `RUN.bat` from this source checkout, or run `.venv-3.12\Scripts\python.exe app.py`. The separate member installer automates the same setup without requiring Git or a system Python.

Allow at least 12 GB of disk space plus song storage. Q8 is the default; Q4 uses less VRAM. Hardware, song length and settings affect speed and memory. There is no arbitrary duration cap in the UI. The native process exits after every song and releases its GPU memory.

The instrumental LoRA is optional: download it in Settings, enable it in Create, select Full plan, then use `[instrumental]` or section tags instead of lyrics.

## Use it from your phone

In **Settings → Use it from your phone**, choose local Wi-Fi access or a temporary public link. Enter optional remote credentials, save, and restart the app. A blank password explicitly disables remote login; a nonblank password uses your username or `ggf` if the username is blank. The PC page is always login-free. Keep the PC/app running; generation does not run on the phone. Windows Firewall may need permission for LAN access. Use the remote URL printed in the app console; public URLs may change on restart.

Preferred local port: **7871**; remote: **8871**, with occupied-port fallback. Local and remote views share one inference lock. Stop generation affects only this app's native job, not other GPU apps. Settings also contains Release models and a confirmed Stop server; stopping the server requires restarting it on the PC.

## Songs, scores and recovery

Each run has a unique `outputs/song-<timestamp>-<random>/` folder containing the WAV master, downloadable FLAC/MP3, generation log and request settings. Download filenames are unique. Optional scores are saved as `score.abc`. **Download another format** converts the retained WAV; it never reruns inference.

The ABC Editor retains the original safe Save, Save As, import, generated-score and Use This Score behavior. Opening another score warns if unsaved edits would be lost. Your browser's random workspace ID restores controls, copied ABC input and last successful result after reload; files stay on the PC. A new public URL is a different browser origin and does not inherit the old browser ID. No cross-user workspace list is exposed.

## Update

Use **Settings → Check for updates / Update and restart**, or close the app and run `.venv-3.12\Scripts\python.exe update_app.py`. Updates check repository commits and use the hosts' automatically generated archives. A normal source push is sufficient; there is no manually rebuilt code ZIP dependency. Models, environment, outputs, workspace files and private access settings are preserved. Existing source is backed up before replacement. Codeberg is primary; GitHub is the fallback regardless of the original install source. Drive is an independent backup, not a required step for ordinary code updates.

## Licenses

Read `NOTICE.md`, `LICENSE-audio.cpp`, the original `disclaimer.md` and `about.nfo`. YuE2 model weights and the optional instrumental adapter are **CC BY-NC 4.0**; access to this installer does not grant different model rights. Upstream binary and dependency licenses remain applicable.
