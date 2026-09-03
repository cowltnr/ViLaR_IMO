import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scripts/check_staged_credentials.sh"


class StagedCredentialScannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = TemporaryDirectory()
        self.repository = Path(self._temporary_directory.name) / "repository"
        self.repository.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Offline Test")
        self._git("config", "user.email", "offline-test@example.invalid")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            check=True,
            text=True,
            capture_output=True,
        )

    def _run_scanner(
        self, *, environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.assertTrue(SCANNER.is_file(), f"Missing scanner: {SCANNER}")
        return subprocess.run(
            [str(SCANNER)],
            cwd=self.repository,
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )

    def _stage_text(self, text: str) -> None:
        (self.repository / "config.txt").write_text(text, encoding="utf-8")
        self._git("add", "config.txt")

    def test_rejects_secret_added_to_staged_blob_without_echoing_value(self) -> None:
        sample_value = "ghp_" + "A" * 24
        self._stage_text(f"token={sample_value}\n")

        result = self._run_scanner()

        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Secret-pattern match found in staged content", output)
        self.assertNotIn(sample_value, output)

    def test_allows_staged_change_that_only_removes_secret(self) -> None:
        sample_value = "ghp_" + "B" * 24
        self._stage_text(f"token={sample_value}\n")
        self._git("commit", "-qm", "test fixture with historical secret")
        self._stage_text("setting=public\n")

        result = self._run_scanner()

        self.assertEqual(0, result.returncode, result.stderr)

    def test_rejects_scanner_error(self) -> None:
        self._stage_text("setting=public\n")
        fake_bin = Path(self._temporary_directory.name) / "fake-bin"
        fake_bin.mkdir()
        fake_rg = fake_bin / "rg"
        fake_rg.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
        fake_rg.chmod(0o755)
        environment = dict(os.environ)
        environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

        result = self._run_scanner(environment=environment)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Credential scanner failed", result.stderr)

    def test_rejects_staged_blob_producer_error(self) -> None:
        self._stage_text("setting=public\n")
        invalid_index = Path(self._temporary_directory.name) / "invalid-index"
        invalid_index.mkdir()
        environment = dict(os.environ)
        environment["GIT_INDEX_FILE"] = str(invalid_index)

        result = self._run_scanner(environment=environment)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Unable to enumerate staged content", result.stderr)


if __name__ == "__main__":
    unittest.main()
