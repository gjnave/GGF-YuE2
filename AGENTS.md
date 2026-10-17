# GGF YuE2 handoff — read before changes

Canonical development app: D:\ggf-apps\yue2\GGF-YuE2. Outer customer scripts: D:\ggf-apps\yue2. Earlier D:\staging\yue2 is preserved, not the release source. Do not confuse this native GGUF build with the old D:\apps2review\yue2\YuE Torch fork.

Follow D:\apps2review\GGF-APP-BUILD-GUIDE.md and the family style guide in that root. Never delete files/folders without explicit user permission. Never send external messages without explicit permission.

Preserve native audio.cpp 0.8.2 / Windows x64 / CUDA 12.4 / UV-managed Python 3.12. There is no Torch or ComfyUI runtime here. Do not upgrade native versions, lower sampling quality or claim a speed gain without a real comparative generation. Model and LoRA revisions/hashes are pinned in model_manifest.json. Model weights are CC BY-NC 4.0.

app.py is the GGF UI. yue2_gguf_gui.py retains the validated native generation and ABC editor helpers. lifecycle.py owns the shared local/remote inference lock and only the app-owned child process. Native engine exits after each song. Both interfaces must share one lock; never kill unrelated GPU processes. Local access stays login-free; Settings controls a separate optional remote view. Blank password means login disabled. Preferred ports 7871/8871 with fallback. Browser workspace restoration uses ONE load handler; preserve uploads outside Gradio cache. Navy/gold palette, explicit light/dark and dropdown text colors, readable mobile controls.

Publish individual release-safe app files to BOTH https://codeberg.org/Cognibuild/GGF-YuE2 and https://github.com/gjnave/GGF-YuE2. Repository archives are host-generated from commits; never introduce a manually rebuilt source ZIP as an updater prerequisite. Drive Software/YuE2 is an independent code-only and installer backup. Exclude environments, native runtime binaries, models, generated songs, workspace tokens, credentials and private configuration from all source pushes.

Customer ZIP is an explicit allowlist of INSTALL.bat, RUN.bat, UPDATE.bat, README.md, original about.nfo, original disclaimer.md, LICENSE-audio.cpp and NOTICE.md only. Never package app source, models, runtime EXEs/DLLs, environments or outputs in it. Preserve the previous ZIP before replacement. Website production filename remains YuE2-GGUF-GetGoingFast-Windows-Instrumental-LoRA-with-Updater.zip in private/files/yue2/. Keep the route /tools/yue2/ and existing membership/price. Narrow website edits only; do not touch shared homepage layout/styles. Back up live files, compare drift, upload approved files and verify remote hashes and the member download.

The customer INSTALL.bat and UPDATE.bat live only beside the source checkout in the separate member package. Do not commit quick-install or updater BATs to this public repository. Keep numbered manual setup instructions in README.md; the source RUN.bat may remain.

Installer logic must be CMD BAT, never PowerShell. Source downloads Codeberg first then GitHub. UV is pinned and hash checked, and provisions Python without global Python. Update checks commit revisions, backs up source and preserves private assets. Any new required file belongs in release_sources.json and bootstrap validation.

See RELEASE-VERIFIED-20261015.md beside the outer scripts for actual publish/test status. Do not treat a planned mirror as verified.
