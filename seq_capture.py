"""Backward-compatible launcher and imports for sequence capture."""

from imgtrim_ui.region_selectors import LiveRegionSelector, RegionSelector
from imgtrim_ui.sequence_app import APP_DIR, INI_PATH, CaptureApp, main


if __name__ == "__main__":
    main()
