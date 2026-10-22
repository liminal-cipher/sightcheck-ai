from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
target = root.parent / '시야체크_실행형_MVP.zip'
folders = ('dist', 'src', 'server', 'scripts', 'tests', 'screenshots', 'public', 'docs', 'LICENSES')
files = ('README.md', 'start.ps1', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'index.html', 'vite.config.js', 'vite.api.config.js', '.gitignore')
with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=8) as archive:
    for name in files:
        file = root / name
        if file.is_file():
            archive.write(file, Path(root.name) / file.relative_to(root))
    for folder in folders:
        for file in (root / folder).rglob('*'):
            if not file.is_file() or '__pycache__' in file.parts:
                continue
            # Generated OCR assets are already included in dist. Avoid duplicating them.
            if folder == 'public' and 'ocr' in file.relative_to(root).parts:
                continue
            archive.write(file, Path(root.name) / file.relative_to(root))
print(f'{target} ({target.stat().st_size / 1024 / 1024:.1f} MB)')
