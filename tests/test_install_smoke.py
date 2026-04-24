import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class InstallSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]

    def test_install_script_runs_with_mocked_curl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home_dir = root / "home"
            fake_bin = root / "fake-bin"
            home_dir.mkdir(parents=True, exist_ok=True)
            fake_bin.mkdir(parents=True, exist_ok=True)

            self._create_mock_curl(fake_bin / "curl")

            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["USERPROFILE"] = str(home_dir)
            env["DSVC_TEST_REPO_ROOT"] = str(self.repo_root)
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

            result = subprocess.run(
                ["bash", "scripts/install.sh"],
                cwd=self.repo_root,
                env=env,
                text=True,
                input="http://127.0.0.1:8080\ntest-user\n",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)
            self.assertIn("Installed dsvc to", result.stdout)

            install_line = next(
                (line for line in result.stdout.splitlines() if line.startswith("Installed dsvc to ")),
                "",
            )
            self.assertTrue(install_line, "Expected installer to print final install location.")
            launcher_path = install_line.removeprefix("Installed dsvc to ").strip()
            launcher = Path(launcher_path)
            config_file = home_dir / ".dsv_client" / "config.json"
            self.assertTrue(launcher.exists(), "Expected dsvc launcher symlink to exist.")
            self.assertTrue(config_file.exists(), "Expected config.json to be created.")

            with open(config_file, "r", encoding="utf-8") as fh:
                config = json.load(fh)
            self.assertEqual("http://127.0.0.1:8080", config.get("base_url"))
            self.assertEqual("test-user", config.get("username"))

    @staticmethod
    def _create_mock_curl(path: Path) -> None:
        script = """#!/usr/bin/env bash
set -euo pipefail

output=""
url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o)
      output="$2"
      shift 2
      ;;
    -*)
      shift
      ;;
    *)
      url="$1"
      shift
      ;;
  esac
done

if [[ -z "$output" || -z "$url" ]]; then
  echo "mock curl: missing output or url" >&2
  exit 1
fi

file_name="${url##*/}"
src="${DSVC_TEST_REPO_ROOT}/${file_name}"

if [[ ! -f "$src" ]]; then
  echo "mock curl: source file not found: $src" >&2
  exit 1
fi

cp "$src" "$output"
"""
        path.write_text(script, encoding="utf-8")
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
