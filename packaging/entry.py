"""PyInstaller 用エントリースクリプト（Shiryō-Coder GUI を起動）。"""

import sys

from shiryo_coder.app import main

if __name__ == "__main__":
    sys.exit(main())
