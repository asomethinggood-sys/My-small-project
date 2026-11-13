"""Small non-user emulator screenshots for reviewing the managed mobile UI."""
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

for name in ('home', 'settings'):
    with Image.open(Path('android/release') / f'continuum-{name}.png') as image:
        image.thumbnail((360, 800))
        buffer = BytesIO()
        image.convert('RGB').save(buffer, 'WEBP', quality=70, method=6)
    text = base64.b64encode(buffer.getvalue()).decode()
    chunks = [text[i:i+3500] for i in range(0, len(text), 3500)]
    if len(chunks) > 8:raise ValueError('Preview budget exceeded')
    for index, chunk in enumerate(chunks):
        print(f'::notice title=Continuum UI {name} {index} of {len(chunks)}::{chunk}')
