import json
from pathlib import Path

import pytest

from core.config import load_config
from core.text_candidates import evaluate_candidate, strip_control_codes_for_analysis
from core.translator import GameTranslator, TranslationCancelled
from game_extractors import save_translated_file
from parsers import get_parser


class DummyTranslator:
    def __init__(self):
        self.calls = []

    def translate_with_retry(self, text):
        self.calls.append(text)
        return f"translated:{text}"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_config_is_loaded_and_patterns_are_validated(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
translation:
  engine: google
  source_lang: ja
  target_lang: zh-CN
  delay_between_requests: 0
  max_workers: 2
processing:
  skip_patterns: ['^[0-9]+$']
  preserve_patterns: ['\\\\{[^}]+\\\\}']
output:
  directory: translated
  backup: false
  log_file: ''
""",
        encoding="utf-8",
    )

    translator = GameTranslator(config=load_config(str(config_path)))

    assert translator.source_lang == "ja"
    assert translator.max_workers == 2
    assert translator.output_dir == "translated"
    assert translator._should_skip("123")


def test_config_loader_reads_adjacent_dotenv_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("translation: {}\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DEEPL_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)

    load_config(str(config_path))

    assert __import__("os").environ["DEEPL_API_KEY"] == "from-dotenv"


def test_backup_preserves_first_original_snapshot(tmp_path):
    source = tmp_path / "data.json"
    write_json(source, {"title": "original"})
    parser = get_parser(str(source))

    first_backup = Path(parser.create_backup())
    write_json(source, {"title": "changed"})
    second_backup = Path(parser.create_backup())

    assert first_backup.name == "data.backup.json"
    assert json.loads(first_backup.read_text(encoding="utf-8"))["title"] == "original"
    assert second_backup != first_backup
    assert json.loads(second_backup.read_text(encoding="utf-8"))["title"] == "changed"


def test_save_as_keeps_source_file_and_writes_separate_output(tmp_path):
    source = tmp_path / "data.json"
    target = tmp_path / "translated" / "data.json"
    write_json(source, {"title": "original"})

    backup = save_translated_file(source, {"title": "translated"}, target)

    assert json.loads(source.read_text(encoding="utf-8"))["title"] == "original"
    assert json.loads(backup.read_text(encoding="utf-8"))["title"] == "original"
    assert json.loads(target.read_text(encoding="utf-8"))["title"] == "translated"


def test_reuses_translation_for_duplicate_text_and_reconstructs_json(tmp_path):
    source = tmp_path / "data.json"
    target = tmp_path / "translated.json"
    write_json(source, {"title": "hello", "nested": ["hello"]})
    dummy = DummyTranslator()
    translator = GameTranslator(engine="google", backup=False, log_file="", delay=0, max_workers=1)
    translator.translator = dummy

    translator.translate_file(str(source), str(target))

    assert dummy.calls == ["hello"]
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "title": "translated:hello",
        "nested": ["translated:hello"],
    }


def test_cancel_never_writes_partial_output(tmp_path):
    source = tmp_path / "data.json"
    target = tmp_path / "translated.json"
    write_json(source, {"first": "one", "second": "two"})
    translator = GameTranslator(engine="google", backup=False, log_file="", delay=0, max_workers=1)
    translator.translator = DummyTranslator()
    translator.set_progress_callback(lambda current, total: False)

    with pytest.raises(TranslationCancelled):
        translator.translate_file(str(source), str(target))

    assert not target.exists()


def test_rpg_safe_json_mode_excludes_resource_names_and_script_parameters(tmp_path):
    source = tmp_path / "Map001.json"
    write_json(
        source,
        {
            "displayName": "Town",
            "faceName": "Actor1",
            "events": [{"name": "Guard", "pages": [{"list": [
                {"code": 401, "parameters": ["Welcome"]},
                {"code": 355, "parameters": ["$gameSwitches.setValue(1, true)"]},
                {"code": 102, "parameters": [["Yes", "No"]]},
            ]}]}],
        },
    )

    segments = get_parser(str(source), rpg_safe=True).parse()

    assert {segment.text for segment in segments} == {"Town", "Guard", "Welcome", "Yes", "No"}


def test_rpg_safe_profile_keeps_context_and_excludes_notes_and_audio_names(tmp_path):
    source = tmp_path / "System.json"
    write_json(
        source,
        {
            "gameTitle": "My Game",
            "note": "Plugin setting: do not translate",
            "titleBgm": {"name": "Theme01"},
            "sounds": [{"name": "Cursor1"}],
            "terms": {"basic": ["Level"]},
            "events": [{"list": [
                {"code": 401, "parameters": ["Hello"]},
                {"code": 102, "parameters": [["Yes", "No"]]},
            ]}],
        },
    )

    segments = get_parser(str(source), rpg_safe=True, rpg_command_codes=[401]).parse()
    by_text = {segment.text: segment for segment in segments}

    assert set(by_text) == {"My Game", "Level", "Hello"}
    assert "Show Text" in by_text["Hello"].context
    assert len(by_text["Hello"].metadata["source_hash"]) == 64


def test_rpg_safe_translation_writes_only_selected_player_text(tmp_path):
    source = tmp_path / "Map001.json"
    target = tmp_path / "Map001_translated.json"
    write_json(
        source,
        {
            "displayName": "Town",
            "events": [{"pages": [{"list": [
                {"code": 401, "parameters": ["Welcome"]},
                {"code": 355, "parameters": ["$gameVariables.setValue(1, 1)"]},
            ]}]}],
            "note": "<plugin:keep>",
        },
    )
    translator = GameTranslator(engine="google", backup=False, log_file="", delay=0, max_workers=1)
    translator.translator = DummyTranslator()

    translator.translate_file(
        str(source),
        str(target),
        rpg_safe=True,
        rpg_command_codes=[401],
        include_rpg_notes=False,
    )

    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["displayName"] == "translated:Town"
    assert result["events"][0]["pages"][0]["list"][0]["parameters"][0] == "translated:Welcome"
    assert result["events"][0]["pages"][0]["list"][1]["parameters"][0] == "$gameVariables.setValue(1, 1)"
    assert result["note"] == "<plugin:keep>"


def test_candidate_scoring_preserves_raw_control_codes_and_rejects_noise():
    raw = "\\C[4]\\N[1]获得了药草！\\C[0]"
    evaluation = evaluate_candidate(raw, source_type="event", field="message")

    assert evaluation.decision == "accept"
    assert evaluation.analysis_text == "获得了药草！"
    assert strip_control_codes_for_analysis("\\C[4]\\N[1]\\C[0]") == ""
    assert evaluate_candidate("img/system/Window.png", source_type="database").decision == "reject"
    assert evaluate_candidate("SceneManager", source_type="generic").decision == "reject"


def test_rpg_dialogue_blocks_merge_and_restore_line_structure(tmp_path):
    source = tmp_path / "Map001.json"
    write_json(
        source,
        {"events": [{"pages": [{"list": [
            {"code": 401, "indent": 0, "parameters": ["First line"]},
            {"code": 401, "indent": 0, "parameters": ["Second line"]},
            {"code": 102, "indent": 0, "parameters": [["Continue"]]},
        ]}]}]},
    )
    parser = get_parser(str(source), rpg_safe=True)
    segments = parser.parse()
    dialogue = next(segment for segment in segments if segment.metadata["type"] == "rpg_dialogue_block")

    assert dialogue.text == "First line\nSecond line"
    assert len(dialogue.metadata["locations"]) == 2
    dialogue.translated_text = "第一行\n第二行\n第三行"
    reconstructed = parser.reconstruct([dialogue])
    commands = reconstructed["events"][0]["pages"][0]["list"]

    assert [command["parameters"][0] for command in commands[:3]] == ["第一行", "第二行", "第三行"]
    assert commands[3]["code"] == 102
