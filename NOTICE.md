# Upstream components and model terms

This interface invokes the publisher-built native audio.cpp executable as a separate process. Runtime binaries and model weights are downloaded at installation time, not included in the customer ZIP or source repository.

- audio.cpp 0.8.2, source/build: https://github.com/0xShug0/audio.cpp/tree/v0.8.2 — Apache License 2.0; full text retained in LICENSE-audio.cpp and the downloaded runtime/LICENSE. Runtime dependencies carry their own bundled notices.
- YuE2 GGUF model and VAE: https://huggingface.co/audio-cpp/Yue2-3B-GGUF — revision and per-file hashes are in model_manifest.json. Model weights: CC BY-NC 4.0, https://creativecommons.org/licenses/by-nc/4.0/ . See the model card for full attribution and use restrictions.
- Optional instrumental adapter: https://huggingface.co/Mothersuperior/YuE2-instrumental-cot-full-loras — CC BY-NC 4.0. Pinned revision and file hash in model_manifest.json.
- YuE upstream: https://github.com/multimodal-art-projection/YuE . The original upstream source is not bundled by this installer.
- UV: https://github.com/astral-sh/uv — MIT/Apache-2.0. The pinned publisher-built UV executable provisions the app-owned Python runtime.
- Gradio: https://github.com/gradio-app/gradio — Apache-2.0. Other Python packages retain their respective distribution licenses.

Get Going Fast branding and original About/disclaimer are retained. No upstream model license is replaced by the installer or a membership purchase.
