import gc
import hashlib
import os
import tempfile
import tkinter as tk
import unittest

from src.downloader import DownloadEngine, FileTask, scan_local_files
from src.gui import CHECKED_MARK, UNCHECKED_MARK, HFDownloaderGUI
from src.hf_parser import RemoteFile
from src.quant_detector import detect_quantizations, extract_quant_tag
from src.verifier import VerifyEngine


class TestQuantDetector(unittest.TestCase):
    def test_extract_quant_tag_variants(self):
        self.assertEqual(extract_quant_tag("qwen2.5-0.5b-instruct-q4_k_m.gguf"), "Q4_K_M")
        self.assertEqual(extract_quant_tag("qwen2.5-0.5b-instruct-fp16.gguf"), "FP16")
        self.assertEqual(extract_quant_tag("GLM-5.3-UD-Q4_K_XL-00001-of-00012.gguf"), "UD-Q4_K_XL")
        self.assertEqual(extract_quant_tag("UD-IQ2_XXS"), "UD-IQ2_XXS")
        self.assertEqual(extract_quant_tag("BF16"), "BF16")
        self.assertIsNone(extract_quant_tag("README.md"))

    def test_subfolder_multi_quant_with_mmproj_and_helper_dir(self):
        files = [
            RemoteFile(".gitattributes", 100),
            RemoteFile("README.md", 500),
            RemoteFile("mmproj-BF16.gguf", 800_000_000),
            RemoteFile("Shard_Rewrite/rewrite.py", 2048),
            RemoteFile("UD-IQ2_M/model-00001-of-00002.gguf", 100_000_000),
            RemoteFile("UD-IQ2_M/model-00002-of-00002.gguf", 120_000_000),
            RemoteFile("UD-Q4_K_XL/model-00001-of-00002.gguf", 200_000_000),
            RemoteFile("UD-Q4_K_XL/model-00002-of-00002.gguf", 250_000_000),
            RemoteFile("BF16/model-00001-of-00001.gguf", 900_000_000),
        ]
        res = detect_quantizations(files)
        self.assertTrue(res.is_multi_quant)
        self.assertEqual([o.label for o in res.options], ["UD-IQ2_M", "UD-Q4_K_XL", "BF16"])
        self.assertEqual(res.options[0].file_count, 2)
        self.assertEqual(res.options[0].total_size, 220_000_000)
        self.assertEqual(res.common_files, [".gitattributes", "README.md"])
        self.assertEqual(res.mmproj_files, ["mmproj-BF16.gguf"])

    def test_flat_multi_quant_and_sharded_grouping(self):
        files = [
            RemoteFile("README.md", 1000),
            RemoteFile("qwen-q2_k.gguf", 400_000_000),
            RemoteFile("qwen-q4_k_m-00001-of-00002.gguf", 250_000_000),
            RemoteFile("qwen-q4_k_m-00002-of-00002.gguf", 260_000_000),
            RemoteFile("qwen-q8_0.gguf", 700_000_000),
            RemoteFile("qwen-fp16.gguf", 1_200_000_000),
        ]
        res = detect_quantizations(files)
        self.assertTrue(res.is_multi_quant)
        self.assertEqual([o.label for o in res.options], ["Q2_K", "Q4_K_M", "Q8_0", "FP16"])
        q4 = [o for o in res.options if o.label == "Q4_K_M"][0]
        self.assertEqual(q4.file_count, 2)
        self.assertEqual(q4.total_size, 510_000_000)

    def test_single_precision_repo_is_not_multi_quant(self):
        files = [
            RemoteFile("config.json", 1024),
            RemoteFile("model-00001-of-00002.safetensors", 5_000_000_000),
            RemoteFile("model-00002-of-00002.safetensors", 5_000_000_000),
        ]
        res = detect_quantizations(files)
        self.assertFalse(res.is_multi_quant)
        self.assertEqual(res.options, [])

    def test_verify_and_download_respect_selected_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_a = b"selected-file-content"
            sha_a = hashlib.sha256(data_a).hexdigest()
            with open(os.path.join(tmp, "selected.gguf"), "wb") as fh:
                fh.write(data_a)

            tasks = [
                FileTask("selected.gguf", len(data_a), expected_sha256=sha_a, selected=True),
                # Unselected missing file must be skipped by both DownloadEngine and VerifyEngine
                FileTask("unselected.gguf", 999999, expected_sha256="0" * 64, selected=False),
            ]
            # Verify only checks selected.gguf -> 1/1 passed, 0 missing
            summaries = []
            ver = VerifyEngine(log_fn=lambda _: None, on_done_fn=summaries.append)
            ver.start(tasks, tmp, workers=2)
            ver.wait(timeout=10)
            self.assertEqual(summaries[-1].total, 1)
            self.assertEqual(summaries[-1].passed, 1)
            self.assertEqual(summaries[-1].missing, 0)

            # DownloadEngine skips unselected task when selected is already completed
            tasks[0].state = "completed"
            tasks[0].downloaded = len(data_a)
            dl = DownloadEngine(log_fn=lambda _: None)
            queued = dl.start(tasks, "http://127.0.0.1:1", "o/r", "main", tmp, workers=1)
            self.assertEqual(queued, 0)

    def test_gui_quant_selection_and_manual_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = [
                RemoteFile("README.md", 100),
                RemoteFile("mmproj-F16.gguf", 500),
                RemoteFile("Q4_K_M/m.gguf", 1000),
                RemoteFile("Q8_0/m.gguf", 2000),
            ]
            root = tk.Tk()
            root.withdraw()
            try:
                gui = HFDownloaderGUI(root, initial_dir=tmp)
                gui.detection = detect_quantizations(files)
                gui.tasks = scan_local_files(files, tmp)
                gui._populate_treeview()
                gui._refresh_quant_combobox()

                # Select Q4_K_M (mmproj checked by default)
                gui.apply_quant_selection("dir:Q4_K_M")
                sel_names = {t.rfilename for t in gui.tasks if t.selected}
                self.assertEqual(sel_names, {"README.md", "mmproj-F16.gguf", "Q4_K_M/m.gguf"})
                self.assertEqual(gui.tree.item("Q4_K_M/m.gguf", "values")[0], CHECKED_MARK)
                self.assertEqual(gui.tree.item("Q8_0/m.gguf", "values")[0], UNCHECKED_MARK)

                # Uncheck mmproj
                gui.include_mmproj_var.set(False)
                gui._on_mmproj_toggle()
                sel_names2 = {t.rfilename for t in gui.tasks if t.selected}
                self.assertEqual(sel_names2, {"README.md", "Q4_K_M/m.gguf"})

                # Manual toggle on Q8_0 switches dropdown to custom
                gui._toggle_task_selection("Q8_0/m.gguf")
                self.assertEqual(gui.current_quant_key, "custom")
                self.assertEqual(gui.tree.item("Q8_0/m.gguf", "values")[0], CHECKED_MARK)
            finally:
                del gui
                gc.collect()
                root.destroy()


if __name__ == "__main__":
    unittest.main()
