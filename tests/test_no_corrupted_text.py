import io
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CorruptedTextTests(unittest.TestCase):
    def test_no_question_mark_runs_in_strings_or_comments(self):
        """文字コード変換の事故で日本語が "??" に潰れた文言を検出する。"""
        problems = []
        for path in sorted(ROOT.rglob("*.py")):
            if any(part in {".git", "__pycache__", "tests"} for part in path.relative_to(ROOT).parts):
                continue
            source = path.read_text(encoding="utf-8")
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type in {tokenize.STRING, tokenize.COMMENT} and "??" in token.string:
                    problems.append(f"{path.name}:{token.start[0]}: {token.string.strip()[:40]}")
        self.assertEqual(problems, [])

    def test_no_replacement_characters(self):
        problems = [
            path.name
            for path in sorted(ROOT.rglob("*.py"))
            if not {".git", "__pycache__", "tests"} & set(path.relative_to(ROOT).parts)
            and chr(0xFFFD) in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
