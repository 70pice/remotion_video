"""Arrange rendered portrait frames for visual layout review; does not change them."""
import json
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
output = root / 'out/components'
is_slice = '--slice' in sys.argv
is_progress = '--progress' in sys.argv
if is_slice:
    portraits = json.loads((root / '.runtime/slice-review.json').read_text(encoding='utf-8'))
else:
    report_name = 'verification-progress.json' if is_progress else 'verification.json'
    report = json.loads((output / report_name).read_text(encoding='utf-8'))
    portraits = report['portraitResults']
    if not is_progress:
        assert len(portraits) == 152
font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 15)
columns, per_page = 4, 20
tile_w, tile_h = 240, 455
files = []
for start in range(0, len(portraits), per_page):
    group = portraits[start:start + per_page]
    sheet = Image.new('RGB', (columns * tile_w, math.ceil(len(group) / columns) * tile_h), '#dce3eb')
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(group):
        name = item['previewImage']
        image = Image.open(output / name).convert('RGB')
        assert image.size == (1080, 1920), (item['id'], image.size)
        image.thumbnail((216, 384), Image.Resampling.LANCZOS)
        x, y = (index % columns) * tile_w + 12, (index // columns) * tile_h + 10
        sheet.paste(image, (x, y))
        label = item['id'].removeprefix('Vertical-')
        draw.text((x, y + 390), label[:26], fill='#172033', font=font)
        draw.text((x, y + 410), label[26:52], fill='#172033', font=font)
    prefix = 'native-slice-review' if is_slice else 'native-progress-review' if is_progress else 'native-layout-review'
    name = f'{prefix}-{start // per_page + 1:02}.jpg'
    sheet.save(output / name, quality=95)
    files.append(name)
print(json.dumps({'pages': files, 'count': len(portraits)}))
