"""Recheck visible glyph bounds from packaged source JPGs; requires Pillow."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'references/pp-type-observations.json').read_text(encoding='utf-8'))
count = 0

def checked(relative, digest):
    path = (root / relative).resolve()
    assert path.is_relative_to(root), relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, relative
    return path

for case in data['cases']:
    path = checked(case['source_file'], case['source_sha256'])
    with Image.open(path) as original:
        assert list(original.size) == case['source_size_px']
        for item in case.get('measurements', []):
            x0, y0, x1, y1 = item['roi_xyxy_exclusive']
            assert 0 <= x0 < x1 <= original.width and 0 <= y0 < y1 <= original.height
            channels = original.crop((x0,y0,x1,y1)).convert('RGB').split()
            match = re.fullmatch(r'all RGB channels (<=|>=) (\d+)', item['pixel_rule'])
            assert match, item['pixel_rule']
            operator, threshold = match.group(1), int(match.group(2))
            merged = channels[0]
            for channel in channels[1:]:
                merged = (ImageChops.lighter if operator == '<=' else ImageChops.darker)(merged, channel)
            mask = merged.point([255 if (v <= threshold if operator == '<=' else v >= threshold) else 0 for v in range(256)])
            box = mask.getbbox()
            assert box is not None
            bx0, by0, bx1, by1 = box
            assert [bx0+x0, by0+y0, bx1+x0, by1+y0] == item['glyph_bbox_xyxy_exclusive'], item['key']
            assert by1-by0 == item['visible_glyph_height_px']
            assert bx1-bx0 == item['visible_glyph_width_px']
            for key in ['roi_file', 'mask_file']:
                checked(item[key], item[key+'_sha256'])
            with Image.open(root / item['mask_file']) as saved_mask:
                assert ImageChops.difference(mask, saved_mask.convert('L')).getbbox() is None
            count += 1
checked(data['measurement_method']['contact_sheet'], data['measurement_method']['contact_sheet_sha256'])
assert count == data['text_rois_count']
print(f'PASS: {count} visible-glyph regions reproduced; source images and evidence hashes verified.')
