"""export testleri için ortak yardımcılar: fixture ev dizini, sahte repo kökü, yapılandırma."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib.exporter.config import LocalConfig

FIXTURE_HOME = Path(__file__).resolve().parent / "fixtures" / "export_home"

PAIRS = (
    ("/home/ada/vault", "{{VAULT_PATH}}"),
    ("/home/ada", "{{HOME}}"),
    ("Ada", "{{USER_NAME}}"),
    ("Turkish", "{{LANGUAGE}}"),
)

HARNESS = {
    "plugins": [{"id": "alpha@claude-plugins-official"}, {"id": "beta@beta-market"}],
    "marketplaces": [
        {"name": "claude-plugins-official", "repo": "anthropics/claude-plugins-official"},
        {"name": "beta-market", "repo": "someone/beta"},
    ],
    "ownSkills": [{"name": "demo"}],
    "export": {
        "settingsKeys": ["env", "model", "language"],
        "permissionKeys": ["permissions", "skipDangerousModePermissionPrompt"],
        "hookRules": [
            {"match": ".orca/agent-hooks", "action": "skip"},
            {"match": "-EncodedCommand", "action": "skip"},
            {"match": "ccstatusline", "action": "keep"},
            {"match": "proje-baslat/doktor_hook.py", "action": "keep"},
        ],
        "exclude": ["skills/*/cache/**", "skills/**/*.bak*"],
    },
}


def local_config(forbidden=("ada",), pairs=PAIRS):
    return LocalConfig(replace=tuple(pairs), forbidden=tuple(forbidden))


class ExportCase(unittest.TestCase):
    """Her test için geçici bir kaynak ev dizini (fixture kopyası) ve repo kökü açar."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="export-test-"))
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.home = self._tmp / "home"
        shutil.copytree(FIXTURE_HOME, self.home)
        self.root = self._tmp / "repo"
        self.root.mkdir()
        # Normal export ağaç taramasını da çalıştırır; ağaç için git deposu gerekir
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True, capture_output=True)
        self.write_harness(HARNESS)
        self.out = self._tmp / "payload"

    def write_harness(self, data):
        (self.root / "harness.json").write_text(json.dumps(data), encoding="utf-8")

    def write_local(self, forbidden=("ada",), pairs=PAIRS):
        path = self._tmp / "local.json"
        path.write_text(
            json.dumps({"replace": [list(p) for p in pairs], "forbidden": list(forbidden)}),
            encoding="utf-8",
        )
        return path

    def edit_settings(self, mutate):
        path = self.home / ".claude" / "settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(mutate(data)), encoding="utf-8")
