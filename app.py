import argparse
import tkinter as tk

from src.gui import HFDownloaderGUI


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hugging Face Model Downloader GUI (Resumable + Retry Failed + Official SHA Verification)"
    )
    parser.add_argument("--url", default="", help="Hugging Face model homepage URL or owner/repo ID")
    parser.add_argument("--dir", default=None, help="Base local directory for saving downloaded models")
    parser.add_argument("--autostart", action="store_true", help="Automatically start downloading on launch")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Initial UI language (default: zh)")
    args = parser.parse_args()

    root = tk.Tk()
    HFDownloaderGUI(
        root,
        initial_url=args.url,
        initial_dir=args.dir,
        autostart=args.autostart,
        lang=args.lang,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
