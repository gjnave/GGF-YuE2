"""Get Going Fast Windows interface for audio.cpp's YuE2 GGUF runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import secrets
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from grizzlymax_asset import GRIZZLYMAX_IMAGE_DATA_URI


ROOT = Path(__file__).resolve().parent
GRIZZLYMAX_URL = "https://getgoingfast.pro/tools/grizzlymax/"
RUNTIME = ROOT / "runtime"
CLI = RUNTIME / "audiocpp_cli.exe"
HF = ROOT / ".venv-3.12" / "Scripts" / "hf.exe"
MODEL = ROOT / "models" / "YuE2-GGUF"
OUTPUTS = ROOT / "outputs"
ABC_EDITOR_ROOT = OUTPUTS / "abc-editor"
LAST_PROMPT = Path(os.environ.get("LOCALAPPDATA") or ROOT) / "GetGoingFast" / "YuE2-GGUF" / "last-prompt.json"
SESSION_SEED = secrets.randbelow(2_147_483_647) + 1
MANIFEST = json.loads((ROOT / "model_manifest.json").read_text(encoding="utf-8"))
LORA_MANIFEST = MANIFEST["instrumental_lora"]
LORA_DIR = MODEL / "loras"
LORA_FILE = LORA_MANIFEST["file"]
SIDECARS = (
    "sidecars/yue2-model-config.json",
    "sidecars/yue2-generation-config.json",
    "sidecars/yue2-qwen.tiktoken",
    "sidecars/yue2-vae-config.json",
)
VAE_FILE = "yue2-vae-f16.gguf"
QUANTS = {"q8": "yue2-3b-q8_0.gguf", "q4": "yue2-3b-q4_0.gguf"}
EXAMPLE_STYLE = "Ultra-cool late-’90s hip-hop soul with dusty boom-bap drums, deep upright bass, warm Rhodes chords, vinyl scratches, chopped horn samples, subtle gospel harmonies, and a confident female lead alternating between smooth melodic singing and sharp, intelligent rap. Smoky nightclub atmosphere, playful swagger, live-DJ energy, memorable call-and-response hook, polished modern low end while preserving an organic vintage groove."
EXAMPLE_LYRICS = """[INTRO - SPOKEN]

Everybody got a tutorial.

Everybody got a link.

Cool.

But does the damn thing run?

[HOOK - SUNG]

Get going fast
Get going fast
Quit staring at the screen
Put your hands on that

Get going fast
Get going fast
You can study all night
Or you can make that stack

Get going fast
Get going fast
Local on the box
Let the whole thing crack

Get going fast
Get going fast
If it breaks, we fix it
Then we run it right back

[VERSE - RAP]

New model dropped, everybody got opinions
Half ain’t installed it, still writing dissertations
Twenty tabs open, three guides contradicting
One says CUDA twelve, next one says you’re finished

Meanwhile I’m in the garage with the hood popped up
Console throwing red, but I don’t scare much
Read the line twice, find the part that got stuck
Patch it, launch it, now the whole thing wakes up

I don’t need the cloud telling me what I can run
Don’t need six subscriptions just to make something fun
Give me twenty-four gigs and a Saturday night
By Sunday morning, somebody better hold the mic

[HOOK - SUNG + RESPONSE]

Get going fast
(Go on, get it running)

Get going fast
(Stop talking, do something)

Get going fast
(Local on the machine)

Get going fast
(Now you know what I mean)

[BREAK - SPOKEN]

You don’t need to know everything.

You need the next step.

Then the next one.

That’s it.

[FINAL HOOK]

Get going fast
Get going fast
From the download
To the first clean pass

Get going fast
Get going fast
Build it on your own
Make the good stuff last

Get going fast
Get going fast
Whole crew in the garage
While the speakers slap

Get going fast
Get going fast
If it works?

