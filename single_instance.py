"""Run only one copy of the app, and hand file paths from a second launch to the first.

Why: with Explorer's right-click menu, selecting five images starts the app five times (once per file).
Instead of five windows, the later launches drop their paths into a small "inbox" folder and exit; the window
that is already open picks them up. No network or sockets are involved, only a lock file and a folder.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class SingleInstance:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.inbox = self.folder / "inbox"
        self._lock = None

    def acquire(self):
        """True if this process is now the one and only instance, False if another one is running."""
        self.inbox.mkdir(parents=True, exist_ok=True)
        handle = open(self.folder / "instance.lock", "a+b")  # noqa: SIM115 - kept open for the process lifetime
        try:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._lock = handle
        self._purge_old()
        return True

    def release(self):
        if self._lock is not None:
            try:
                if sys.platform == "win32":
                    self._lock.seek(0)
                    msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
                self._lock.close()
            except OSError:
                pass
            self._lock = None

    def send(self, paths):
        """Give paths (possibly none) to the running instance."""
        self.inbox.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex
        tmp = self.inbox / f"{name}.tmp"
        tmp.write_text(json.dumps([str(p) for p in paths], ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.inbox / f"{name}.msg")      # appears atomically, never half-written

    def collect(self):
        """Messages received since the last call: a list with one list of paths per second launch."""
        messages = []
        for f in sorted(self.inbox.glob("*.msg"), key=lambda p: p.stat().st_mtime):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                messages.append([str(x) for x in data] if isinstance(data, list) else [])
            except (OSError, ValueError):
                messages.append([])
            try:
                f.unlink()
            except OSError:
                pass
        return messages

    def _purge_old(self, seconds=60):
        """Messages left behind by an instance that died are not meant for a brand-new one."""
        limit = time.time() - seconds
        for f in self.inbox.glob("*"):
            try:
                if f.stat().st_mtime < limit:
                    f.unlink()
            except OSError:
                pass
