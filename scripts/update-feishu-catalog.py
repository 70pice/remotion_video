"""Compatibility entry for the bounded five-column workbook updater."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('update-component-path-sheet.py')), run_name='__main__')
