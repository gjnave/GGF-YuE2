"""Real Q4 ABC editor and generation smoke checks; run from the app root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yue2_gguf_gui as app




def roundtrip(source: Path, mode: str, old: str, new: str, seed: int) -> None:
    original, opened_path, baseline, _, _ = app.open_generated_score(str(source), "", "")
    assert opened_path == str(source)
    assert old in original
    edited = original.replace(old, new, 1)
    try:
        app.open_recent_score(edited, baseline)
    except Exception as exc:
        assert "unsaved" in str(exc).lower()
    else:
        raise AssertionError("Unsaved edits were replaced")

    saved_path, saved_baseline, _, _ = app.save_editor_score_as(edited, f"{mode}-edited.abc")
    assert saved_baseline == edited
    assert Path(saved_path).read_text(encoding="utf-8") == edited
    updated = edited.replace("X:1", "X:2", 1)  # Save another edit in place.
    _, saved_baseline, _, _ = app.save_editor_score(updated, saved_path)
    assert Path(saved_path).read_text(encoding="utf-8") == saved_baseline

    score_update, tab_update, plan_update, export_update, accordion_update, _ = app.use_editor_score(updated, mode)
    assert tab_update["selected"] == "generate"
    assert plan_update["value"] == mode
    assert not export_update["value"]
    assert accordion_update["open"]
    draft = Path(score_update["value"])
    assert draft.read_text(encoding="utf-8") == updated
    assert draft != Path(saved_path)

    result = app.generate("Bright rock with drums and piano", "[Verse] Get going fast", mode,
                          seed, str(draft), "q4", "flac", False)
    song = Path(result[0])
    assert song.is_file() and song.stat().st_size > 100_000
    assert (song.parent / "score.abc").read_text(encoding="utf-8") == updated
    print(mode, "edited-score roundtrip:", song)


if __name__ == '__main__':
    # Explicit legacy developer smoke; never run GPU work during test discovery.
    if '--legacy-fixtures' not in sys.argv:
        raise SystemExit('Use test_release.py for portable checks. This legacy GPU smoke needs --legacy-fixtures and the original local song fixtures.')
    app.LAST_PROMPT = app.OUTPUTS / "abc-editor-test-profile" / "last-prompt.json"
    roundtrip(app.OUTPUTS / "song-20260914-171835-4f99d2" / "score.abc",
              "full", '"Eb"', '"F"', 314159)
    roundtrip(app.OUTPUTS / "song-20260914-172000-595a7d" / "score.abc",
              "melody", "d4d4", "e4d4", 271828)
