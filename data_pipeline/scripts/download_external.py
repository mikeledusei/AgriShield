"""Download original CC-BY research files, verifying publisher MD5 and never overwriting."""
from pathlib import Path
import hashlib
import urllib.request

OUT = Path(__file__).resolve().parents[1] / 'data' / 'external' / 'lam_odongo_2022'
FILES = {
    'Impacts_drought_indicators_WS.csv': ('https://data.4tu.nl/file/7dc5bc6c-7aab-46f5-9634-2aa56c96f18b/53bba5fe-e3ce-4804-8d8d-2afa2f13bf3f', 'dc918ff6db275e6229554edb3b12e566'),
    'README.txt': ('https://data.4tu.nl/file/7dc5bc6c-7aab-46f5-9634-2aa56c96f18b/07fa3304-088a-4ac0-a19d-dc756489662e', 'e8efe980e3ece5f5d146b587c4f177ee'),
}


def download():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in FILES.items():
        path = OUT / name
        if path.exists():
            if hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest() != expected:
                raise ValueError(f'{path} already exists but differs from the publisher hash; refusing to overwrite it.')
            print(f'Already verified: {path}')
            continue
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000 or hashlib.md5(raw, usedforsecurity=False).hexdigest() != expected:
            raise ValueError(f'{name} failed the publisher checksum or size check; nothing was saved.')
        with path.open('xb') as target:
            target.write(raw)
        print(f'Saved and verified: {path}')


if __name__ == '__main__':
    download()
