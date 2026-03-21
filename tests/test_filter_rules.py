import tempfile
import unittest
from pathlib import Path

from game_extractors import is_irrelevant_text_file


class FilterRulesTest(unittest.TestCase):
    def test_skip_known_output_dirs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "output" / "data.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
            self.assertTrue(is_irrelevant_text_file(target, root))

    def test_skip_backup_and_log_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            backup_file = root / "Map001.backup_123.json"
            log_file = root / "translation_log.json"
            backup_file.write_text("{}", encoding="utf-8")
            log_file.write_text("{}", encoding="utf-8")

            self.assertTrue(is_irrelevant_text_file(backup_file, root))
            self.assertTrue(is_irrelevant_text_file(log_file, root))

    def test_skip_translated_suffix_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zh_file = root / "Map001_zh-cn.json"
            translated_file = root / "Items_translated.json"
            zh_file.write_text("{}", encoding="utf-8")
            translated_file.write_text("{}", encoding="utf-8")

            self.assertTrue(is_irrelevant_text_file(zh_file, root))
            self.assertTrue(is_irrelevant_text_file(translated_file, root))

    def test_keep_normal_game_data_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            normal_file = root / "data" / "Actors.json"
            normal_file.parent.mkdir(parents=True, exist_ok=True)
            normal_file.write_text("{}", encoding="utf-8")

            self.assertFalse(is_irrelevant_text_file(normal_file, root))


if __name__ == "__main__":
    unittest.main()
