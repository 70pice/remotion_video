"""Compatibility entry for complete component workbook readback."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('verify-component-path-sheet.py')), run_name='__main__')
