"""Compatibility wrapper for launching the application."""

from __future__ import annotations


def main():
    from app.main import main as run_application
    run_application()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--check-python-runtime":
        from app.python_runtime_check import check_runtime
        sys.exit(check_runtime(sys.argv[2], sys.argv[3]))
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from app.cli import main as cli_main
        sys.exit(cli_main(sys.argv[2:]))
    main()
