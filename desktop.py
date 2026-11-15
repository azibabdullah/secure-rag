import multiprocessing
import os
import sys

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from src.utils.packaged_check import run
        raise SystemExit(run(sys.argv[2]))
    from src.gui.web_app import run_dashboard
    raise SystemExit(run_dashboard())
