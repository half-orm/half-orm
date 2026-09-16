"""Publish the BREAKING_CHANGES files that ship inside the package.

`half_orm/migrations/BREAKING_CHANGES-X.Y.Z.md` is what an upgrade tool reads
(see `half_orm.migrations.get_breaking_changes_dir`), so it is already the
authoritative text. Copying it into a documentation page would create a second
one, and the two would part company at the first correction.

So the page holds a marker and this hook fills it from those files, newest
version first. What the site shows is then what the installed package says, by
construction rather than by diligence.
"""

import logging
import re
from pathlib import Path

MARKER = '<!-- breaking-changes -->'

_FILE_RE = re.compile(r'^BREAKING_CHANGES-(\d+)\.(\d+)\.(\d+)\.md$')

log = logging.getLogger('mkdocs.hooks.breaking_changes')


def _demote_headings(text):
    """Add one level to every heading, leaving fenced code alone.

    The files are written as standalone documents, so each opens at `#`. Below
    the page's own title they have to start at `##`. A `#` inside a fence is a
    Python comment -- these files are full of them -- so fences are tracked
    rather than the lines merely tested for a leading hash.
    """
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
        elif not in_fence and line.startswith('#'):
            line = '#' + line
        out.append(line)
    return '\n'.join(out)


def _sections(migrations_dir):
    "Every shipped file, newest version first."
    found = []
    for path in migrations_dir.iterdir():
        match = _FILE_RE.match(path.name)
        if match:
            found.append((tuple(int(g) for g in match.groups()), path))
    return [path for _, path in sorted(found, reverse=True)]


def on_page_markdown(markdown, page, config, files):
    if MARKER not in markdown:
        return markdown

    migrations = Path(config['docs_dir']).parent / 'half_orm' / 'migrations'
    if not migrations.is_dir():
        log.warning(
            "%s: no half_orm/migrations directory, so the breaking changes "
            "cannot be published from the package", page.file.src_path)
        return markdown.replace(MARKER, '')

    paths = _sections(migrations)
    if not paths:
        return markdown.replace(
            MARKER, 'No breaking changes have been recorded yet.')

    rendered = '\n\n'.join(
        _demote_headings(path.read_text(encoding='utf-8').strip())
        for path in paths)
    return markdown.replace(MARKER, rendered)
