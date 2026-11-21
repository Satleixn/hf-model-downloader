import unittest

from src.hf_parser import ParsedRepo, parse_hf_input


class TestHFParser(unittest.TestCase):
    def test_standard_homepage_url(self):
        res = parse_hf_input("https://huggingface.co/MoonMath-ai/GLM-5.3-Uncensored-FP8")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "MoonMath-ai/GLM-5.3-Uncensored-FP8", "main"),
        )
        self.assertEqual(res.model_name, "GLM-5.3-Uncensored-FP8")

    def test_url_with_trailing_slash_and_query(self):
        res = parse_hf_input("https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/?tab=files#readme")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "deepseek-ai/DeepSeek-V4-Pro", "main"),
        )

    def test_url_with_tree_revision(self):
        res = parse_hf_input("https://huggingface.co/org/my-model/tree/fp8-branch")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "org/my-model", "fp8-branch"),
        )

    def test_url_with_blob_file(self):
        res = parse_hf_input("https://huggingface.co/org/my-model/blob/v2/config.json")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "org/my-model", "v2"),
        )

    def test_hf_mirror_url(self):
        res = parse_hf_input("https://hf-mirror.com/zai-org/GLM-5.3")
        self.assertEqual(
            res,
            ParsedRepo("https://hf-mirror.com", "zai-org/GLM-5.3", "main"),
        )

    def test_bare_host_without_scheme(self):
        res = parse_hf_input("huggingface.co/zai-org/GLM-5.3")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "zai-org/GLM-5.3", "main"),
        )

    def test_raw_repo_id(self):
        res = parse_hf_input("zai-org/GLM-5.3", default_endpoint="https://hf-mirror.com")
        self.assertEqual(
            res,
            ParsedRepo("https://hf-mirror.com", "zai-org/GLM-5.3", "main"),
        )

    def test_raw_repo_id_with_revision(self):
        res = parse_hf_input("zai-org/GLM-5.3@dev")
        self.assertEqual(
            res,
            ParsedRepo("https://huggingface.co", "zai-org/GLM-5.3", "dev"),
        )

    def test_reject_dataset_and_invalid_inputs(self):
        with self.assertRaises(ValueError):
            parse_hf_input("")
        with self.assertRaises(ValueError):
            parse_hf_input("https://huggingface.co/datasets/org/data")
        with self.assertRaises(ValueError):
            parse_hf_input("only-one-segment")


if __name__ == "__main__":
    unittest.main()
