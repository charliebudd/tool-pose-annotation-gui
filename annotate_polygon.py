import os

os.environ.setdefault("KIVY_NO_ARGS", "1")

from src.polygon_annotator.cli import main


if __name__ == "__main__":
    main()
