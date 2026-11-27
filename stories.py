"""Write the text that the stories model learns from.

python stories.py    writes data/stories-train.txt and data/stories-valid.txt

The text is TinyStories, with every story ended by a blank line and a zero
byte. The zero tells a model where a story ends, and a chip that is given a
zero starts a new one.
"""
import hashlib
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / 'data'
URL = 'https://huggingface.co/datasets/roneneldan/TinyStories/resolve/main/'
SHA256 = {  # of the text written, so that everyone trains on the same bytes
    'train': '8ef7f507fa050b028e15dbc0d9bdf5922f89d59368a6419169d42669c0ecd85a',
    'valid': 'f82fdbcc962645c8866a2e49e07827574d15c529931da2b7c566caaa1a902c23',
}

DATA.mkdir(exist_ok=True)
for part, sha256 in SHA256.items():
    raw = DATA / f'TinyStoriesV2-GPT4-{part}.txt'
    if not raw.exists():
        urllib.request.urlretrieve(URL + raw.name, raw)
    stories = raw.read_bytes().split(b'<|endoftext|>')[1:-1]  # the first and last may be cut short
    text = b''.join(s.strip() + b'\n\n\0' for s in stories if s.strip())
    assert hashlib.sha256(text).hexdigest() == sha256, f'{part}: not the expected text'
    (DATA / f'stories-{part}.txt').write_bytes(text)
