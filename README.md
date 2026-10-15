# YuE2 Music Studio — Get Going Fast

Create songs from lyrics and a musical style, make instrumentals with an optional adapter, and edit ABC compositions. Windows / NVIDIA / native audio.cpp GGUF inference. No ComfyUI, PyTorch installation or CUDA compilation is used by this app.

## Install and run

1. Download the small installer ZIP from [Get Going Fast](https://getgoingfast.pro/tools/yue2/), or clone this repository and use its installer.
2. Extract to a writable folder on your internal drive. Double-click **INSTALL.bat**. Keep the window open until setup finishes.
3. Double-click **RUN.bat**. The app files and private environment live in `GGF-YuE2` beside the BAT files.

You do not need system Python or Git. The CMD installer bootstraps pinned UV and provisions **64-bit Python 3.12**. It downloads app source from Codeberg, falling back to GitHub, installs dependencies, downloads and verifies the official audio.cpp 0.8.2 Windows CUDA 12.4 runtime, and downloads the selected pinned model with resume and SHA-256 checks. It does not install the system CUDA Toolkit or alter other apps. Install a current NVIDIA driver yourself.

Allow at least 12 GB of disk space plus song storage. Q8 is the default; Q4 uses less VRAM. Hardware, song length and settings affect speed and memory. There is no arbitrary duration cap in the UI. The native process exits after every song and releases its GPU memory.

`INSTALL.bat q4`, `INSTALL.bat q8`, or `INSTALL.bat both` selects the model without the menu. The instrumental LoRA is optional: download it in Settings, enable it in Create, select Full plan, then use `[instrumental]` or section tags instead of lyrics.

### Run directly from a source checkout

The simplest path is still to run the repository's INSTALL.bat and RUN.bat. Alternatively, with UV already installed, run these commands **inside the source checkout**:

```cmd
uv venv --managed-python --python 3.12 .venv-3.12
uv pip install --python .venv-3.12\Scripts\python.exe -r requirements.txt
.venv-3.12\Scripts\python.exe setup_runtime.py
.venv-3.12\Scripts\python.exe yue2_gguf_gui.py --download q8
.venv-3.12\Scripts\python.exe yue2_gguf_gui.py --check
.venv-3.12\Scripts\python.exe app.py
```

## Use it from your phone

In **Settings → Use it from your phone**, choose local Wi-Fi access or a temporary public link. Enter optional remote credentials, save, and restart the app. A blank password explicitly disables remote login; a nonblank password uses your username or `ggf` if the username is blank. The PC page is always login-free. Keep the PC/app running; generation does not run on the phone. Windows Firewall may need permission for LAN access. Use the remote URL printed in the app console; public URLs may change on restart.

Preferred local port: **7871**; remote: **8871**, with occupied-port fallback. Local and remote views share one inference lock. Stop generation affects only this app's native job, not other GPU apps. Settings also contains Release models and a confirmed Stop server; stopping the server requires restarting it on the PC.

## Songs, scores and recovery

Each run has a unique `outputs/song-<timestamp>-<random>/` folder containing the WAV master, downloadable FLAC/MP3, generation log and request settings. Download filenames are unique. Optional scores are saved as `score.abc`. **Download another format** converts the retained WAV; it never reruns inference.

The ABC Editor retains the original safe Save, Save As, import, generated-score and Use This Score behavior. Opening another score warns if unsaved edits would be lost. Your browser's random workspace ID restores controls, copied ABC input and last successful result after reload; files stay on the PC. A new public URL is a different browser origin and does not inherit the old browser ID. No cross-user workspace list is exposed.

## Update

Use **Settings → Check for updates / Update and restart**, or close the app and run UPDATE.bat. Updates check repository commits and use the hosts' automatically generated archives. A normal source push is sufficient; there is no manually rebuilt code ZIP dependency. Models, environment, outputs, workspace files and private access settings are preserved. Existing source is backed up before replacement. Codeberg is primary; GitHub is the fallback regardless of the original install source. Drive is an independent backup, not a required step for ordinary code updates.

## Licenses

Read `NOTICE.md`, `LICENSE-audio.cpp`, the original `disclaimer.md` and `about.nfo`. YuE2 model weights and the optional instrumental adapter are **CC BY-NC 4.0**; access to this installer does not grant different model rights. Upstream binary and dependency licenses remain applicable.
