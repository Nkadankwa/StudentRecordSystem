"""Build a portable source archive without environments, databases or secrets."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('accounts', 'academics', 'config', 'management', 'student', 'templates', 'static', 'tests', 'tools', 'data')
FILES = ('manage.py', 'requirements.txt', 'README.md', 'DESIGN.md', '.gitignore', '.env.example', '.env.production.example')
DOCS = ('domain-model.md', 'deployment.md', 'operations.md', 'performance-results.json', 'handover.md', 'release-verification.md')


def package(destination):
    sources = [ROOT / name for name in FILES]
    sources += [ROOT / 'docs' / name for name in DOCS if (ROOT / 'docs' / name).is_file()]
    for folder in FOLDERS:
        sources += [file for file in (ROOT / folder).rglob('*') if file.is_file()
            and '__pycache__' not in file.parts and 'node_modules' not in file.parts
            and (file.suffix in {'.py', '.html', '.css', '.js', '.cjs', '.svg', '.sql', '.md', '.woff2'}
                 or file.name in {'LICENSE.txt', 'package.json', 'package-lock.json'})]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED) as archive:
        for file in sorted(sources):
            if not file.resolve().is_relative_to(ROOT):
                raise ValueError('Source symlinks outside the project cannot be packaged.')
            archive.write(file, Path('StudentRecordSystem') / file.relative_to(ROOT))
    return len(sources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='New .zip file; existing archives are never overwritten.')
    args = parser.parse_args()
    print(f'Packaged {package(args.destination)} source files. No private configuration or database included.')
