import gc
import string
import tkinter as tk
import unittest

from src.downloader import FileTask
from src.gui import HFDownloaderGUI
from src.i18n import TRANSLATIONS, format_task_status, tr


def _extract_placeholders(template: str) -> set[str]:
    formatter = string.Formatter()
    return {field_name for _, field_name, _, _ in formatter.parse(template) if field_name is not None}


class TestI18n(unittest.TestCase):
    def test_zh_and_en_keys_and_placeholders_match(self):
        zh_keys = set(TRANSLATIONS["zh"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())
        self.assertEqual(zh_keys, en_keys)

        for key in zh_keys:
            self.assertEqual(
                _extract_placeholders(TRANSLATIONS["zh"][key]),
                _extract_placeholders(TRANSLATIONS["en"][key]),
                msg=f"Placeholder mismatch for key: {key}",
            )

    def test_format_task_status_both_languages(self):
        self.assertEqual(format_task_status("completed", "passed", "", "zh"), "校验通过 ✔")
        self.assertEqual(format_task_status("completed", "passed", "", "en"), "Verified ✔")
        self.assertEqual(format_task_status("failed", "mismatch", "", "en"), "SHA Mismatch ✘")
        self.assertIn("timeout", format_task_status("failed", "", "timeout", "en"))

    def test_gui_live_language_switch(self):
        root = tk.Tk()
        root.withdraw()
        try:
            gui = HFDownloaderGUI(root)
            # Default is Chinese
            self.assertEqual(gui.lang, "zh")
            self.assertEqual(gui.lang_var.get(), "中文")
            self.assertEqual(gui.start_btn.cget("text"), tr("zh", "start_btn"))

            # Add a sample task to test live row status translation
            gui.tasks = [FileTask("config.json", 128, downloaded=128, state="completed", verify_state="passed")]
            gui._populate_treeview()

            # Switch to English
            gui.set_language("en")
            self.assertEqual(gui.lang, "en")
            self.assertEqual(gui.lang_var.get(), "English")
            self.assertEqual(gui.start_btn.cget("text"), tr("en", "start_btn"))
            self.assertEqual(gui.verify_btn.cget("text"), tr("en", "verify_btn"))
            self.assertEqual(gui.tree.item("config.json", "values")[6], "Verified ✔")

            # Switch back to Chinese
            gui.set_language("zh")
            self.assertEqual(gui.start_btn.cget("text"), tr("zh", "start_btn"))
            self.assertEqual(gui.tree.item("config.json", "values")[6], "校验通过 ✔")
        finally:
            del gui
            gc.collect()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
