"""Small CI-only screenshot previews for review through the GitHub API.

Screenshots are from local emulator fixtures, never a user's device or credentials.
Full-resolution originals remain release assets. No app runtime dependency.
"""
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

for name in ('home', 'locations'):
    with Image.open(Path('android/release') / f'nyx-{name}.png') as image:
        image.thumbnail((320, 760))
        output = BytesIO()
        image.convert('RGB').save(output, 'WEBP', quality=65, method=6)
    encoded = base64.b64encode(output.getvalue()).decode()
    chunks = [encoded[i:i+3500] for i in range(0, len(encoded), 3500)]
    if len(chunks) > 5:
        raise ValueError('UI preview exceeds annotation budget')
    for index, chunk in enumerate(chunks):
        print(f'::notice title=Nyx UI {name} {index} of {len(chunks)}::{chunk}')