Don’t touch that."""


def load_last_prompt() -> tuple[str, str]:
    if LAST_PROMPT.is_file():
        try:
            saved = json.loads(LAST_PROMPT.read_text(encoding="utf-8"))
            if isinstance(saved.get("style"), str) and isinstance(saved.get("lyrics"), str):
                return saved["style"], saved["lyrics"]
        except (OSError, ValueError, AttributeError):
            pass
    return EXAMPLE_STYLE, EXAMPLE_LYRICS


def save_last_prompt(style: str, lyrics: str) -> None:
    LAST_PROMPT.parent.mkdir(parents=True, exist_ok=True)
    LAST_PROMPT.write_text(json.dumps({"style": style, "lyrics": lyrics},
                                      ensure_ascii=False, indent=2), encoding="utf-8")


def validate_abc(text: str) -> str:
    """Check the minimal structure YuE2's generated and supplied scores need."""
    import gradio as gr

    score = text.lstrip("\ufeff")
    if not score.strip() or len(score.encode("utf-8")) > 2_000_000:
        raise gr.Error("Enter an ABC score under 2 MB.")
    if not re.search(r"(?m)^X:\s*\d+\s*$", score) or not re.search(r"(?m)^K:\s*\S", score):
        raise gr.Error("The score needs an X: tune number and a K: key header.")
    return score


def _score_path(path: str) -> Path:
    import gradio as gr

    if not path:
        raise gr.Error("Choose an ABC score first.")
    score_path = Path(path).resolve()
    if not score_path.is_file() or score_path.suffix.lower() != ".abc":
        raise gr.Error("Choose an existing .abc file.")
    if score_path.stat().st_size > 2_000_000:
        raise gr.Error("The ABC score must be under 2 MB.")
    return score_path


def _editor_path(path: str) -> Path:
    import gradio as gr

    score_path = _score_path(path)
    if not score_path.is_relative_to(OUTPUTS.resolve()):
        raise gr.Error("This score is outside the YuE2 output folder. Import it first.")
    return score_path


def _require_saved_before_open(text: str, baseline: str) -> None:
    import gradio as gr

    if text != baseline:
        raise gr.Error("You have unsaved ABC edits. Save or Save As before opening another score.")


def _open_score(path: str, current_text: str, baseline: str, imported: bool = False):
    import gradio as gr

    _require_saved_before_open(current_text, baseline)
    source = _score_path(path)
    score = validate_abc(source.read_text(encoding="utf-8-sig"))
    if imported:
        folder = ABC_EDITOR_ROOT / f"import-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        folder.mkdir(parents=True, exist_ok=False)
        source = folder / "score.abc"
        source.write_text(score, encoding="utf-8", newline="\n")
        note = "Imported into YuE2. Save updates this copy; download it to keep it on your PC."
    else:
        source = _editor_path(str(source))
        note = f"Opened {source}. Save updates this score."
    return score, str(source), score, note, gr.update(value=str(source), visible=True)


def open_uploaded_score(path: str, current_text: str, baseline: str):
    return _open_score(path, current_text, baseline, imported=True)


def open_generated_score(path: str, current_text: str, baseline: str):
    return _open_score(path, current_text, baseline)


def most_recent_score() -> str | None:
    scores = (path for path in OUTPUTS.glob("song-*/score.abc") if path.is_file())
    latest = max(scores, key=lambda path: path.parent.name, default=None)
    return str(latest) if latest else None


def open_recent_score(current_text: str, baseline: str):
    import gradio as gr

    latest = most_recent_score()
    if not latest:
        raise gr.Error("No generated score found. Generate a song with Save generated ABC score checked.")
    return open_generated_score(latest, current_text, baseline)


def auto_open_recent_score(path: str | None, current_text: str, baseline: str):
    import gradio as gr

    if path:
        return current_text, path, baseline, gr.update(), gr.update()
    latest = most_recent_score()
    if not latest:
        return current_text, path, baseline, "No generated score yet. Import an .abc file or generate one.", gr.update()
    return open_generated_score(latest, current_text, baseline)


def save_editor_score(text: str, path: str):
    import gradio as gr

    destination = _editor_path(path)
    score = validate_abc(text)
    destination.write_text(score, encoding="utf-8", newline="\n")
    return str(destination), score, f"Saved {destination}.", gr.update(value=str(destination), visible=True)


def save_editor_score_as(text: str, filename: str):
    import gradio as gr

    score = validate_abc(text)
    name = filename.strip()
    if not name or re.search(r'[\\/:*?"<>|]', name) or name.endswith((".", " ")):
        raise gr.Error("Enter a filename without path characters, such as my-song.abc.")
    if not name.lower().endswith(".abc"):
        name += ".abc"
    if len(name) > 100:
        raise gr.Error("Keep the filename under 100 characters.")
    folder = ABC_EDITOR_ROOT / f"edit-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / name
    destination.write_text(score, encoding="utf-8", newline="\n")
    return str(destination), score, f"Saved new score {destination}.", gr.update(value=str(destination), visible=True)


