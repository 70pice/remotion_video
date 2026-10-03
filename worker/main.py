import argparse
import signal
import threading
from pathlib import Path

from videoagents.default_config import RUNTIME_ROOT
from videoagents.storage import Repository
from worker.runner import Worker


def main():
    parser = argparse.ArgumentParser(description="VideoAgents 独立执行进程")
    parser.add_argument("--runtime-dir", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    worker = Worker(Repository(args.runtime_dir))
    if args.once:
        worker.once()
        return
    print("VideoAgents worker ready", flush=True)
    while not stop.is_set():
        if not worker.once():
            stop.wait(1)


if __name__ == "__main__":
    main()
