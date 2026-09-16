"""Publish the BREAKING_CHANGES files that ship inside the package.

`half_orm/migrations/BREAKING_CHANGES-X.Y.Z.md` is what an upgrade tool reads
(see `half_orm.migrations.get_breaking_changes_dir`), so it is already the
authoritative text. Copying it into a documentation page would create a second
one, and the two would part company at the first correction.

So the page holds a marker and this hook fills it from those files, newest
version first. What the site shows is then what the installed package says, by
construction rather than by diligence.

A second marker puts a notice on the home page when the line being built is
one that introduced breaking changes. Each published version of this site is
its own build -- mike deploys /1.1/, /0.18/ and the rest separately -- so the
notice speaks about the release the reader is actually reading about, and says
nothing on a release that broke nothing.
"""

import logging
import re
from pathlib import Path

MARKER = '<!-- breaking-changes -->'
NOTICE_MARKER = '<!-- breaking-changes-notice -->'

_FILE_RE = re.compile(r'^BREAKING_CHANGES-(\d+)\.(\d+)\.(\d+)\.md$')

# '1.2-rc' and '1.2-dev' are builds of the 1.2 line. Kept in step with the twin
# in hooks/security_notice.py, which matches advisory pages the same way.
_LINE_RE = re.compile(r'^(\d+\.\d+)')

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


def _anchor(version):
    "The id given to a version's heading, and linked to from elsewhere."
    return 'breaking-' + '-'.join(str(n) for n in version)


def _sections(migrations_dir):
    "Every shipped file, newest version first."
    found = []
    for path in migrations_dir.iterdir():
        match = _FILE_RE.match(path.name)
        if match:
            found.append((tuple(int(g) for g in match.groups()), path))
    return sorted(found, reverse=True)


def on_page_markdown(markdown, page, config, files):
    if MARKER not in markdown and NOTICE_MARKER not in markdown:
        return markdown

    migrations = Path(config['docs_dir']).parent / 'half_orm' / 'migrations'
    if not migrations.is_dir():
        log.warning(
            "%s: no half_orm/migrations directory, so the breaking changes "
            "cannot be published from the package", page.file.src_path)
        return markdown.replace(MARKER, '').replace(NOTICE_MARKER, '')

    if NOTICE_MARKER in markdown:
        notice = _notice(migrations, config)
        markdown = markdown.replace(NOTICE_MARKER, notice or '')
        if MARKER not in markdown:
            return markdown

    paths = _sections(migrations)
    if not paths:
        return markdown.replace(
            MARKER, 'No breaking changes have been recorded yet.')

    blocks = []
    for version, path in paths:
        text = _demote_headings(path.read_text(encoding='utf-8').strip())
        # attr_list gives the heading a stable id, so the summary above can
        # link to it without this hook having to reproduce mkdocs' slugs.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('## '):
                lines[i] = f'{line} {{#{_anchor(version)}}}'
                break
        blocks.append('\n'.join(lines))

    summary = 'Releases that require changes to your code: ' + ', '.join(
        f'[{".".join(str(n) for n in version)}](#{_anchor(version)})'
        for version, _ in paths) + '.'

    return markdown.replace(MARKER, summary + '\n\n' + '\n\n'.join(blocks))


def _notice(migrations_dir, config):
    """The notice for the line being built, or None.

    Unlike the security notice, this one does not fall back to the most recent
    file when the version is `dev`: an advisory stays true whichever line you
    read it from, while "this release requires changes to your code" is a
    statement about one release, and dev is not it. A build with no version at
    all -- `mkdocs serve`, `make docs` -- still shows the newest, so the
    mechanism is visible while working on it.
    """
    paths = _sections(migrations_dir)
    if not paths:
        return None

    version = str(config['extra'].get('doc_version') or '')
    if not version:
        version, _ = paths[0]
    else:
        line = _LINE_RE.match(version)
        if not line:
            return None
        major, minor = (int(n) for n in line.group(1).split('.'))
        match = [v for v, _ in paths if v[:2] == (major, minor)]
        if not match:
            return None
        version = match[0]

    number = '.'.join(str(n) for n in version)
    return (
        '!!! warning "Breaking changes"\n\n'
        f'    **{number}** requires changes to your code. See\n'
        f'    [Breaking changes](breaking-changes.md#{_anchor(version)}) for\n'
        '    what changed and what to write instead.\n')
