"""Offline-only reset. Run with AI service stopped to avoid a live index writer."""
import shutil

from .config import Settings


def main():
    settings = Settings()
    archive = (settings.data_dir / "archive").resolve()
    demo = (settings.mcp_demo_dir or settings.data_dir / "mcp_demo").resolve()
    if demo == archive or archive.is_relative_to(demo) or demo.is_relative_to(archive) or demo == demo.parent:
        raise SystemExit("Unsafe MCP_DEMO_DIR: overlaps archive or filesystem root")
    # Keep mounted directory itself; remove only known index storage entries within it.
    for name in ("metadata.sqlite3", "metadata.sqlite3-wal", "metadata.sqlite3-shm", "chroma"):
        target = demo / name
        if target.is_symlink() or not target.resolve().is_relative_to(demo):
            raise SystemExit("Unsafe symlink inside demo directory")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    print("Synthetic MCP index reset. Archive data unchanged.")


if __name__ == "__main__":
    main()

