from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import sys


class TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return any(getattr(stream, "isatty", lambda: False)() for stream in self.streams)

    @property
    def encoding(self):
        return getattr(self.streams[0], "encoding", None)

    def fileno(self):
        return self.streams[0].fileno()


def run_log_path(jobs_root, job_id, prefix="run"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}_{os.getpid()}.log"
    return Path(jobs_root) / str(job_id) / "logs" / filename


@contextmanager
def tee_to_log(log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", buffering=1) as log_file:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = TeeStream(original_stdout, log_file)
        sys.stderr = TeeStream(original_stderr, log_file)

        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
