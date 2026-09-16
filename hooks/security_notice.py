"""Put the security notice on the home page, and only when there is one.

A notice about a specific release is true for a while and then is not, and the
one thing worse than no security notice is one that outlived its subject. So
the home page does not carry the text: it carries a marker, and this hook fills
it in from the advisory page for the line being built -- or removes it, when
that line has no advisory.

The condition is the existence of `docs/security-<line>.md`. Nothing else has
to be edited to raise or drop the notice: writing that file raises it, and a
line that never needed one never shows it.

`<line>` is the major.minor being published, which the documentation workflow
already computes (`DOC_VERSION`, `docs-impl.yml`) and passes through
`extra.doc_version`. A release candidate (`1.2-rc`) or a branch build
(`1.2-dev`) belongs to its own line and is reduced to it.

Two builds know no version: `mkdocs serve` run locally, and `main`, which
publishes as `dev`. Both fall back to the most recent advisory on file, so the
notice is visible while writing it, rather than only after a tag is pushed.
"""

import re
from pathlib import Path

MARKER = '<!-- security-notice -->'

# security-1.1.md, security-0.18.md -- the major.minor line it speaks for.
_ADVISORY_RE = re.compile(r'^security-(\d+)\.(\d+)\.md$')

# '1.2-rc' and '1.2-dev' are builds of the 1.2 line; '1.1' is itself.
_LINE_RE = re.compile(r'^(\d+\.\d+)')


def _advisories(docs_dir):
    "Map every advisory page on file to the (major, minor) line it covers."
    found = {}
    for path in Path(docs_dir).glob('security-*.md'):
        match = _ADVISORY_RE.match(path.name)
        if match:
            found[(int(match.group(1)), int(match.group(2)))] = path
    return found


def _notice_text(path):
    """The sentence to show, read from the advisory's `notice:` front matter.

    The wording of a security notice is editorial, so it lives in the page it
    points at rather than in this code. It is one line: front matter is read
    here by pattern, not by a YAML parser, so a folded block would arrive as
    `>-`. A page without a `notice:` still gets a notice -- a missing sentence
    must not be the reason nothing is displayed.
    """
    text = path.read_text(encoding='utf-8')
    match = re.search(r'^notice:\s*(.+?)\s*$', text, re.MULTILINE)
    if match:
        return match.group(1).strip('"\'')
    return 'This release line has a security advisory.'


def on_page_markdown(markdown, page, config, files):
    if MARKER not in markdown:
        return markdown

    advisories = _advisories(config['docs_dir'])
    version = str(config['extra'].get('doc_version') or '')
    line_match = _LINE_RE.match(version)

    if line_match:
        major, minor = line_match.group(1).split('.')
        target = advisories.get((int(major), int(minor)))
    elif advisories:
        # No version, or 'dev': speak for the most recent line on file.
        target = advisories[max(advisories)]
    else:
        target = None

    if target is None:
        return markdown.replace(MARKER, '')

    link = target.name[:-len('.md')]
    notice = (
        '!!! warning "Security advisory"\n\n'
        f'    {_notice_text(target)} See [Security]({link}.md) for what is\n'
        '    fixed, in which release, and what to do about it.\n'
    )
    return markdown.replace(MARKER, notice)