def use_editor_score(text: str, cot: str):
    import gradio as gr

    score = validate_abc(text)
    folder = ABC_EDITOR_ROOT / f"draft-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
    folder.mkdir(parents=True, exist_ok=False)
    draft = folder / "score.abc"
    draft.write_text(score, encoding="utf-8", newline="\n")
    return (gr.update(value=str(draft)), gr.update(selected="generate"),
            gr.update(value="full" if cot == "off" else cot), gr.update(value=False),
            gr.update(open=True),
            f"Edited score loaded for generation from {draft.name}. Click Generate song to render it.")


@lru_cache(maxsize=32)
def _sha256(path: str, size: int, modified_ns: int) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_file(name: str) -> bool:
    expected = MANIFEST["files"][name]
    path = MODEL / name
    if not path.is_file():
        return False
    stat = path.stat()
    if stat.st_size != expected["bytes"]:
        return False
    return _sha256(str(path), stat.st_size, stat.st_mtime_ns) == expected["sha256"]


def required_files(quant: str) -> tuple[str, ...]:
    if quant not in QUANTS:
        raise ValueError("Choose Q8 or Q4.")
    return (*SIDECARS, VAE_FILE, QUANTS[quant])


def model_ready(quant: str) -> bool:
    return all(valid_file(name) for name in required_files(quant))


def lora_ready() -> bool:
    path = LORA_DIR / LORA_FILE
    if not path.is_file():
        return False
    stat = path.stat()
    if stat.st_size != LORA_MANIFEST["bytes"]:
        return False
    return _sha256(str(path), stat.st_size, stat.st_mtime_ns) == LORA_MANIFEST["sha256"]


