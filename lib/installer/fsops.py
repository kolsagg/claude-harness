"""Yedekli, idempotent dosya yazıcı. dry_run'da hiçbir şey yazmaz, yalnız eylemleri kaydeder."""
import os
import shutil
from pathlib import Path


class Writer:
    def __init__(self, home, stamp, dry_run=False):
        self.home = Path(home)
        self.claude = self.home / ".claude"
        self.stamp = stamp
        self.dry_run = dry_run
        self.actions = []  # (eylem, home'a göre yol)

    def _rel(self, path):
        return Path(path).relative_to(self.home).as_posix()

    def _backup_dest(self, path):
        root = self.claude / "backups" / f"claude-harness-{self.stamp}"
        try:
            return root / Path(path).relative_to(self.claude)
        except ValueError:
            return root / Path(path).relative_to(self.home)

    def _backup(self, path):
        if self.dry_run:
            return
        dest = self._backup_dest(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

    def write(self, path, data, only_if_absent=False, mode_from=None):
        """created | updated | unchanged | kept döndürür."""
        path = Path(path)
        exists = path.is_file()
        if exists and only_if_absent:
            self.actions.append(("kept", self._rel(path)))
            return "kept"
        if exists and path.read_bytes() == data:
            self.actions.append(("unchanged", self._rel(path)))
            return "unchanged"
        if exists:
            self._backup(path)
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if mode_from is not None and os.name != "nt":
                shutil.copymode(mode_from, path)
        status = "updated" if exists else "created"
        self.actions.append((status, self._rel(path)))
        return status

    def remove(self, path, stop_at):
        """Yedekleyip siler; boş kalan üst klasörleri stop_at'a kadar temizler."""
        path = Path(path)
        self._backup(path)
        if not self.dry_run:
            path.unlink()
            parent = path.parent
            stop = Path(stop_at)
            while parent != stop and stop in parent.parents:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        self.actions.append(("removed", self._rel(path)))

    def count(self, action):
        return sum(1 for a, _ in self.actions if a == action)
