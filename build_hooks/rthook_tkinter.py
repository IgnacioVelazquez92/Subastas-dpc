import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    tcl_root = base_dir / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"

    if tcl_library.exists():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
    if tk_library.exists():
        os.environ["TK_LIBRARY"] = str(tk_library)
