import os
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from src.config import get_default_downloads_dir, load_saved_dir, save_selected_dir
from src.gui import HFDownloaderGUI


class TestConfigAndPathPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = os.path.join(self.tmpdir.name, "config.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_default_downloads_dir(self):
        default_dir = get_default_downloads_dir()
        self.assertTrue(default_dir.endswith("Downloads"))

    def test_save_and_load_dir_roundtrip(self):
        self.assertIsNone(load_saved_dir(self.cfg_path))
        target = os.path.join(self.tmpdir.name, "models")
        save_selected_dir(target, self.cfg_path)
        self.assertEqual(load_saved_dir(self.cfg_path), os.path.normpath(target))

    def test_gui_browse_saves_and_missing_dir_prompts(self):
        valid_dir = os.path.join(self.tmpdir.name, "valid_models")
        os.makedirs(valid_dir, exist_ok=True)
        missing_dir = os.path.join(self.tmpdir.name, "deleted_drive_models")

        # 1. No saved config -> defaults to Downloads
        root = tk.Tk()
        root.withdraw()
        try:
            gui = HFDownloaderGUI(root, config_path=self.cfg_path)
            self.assertEqual(gui.save_dir_var.get(), get_default_downloads_dir())

            # Browse selects valid_dir -> persisted to config.json
            with patch("src.gui.filedialog.askdirectory", return_value=valid_dir):
                gui._browse_dir()
            self.assertEqual(gui.save_dir_var.get(), os.path.normpath(valid_dir))
            self.assertEqual(load_saved_dir(self.cfg_path), os.path.normpath(valid_dir))
        finally:
            root.destroy()

        # 2. Saved path does not exist -> startup check warns and opens browse dialog
        save_selected_dir(missing_dir, self.cfg_path)
        root2 = tk.Tk()
        root2.withdraw()
        try:
            gui2 = HFDownloaderGUI(root2, config_path=self.cfg_path)
            self.assertEqual(gui2.save_dir_var.get(), os.path.normpath(missing_dir))
            with patch("src.gui.messagebox.showwarning") as mock_warn, patch(
                "src.gui.filedialog.askdirectory", return_value=valid_dir
            ):
                gui2._check_saved_dir_on_startup()
            mock_warn.assert_called_once()
            self.assertEqual(gui2.save_dir_var.get(), os.path.normpath(valid_dir))
            self.assertEqual(load_saved_dir(self.cfg_path), os.path.normpath(valid_dir))
        finally:
            root2.destroy()


if __name__ == "__main__":
    unittest.main()