def download_model(quant: str) -> str:
    """Fetch only missing or invalid files; never re-download a verified quant."""
    if not HF.is_file():
        raise FileNotFoundError("The UV Python environment is missing. Run 1-INSTALL-YuE2-GGUF-GGF.bat.")
    needed = [name for name in required_files(quant) if not valid_file(name)]
    if not needed:
        return f"{quant.upper()} and the F16 audio decoder are verified. Download skipped."
    MODEL.mkdir(parents=True, exist_ok=True)
    command = [str(HF), "download", MANIFEST["repository"], *needed,
               "--revision", MANIFEST["revision"], "--local-dir", str(MODEL)]
    if any((MODEL / name).exists() for name in needed):
        command.append("--force-download")
    print(f"Downloading {quant.upper()}: {', '.join(needed)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    bad = [name for name in required_files(quant) if not valid_file(name)]
    if bad:
        raise RuntimeError(f"Model verification failed after download: {', '.join(bad)}")
    return f"{quant.upper()} and the F16 audio decoder downloaded and SHA-256 verified."


def download_lora() -> str:
    """Fetch the pinned BF16 instrumental adapter only when it is missing or invalid."""
    if not HF.is_file():
        raise FileNotFoundError("The UV Python environment is missing. Run 1-INSTALL-YuE2-GGUF-GGF.bat.")
    if lora_ready():
        return "Instrumental LoRA is verified. Download skipped."
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    command = [str(HF), "download", LORA_MANIFEST["repository"], LORA_FILE,
               "--revision", LORA_MANIFEST["revision"], "--local-dir", str(LORA_DIR)]
    if (LORA_DIR / LORA_FILE).exists():
        command.append("--force-download")
    print(f"Downloading instrumental LoRA: {LORA_FILE}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    if not lora_ready():
        raise RuntimeError("Instrumental LoRA verification failed after download.")
    return "Instrumental LoRA downloaded and SHA-256 verified."


def check_install() -> None:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Launch with the UV-managed Python 3.12 environment.")
    if not CLI.is_file() or not (RUNTIME / "ggml-cuda.dll").is_file():
        raise FileNotFoundError("The bundled audio.cpp CUDA runtime is incomplete.")
    version = subprocess.run([str(CLI), "--version"], cwd=ROOT, text=True,
                             capture_output=True, check=True)
    if "0.8.2" not in version.stdout:
        raise RuntimeError("YuE2 instrumental LoRA requires the bundled audio.cpp 0.8.2 runtime.")
    probe = subprocess.run([str(CLI), "--backend", "cuda", "--list-devices"],
                           cwd=ROOT, text=True, capture_output=True, check=True)
    if "CUDA:0" not in probe.stdout:
        raise RuntimeError("No NVIDIA CUDA device was found by audio.cpp.")
    installed = [quant.upper() for quant in QUANTS if model_ready(quant)]
    if not installed:
        raise FileNotFoundError("No verified GGUF quant is installed. Run the installer.")
    lora = "installed" if lora_ready() else "available from the GUI"
    print(f"YuE2 GGUF ready: Python 3.12, audio.cpp 0.8.2 CUDA, models: {', '.join(installed)}, instrumental LoRA: {lora}")


def quant_choices() -> list[tuple[str, str]]:
    return [
        (f"Q8 · higher fidelity ({'installed' if model_ready('q8') else 'download available'})", "q8"),
        (f"Q4 · lowest VRAM ({'installed' if model_ready('q4') else 'download available'})", "q4"),
    ]


def install_from_gui(quant: str):
    import gradio as gr

    try:
        note = download_model(quant)
        return gr.update(value=note, visible=True), gr.update(choices=quant_choices(), value=quant)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc


def install_lora_from_gui():
    import gradio as gr

    try:
        return gr.update(value=download_lora(), visible=True)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc


def instrumental_template():
    import gradio as gr

    return "[instrumental]", gr.update(value="full"), gr.update(value=True)


def instrumental_lyrics(lyrics: str) -> str:
    """Validate the three caption layouts on which the AR adapter was trained."""
    text = lyrics.strip() or "[instrumental]"
    if text.lower() == "[instrumental]":
        return "[instrumental]"
    tag = re.compile(
        r"^\[(intro|verse|pre-chorus|chorus|bridge|outro)(?:\s+\d+:\d{2}-\d+:\d{2})?\]$",
        re.IGNORECASE,
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or any(not tag.fullmatch(line) for line in lines):
        raise ValueError(
            "Instrumental LoRA lyrics must be [instrumental], or one supported section tag per line: "
            "[intro], [verse], [pre-chorus], [chorus], [bridge], [outro]. Optional m:ss-m:ss times are allowed."
        )
    return "\n".join(lines)


def audio_extension(output_format: str) -> str:
    if output_format == "flac":
        return "flac"
    if output_format == "mp3":
        return "mp3"
    raise ValueError("Choose FLAC or MP3.")


def random_seed() -> int:
    return secrets.randbelow(2_147_483_647) + 1


def convert_audio(wav: Path, output_format: str) -> Path:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Audio conversion is not installed. Rerun 1-INSTALL-YuE2-GGUF-GGF.bat.") from exc
    final = wav.parent / f"ggf-yue2-{wav.parent.name}.{audio_extension(output_format)}"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, "-y", "-v", "error", "-i", str(wav)]
    if output_format == "flac":
        command.extend(["-c:a", "flac", "-compression_level", "8"])
    else:
        command.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
    command.append(str(final))
    subprocess.run(command, cwd=ROOT, check=True)
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg did not produce {final.name}.")
    return final


def convert_current_song(song_path: str | None, output_format: str):
    import gradio as gr

    if not song_path:
        raise gr.Error("Generate a song before converting it.")
    selected = Path(song_path)
    wav = selected.parent / "audio.wav"
    if not wav.is_file():
        raise gr.Error("The WAV master for this song was not found.")
    try:
        converted = convert_audio(wav, output_format)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    return str(converted), gr.update(
        value=f"{converted.name.upper()} is ready. Use the download icon in the player.", visible=True)


def generate(style: str, lyrics: str, cot: str, seed: int, abc_file: str | None,
             quant: str = "q8", output_format: str = "flac",
             save_generated_score: bool = False, use_instrumental_lora: bool = False,
             lora_scale: float = 1.0):
    import gradio as gr

    if not style.strip():
        raise gr.Error("Enter a style before generating.")
    if use_instrumental_lora:
        if cot != "full":
            raise gr.Error("Instrumental LoRA requires Full plan.")
        if not lora_ready():
            raise gr.Error("Instrumental LoRA is not installed. Click Download instrumental LoRA first.")
        if not 0.0 <= float(lora_scale) <= 1.5:
            raise gr.Error("Instrumental LoRA strength must be between 0 and 1.5.")
        try:
            lyrics = instrumental_lyrics(lyrics)
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc
    elif not lyrics.strip():
        raise gr.Error("Enter lyrics before generating.")
    if abc_file and cot == "off":
        raise gr.Error("A supplied score needs Full plan or Melody plan.")
    if save_generated_score and cot == "off":
        raise gr.Error("A generated score needs Full plan or Melody plan.")
    import lifecycle
    lifecycle.stage('Checking selected model…')
    if not model_ready(quant):
        raise gr.Error(f"{quant.upper()} is not fully installed. Click Download selected quant first.")
    save_last_prompt(style.strip(), lyrics.strip())
    folder = OUTPUTS / f"song-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
    folder.mkdir(parents=True, exist_ok=False)
    wav = folder / "audio.wav"
    score = folder / "score.abc"
    if abc_file:
        shutil.copy2(abc_file, score)
    (folder / "request.json").write_text(json.dumps({
        "style": style.strip(), "lyrics": lyrics.strip(), "cot": cot,
        "seed": int(seed), "quant": quant, "output_format": output_format,
        "model_revision": MANIFEST["revision"],
        "audio_cpp_build": "0.8.2", "nar_ode_steps": 32,
        "supplied_abc": bool(abc_file), "save_generated_score": bool(save_generated_score),
        "instrumental_lora": bool(use_instrumental_lora),
        "instrumental_lora_scale": float(lora_scale) if use_instrumental_lora else None,
        "instrumental_lora_revision": LORA_MANIFEST["revision"] if use_instrumental_lora else None,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    command = [str(CLI), "--task", "gen", "--family", "yue2",
               "--model", str(MODEL),
               "--backend", "cuda", "--threads", "8", "--lyrics", lyrics.strip(),
               "--request-option", f"style={style.strip()}",
               "--request-option", f"cot={cot}", "--seed", str(int(seed)),
               "--num-inference-steps", "32",
               "--session-option", f"yue2.model_gguf={QUANTS[quant]}",
               "--session-option", f"yue2.vae_gguf={VAE_FILE}",
               "--out", str(wav), "--metrics", "--log"]
    if use_instrumental_lora:
        command.extend(["--session-option", f"yue2.ar_lora=loras/{LORA_FILE}",
                        "--session-option", f"yue2.ar_lora_scale={float(lora_scale):g}"])
    if abc_file:
        command.extend(["--request-option", f"abc_file={score}"])
    elif save_generated_score:
        command.extend(["--out-dir", str(folder)])
    log = folder / "generate.log"
    try:
        if lifecycle.CANCEL.is_set():
            raise RuntimeError('Generation stopped before the engine started.')
        lifecycle.stage('Loading native CUDA engine…')
        with log.open("w", encoding="utf-8", errors="replace") as stream:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors="replace",
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            lifecycle.register(process)
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                stream.write(line)
                stream.flush()
                lifecycle.stage(line.strip())
            code = process.wait()
        if lifecycle.CANCEL.is_set():
            raise RuntimeError('Generation stopped. Previously saved songs are kept.')
        if code != 0:
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
            raise RuntimeError(f"audio.cpp exited with code {code}. See {log}\n{tail}")
        if not wav.is_file() or wav.stat().st_size < 44:
            raise RuntimeError(f"audio.cpp did not produce a valid WAV file. See {log}")
        if save_generated_score and not abc_file and (not score.is_file() or score.stat().st_size == 0):
            raise RuntimeError(f"audio.cpp did not export the generated ABC score. See {log}")
        lifecycle.stage('Saving audio…')
        output = convert_audio(wav, output_format)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    note = (f"Saved to {folder}\nDownload: {output.name.upper()} "
            f"({output_format.upper()}); WAV master retained\n"
            f"Model: YuE2 {quant.upper()} + F16 VAE")
    if use_instrumental_lora:
        note += f"\nInstrumental AR LoRA: BF16 at strength {float(lora_scale):g}"
    if cot != "off" and not abc_file and save_generated_score:
        note += "\nGenerated ABC score saved beside the song."
    return (str(output),
            gr.update(value=str(score) if score.is_file() else None, visible=score.is_file()),
            gr.update(value=note, visible=True),
            str(output), gr.update(value="", visible=False),
            gr.update(visible=score.is_file()), str(score) if score.is_file() else None)


def edit_generated_in_editor(path: str, current_text: str, baseline: str):
    import gradio as gr

    return (*open_generated_score(path, current_text, baseline), gr.update(selected="editor"))


def install_local_connection_reset_filter() -> None:
    """Silence only Windows' harmless local-browser disconnect traceback."""
    def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        error = context.get("exception")
        if isinstance(error, ConnectionResetError) and getattr(error, "winerror", None) == 10054:
            return
        loop.default_exception_handler(context)

    base_policy = type(asyncio.get_event_loop_policy())

    class LocalConnectionResetPolicy(base_policy):
        def new_event_loop(self):
            loop = super().new_event_loop()
            loop.set_exception_handler(handle_exception)
            return loop

    asyncio.set_event_loop_policy(LocalConnectionResetPolicy())


CSS = """
.gradio-container { max-width: 1200px !important; margin: auto !important;
    background: #f7efdf !important; color: #132a3a !important; }
#ggf-hero { margin: 18px 0 20px; padding: 26px 28px; border-radius: 12px;
    background: linear-gradient(120deg, #112d3d, #173d52); color: white;
    box-shadow: 0 8px 16px rgba(18,42,58,.20); }
#ggf-hero h1 { color: white; margin: 0 0 6px; font-size: 31px; }
#ggf-hero p { color: #d9edf5; margin: 0; }
#ggf-hero a { display: inline-block; margin: 16px 10px 0 0; padding: 7px 12px;
    color: white; border: 1px solid #ffffff88; border-radius: 7px;
    text-decoration: none; font-weight: 700; }
#ggf-hero a:hover { background: white; color: #173d52; }
#ggf-start, #ggf-input, #ggf-output { padding: 16px; border: 1px solid #e5dac8;
    border-radius: 9px; background: #fffdf8; box-shadow: 0 3px 9px #262a321a; }
#ggf-output { align-self: flex-start; height: auto !important; }
#ggf-right { align-self: flex-start; }
#ggf-promo { margin: 26px 0 8px; text-align: center; }
#ggf-promo h2 { margin: 0 0 14px; color: #132a3a; font-size: clamp(24px, 2.7vw, 34px);
    font-weight: 850; line-height: 1.1; }
#ggf-promo .ggf-promo-image { display: block; overflow: hidden; border-radius: 9px;
    box-shadow: 0 4px 12px #262a3229; }
#ggf-promo img { display: block; width: 100%; height: auto; }
#ggf-promo .ggf-promo-cta { display: inline-block; margin-top: 16px;
    padding: 10px 24px; border-radius: 8px; background: #684dca; color: #fff;
    font-size: 18px; font-weight: 750; text-decoration: none; }
#ggf-promo .ggf-promo-cta:hover { background: #523aa9; color: #fff; }
#ggf-convert-row { align-items: flex-end; }
#ggf-convert-row button { min-height: 40px; }
#ggf-convert-status { margin-top: -6px; }
#ggf-editor { padding: 18px; border: 1px solid #e5dac8; border-radius: 9px;
    background: #fffdf8; box-shadow: 0 3px 9px #262a321a; }
#ggf-editor textarea { font-family: Consolas, 'Courier New', monospace; font-size: 13px; }
.gradio-container button.primary { background: #684dca; border: 0; font-weight: 700; }
.gradio-container button.primary:hover { background: #523aa9; }
"""


def build_demo():
    import gradio as gr

    initial_style, initial_lyrics = load_last_prompt()
    with gr.Blocks(title="Get Going Fast | YuE2 GGUF Music Studio") as demo:
        gr.HTML("""<section id="ggf-hero">
          <h1>Get Going Fast — YuE2 GGUF Music Studio</h1>
          <p>Create full songs with vocals locally on your NVIDIA GPU, with a model size that fits your system.</p>
          <a href="https://getgoingfast.pro" target="_blank" rel="noopener noreferrer">GetGoingFast.pro</a>
          <a href="https://youtube.com/@theaihobbyguy" target="_blank" rel="noopener noreferrer">YouTube: The AI Hobby Guy</a>
        </section>""")
        gr.HTML("""<section id="ggf-start"><strong>Start here</strong><br>
          Describe the sound, enter lyrics, choose Q8 for higher fidelity or Q4 for lower VRAM, select FLAC or MP3, and click Generate.
          If a quant is missing, click Download selected quant. Full and Melody plan accept an existing ABC score.
          For instrumentals, enable the optional LoRA, use Full plan, and use [instrumental] or section tags instead of lyrics.
          Generation progress appears in the Command Prompt window.
        </section>""")
        with gr.Tabs(selected="generate") as tabs:
            with gr.Tab("Generate song", id="generate"):
                with gr.Row(equal_height=False):
                    with gr.Column(elem_id="ggf-input"):
                        style = gr.Textbox(label="Style and sound", value=initial_style, lines=3)
                        lyrics = gr.Textbox(label="Lyrics", value=initial_lyrics, lines=12)
                        with gr.Row():
                            cot = gr.Dropdown(label="Musical plan", choices=[("Full plan", "full"),
                                ("Melody plan", "melody"), ("Direct generation", "off")], value="full")
                            with gr.Column():
                                seed = gr.Number(label="Seed (randomized each app launch)", value=SESSION_SEED,
                                                 precision=0, minimum=0)
                                randomize_seed = gr.Button("Randomize seed", size="sm")
                        save_generated_score = gr.Checkbox(label="Save generated ABC score", value=False)
                        quant = gr.Dropdown(label="Model quant", choices=quant_choices(),
                                            value="q8" if model_ready("q8") else "q4" if model_ready("q4") else "q8")
                        output_format = gr.Dropdown(label="Download format", choices=[("FLAC · lossless", "flac"),
                                                    ("MP3 · 320 kbps", "mp3")], value="flac")
                        download = gr.Button("Download selected quant")
                        download_status = gr.Markdown(value="", visible=False)
                        with gr.Accordion("Instrumental LoRA (optional)", open=False):
                            use_instrumental_lora = gr.Checkbox(
                                label="Use instrumental AR LoRA", value=False)
                            lora_scale = gr.Slider(
                                label="Instrumental LoRA strength", minimum=0.0, maximum=1.5,
                                step=0.05, value=1.0)
                            gr.Markdown(
                                "Use **Full plan**. Put `[instrumental]` in Lyrics, or use one section tag per line. "
                                "The standard BF16 adapter is about 140 MB and works with Q8 or Q4.")
                            with gr.Row():
                                set_instrumental = gr.Button("Use instrumental template")
                                download_instrumental = gr.Button("Download instrumental LoRA")
                            lora_status = gr.Markdown(
                                value="Instrumental LoRA is installed." if lora_ready() else "",
                                visible=lora_ready())
                        with gr.Accordion("Existing ABC score (optional)", open=False) as abc_accordion:
                            abc = gr.File(label="ABC score", file_types=[".abc"], type="filepath")
                        start = gr.Button("Generate song", variant="primary")
                    with gr.Column(elem_id="ggf-right"):
                        with gr.Column(elem_id="ggf-output"):
                            audio = gr.Audio(label="Generated song", type="filepath")
                            current_song = gr.State(value=None)
                            with gr.Row(equal_height=False, variant="compact", elem_id="ggf-convert-row"):
                                convert_format = gr.Dropdown(label="Another download format",
                                                             choices=[("FLAC · lossless", "flac"),
                                                                      ("MP3 · 320 kbps", "mp3")],
                                                             value="mp3", scale=2, min_width=170)
                                convert_song = gr.Button("Convert", size="sm", scale=1, min_width=120)
                            convert_status = gr.Markdown(value="", visible=False, elem_id="ggf-convert-status")
                            score = gr.File(label="ABC score", visible=False)
                            latest_score = gr.State(value=None)
                            edit_abc = gr.Button("Edit ABC", visible=False)
                            location = gr.Textbox(label="Output folder", interactive=False, lines=3, visible=False)
                        gr.HTML(f'''<aside id="ggf-promo" aria-label="GrizzlyMax music video creator">
                          <h2>Put your music to video</h2>
                          <a class="ggf-promo-image" href="{GRIZZLYMAX_URL}" target="_blank" rel="noopener noreferrer"
                             aria-label="Open GrizzlyMax download page">
                            <img src="{GRIZZLYMAX_IMAGE_DATA_URI}" alt="GrizzlyMax music video creator"></a>
                          <a class="ggf-promo-cta" href="{GRIZZLYMAX_URL}" target="_blank" rel="noopener noreferrer">Download here</a>
                        </aside>''')
            with gr.Tab("ABC Editor", id="editor") as editor_tab:
                with gr.Column(elem_id="ggf-editor"):
                    gr.Markdown("Edit a generated score or import an `.abc` file. Save writes the score shown below; **Use This Score** sends even unsaved edits to Generate song.")
                    editor_path = gr.State(value=None)
                    editor_baseline = gr.State(value="")
                    with gr.Row():
                        uploaded = gr.File(label="Open an existing .abc file", file_types=[".abc"], type="filepath")
                        with gr.Column():
                            open_uploaded = gr.Button("Open uploaded score")
                            open_recent = gr.Button("Open most recent generated score")
                    editor_text = gr.Textbox(label="ABC score", lines=22, max_lines=34)
                    editor_status = gr.Markdown("Generate a song with ABC export, or import an .abc file.")
                    with gr.Row():
                        save_score = gr.Button("Save")
                        save_name = gr.Textbox(label="Save As filename", value="edited-score.abc", scale=2)
                        save_as = gr.Button("Save As")
                    editor_download = gr.File(label="Download ABC score", visible=False)
                    use_score = gr.Button("Use This Score", variant="primary")
        demo.load(load_last_prompt, outputs=[style, lyrics])
        download.click(install_from_gui, inputs=[quant], outputs=[download_status, quant], concurrency_limit=1)
        download_instrumental.click(install_lora_from_gui, outputs=[lora_status], concurrency_limit=1)
        set_instrumental.click(instrumental_template,
                               outputs=[lyrics, cot, save_generated_score])
        randomize_seed.click(random_seed, outputs=[seed])
        convert_song.click(convert_current_song, inputs=[current_song, convert_format],
                           outputs=[audio, convert_status], concurrency_limit=1)
        start.click(generate, inputs=[style, lyrics, cot, seed, abc, quant, output_format,
                                     save_generated_score, use_instrumental_lora, lora_scale],
                    outputs=[audio, score, location, current_song, convert_status, edit_abc, latest_score], concurrency_limit=1)
        editor_outputs = [editor_text, editor_path, editor_baseline, editor_status, editor_download]
        editor_tab.select(auto_open_recent_score, inputs=[editor_path, editor_text, editor_baseline],
                          outputs=editor_outputs)
        uploaded.upload(open_uploaded_score, inputs=[uploaded, editor_text, editor_baseline], outputs=editor_outputs)
        open_uploaded.click(open_uploaded_score, inputs=[uploaded, editor_text, editor_baseline], outputs=editor_outputs)
        open_recent.click(open_recent_score, inputs=[editor_text, editor_baseline], outputs=editor_outputs)
        edit_abc.click(edit_generated_in_editor, inputs=[latest_score, editor_text, editor_baseline],
                       outputs=[*editor_outputs, tabs])
        save_score.click(save_editor_score, inputs=[editor_text, editor_path],
                         outputs=[editor_path, editor_baseline, editor_status, editor_download])
        save_as.click(save_editor_score_as, inputs=[editor_text, save_name],
                      outputs=[editor_path, editor_baseline, editor_status, editor_download])
        use_score.click(use_editor_score, inputs=[editor_text, cot],
                        outputs=[abc, tabs, cot, save_generated_score, abc_accordion, editor_status])
    return demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-model", choices=tuple(QUANTS))
    parser.add_argument("--download", choices=tuple(QUANTS))
    parser.add_argument("--download-lora", action="store_true")
    args = parser.parse_args()
    if args.check_model:
        if not model_ready(args.check_model):
            raise SystemExit(f"{args.check_model.upper()} is missing or failed SHA-256 verification")
        print(f"{args.check_model.upper()} model verified. Download skipped.")
    elif args.download:
        print(download_model(args.download))
    elif args.download_lora:
        print(download_lora())
    elif args.check:
        check_install()
    else:
        import gradio as gr

        install_local_connection_reset_filter()
        build_demo().queue(default_concurrency_limit=1).launch(
            server_name="127.0.0.1", server_port=7861, share=False,
            inbrowser=True, show_error=True, css=CSS, theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
