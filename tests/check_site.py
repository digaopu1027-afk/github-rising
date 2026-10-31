"""Check generated local links and assets, including a GitHub Pages base path."""
from html.parser import HTMLParser
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for name in ('href', 'src'):
            if values.get(name):
                self.targets.append(values[name])


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist').resolve()
    base = (os.environ.get('BASE_PATH') or '/').rstrip('/')
    errors, count = [], 0
    files = list(root.rglob('*.html'))
    for page in files:
        parser = Links()
        parser.feed(page.read_text())
        for link in parser.targets:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            count += 1
            target = unquote(parsed.path)
            if target.startswith('/'):
                if base and target != base and not target.startswith(base + '/'):
                    errors.append('%s: link escapes base path: %s' % (page.relative_to(root), link))
                    continue
                destination = root / target[len(base):].lstrip('/')
            else:
                destination = page.parent / target
            if destination.is_dir():
                destination = destination / 'index.html'
            if not destination.exists():
                errors.append('%s: missing %s' % (page.relative_to(root), link))
    if not files:
        errors.append('No built HTML pages found')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print('Checked %d pages and %d local links/assets; no missing targets.' % (len(files), count))


if __name__ == '__main__':
    main()
