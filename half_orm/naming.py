"""Names half_orm derives from the catalog, and what happens when two of them
are the same.

A relation is reached through Python names: its columns are attributes, and
so are its foreign keys, direct (``fk_<constraint>``) and reverse
(``rfk_<...>``). PostgreSQL has one namespace per kind of object and accepts
anything in a name; Python has one namespace per object. So two things the
database tells apart can end up answering to one name -- and one of them
used to disappear without a word.

half_orm no longer picks a winner. Every such name is checked when the
catalog is read, and a clash raises
:class:`~half_orm.model_errors.NamingError`, listing all of them. A clash is
settled by giving one of the two a name of its own:

* in the database, where every client will read it::

      COMMENT ON COLUMN public.orders.fk_owner IS '@ho_name owner_ref';
      COMMENT ON CONSTRAINT post_author_id_fkey ON public.post
          IS '@ho_reverse_name posts';

* or, for a database one cannot write to, on the Model::

      Model('legacy',
            field_names={'public.orders': {'fk_owner': 'owner_ref'}},
            reverse_names={('public.post', 'post_author_id_fkey'): 'posts'},
            ignore=['old.*'])

The rest of an annotated comment is free text; only the ``@ho_...`` line is
read. A declaration on the Model wins over one in the database.
"""

import re
from fnmatch import fnmatchcase
from keyword import iskeyword
from typing import NamedTuple

FIELD_ANNOTATION = 'ho_name'
REVERSE_ANNOTATION = 'ho_reverse_name'

REVERSE_PREFIX = '_reverse_fkey_'

# What a column may not be called in Python, because Relation is already
# using it. The prefixes are the library's own namespace -- the last one is
# how Python spells Relation's private methods -- and the names are the
# attributes that predate it. test/naming checks that every attribute of
# Relation is covered, so that adding one cannot silently reopen the clash.
RESERVED_PREFIXES = ('ho_', '_ho_', '_Relation__')
RESERVED_NAMES = frozenset({
    'Fkeys',
    '_qrn', '_fqrn', '_t_fqrn',
    '_dbname', '_schemaname', '_relationname',
    '_rels_ids', '_HO_WRITABLE_KINDS',
})


class Naming(NamedTuple):
    """The naming declarations made on a Model, in hashable form.

    Part of what identifies a Model: two Models that do not declare the same
    names do not see the same relations, and share neither their catalog
    description nor their relation classes.
    """
    fields: frozenset = frozenset()     # ((relation, column), python name)
    reverse: frozenset = frozenset()    # ((relation, constraint), name)
    ignore: frozenset = frozenset()     # 'schema.relation' patterns


NO_NAMING = Naming()


def is_reserved(name: str) -> bool:
    "Whether `name` is one Relation uses itself."
    return (name.startswith(RESERVED_PREFIXES)
            or name in RESERVED_NAMES
            or (name.startswith('__') and name.endswith('__')))


def is_python_name(name) -> bool:
    "Whether `name` can be written after a dot."
    return isinstance(name, str) and name.isidentifier() and not iskeyword(name)


def normalize(field_names=None, reverse_names=None, ignore=None) -> Naming:
    """Check the shape of the Model's naming arguments and freeze them.

    Raises:
        ValueError: if an argument does not have the documented shape. What
            the declarations *say* is checked later, against the catalog.
    """
    for argument, value in (('field_names', field_names),
                            ('reverse_names', reverse_names)):
        if value is not None and not isinstance(value, dict):
            raise ValueError(
                f"{argument} must be a dict, got {type(value).__name__}")
    fields = set()
    for relation, columns in (field_names or {}).items():
        if not isinstance(relation, str) or not isinstance(columns, dict):
            raise ValueError(
                "field_names must map 'schema.relation' to {column: python_name}, "
                f"got {relation!r}: {columns!r}")
        for column, name in columns.items():
            fields.add(((relation, column), name))

    reverse = set()
    for key, name in (reverse_names or {}).items():
        if (not isinstance(key, tuple) or len(key) != 2
                or not all(isinstance(part, str) for part in key)):
            raise ValueError(
                "reverse_names must map ('schema.relation', 'constraint') to a "
                f"name, got {key!r}")
        reverse.add((key, name))

    if ignore is None:
        patterns = ()
    elif isinstance(ignore, str):
        patterns = [pattern.strip() for pattern in ignore.split(',')]
    else:
        patterns = [str(pattern).strip() for pattern in ignore]
    return Naming(
        frozenset(fields), frozenset(reverse),
        frozenset(pattern for pattern in patterns if pattern))


def is_ignored(naming: Naming, schema: str, relation: str) -> bool:
    """Whether the relation matches one of the `ignore` patterns.

    A pattern is matched against ``schema.relation`` as it is written without
    quotes, shell style: ``old.*`` is every relation of the schema ``old``.
    """
    dotted = f'{schema}.{relation}'
    return any(fnmatchcase(dotted, pattern) for pattern in naming.ignore)


def annotation(comment, keyword):
    """Read ``@<keyword> <name>`` from a comment, or return None.

    The annotation is a line of its own; whatever else the comment says is
    the author's business.
    """
    if not comment:
        return None
    match = re.search(
        rf'^[ \t]*@{keyword}[ \t]+(\S+)[ \t]*$', comment, re.MULTILINE)
    return match.group(1) if match else None


def python_field_name(column: str, fieldnum: int, declared=None) -> str:
    """The attribute a column is reached through.

    Its declared name if it has one, its own if Python can write it, and
    ``column<N>`` otherwise -- ``a = 1`` is a legitimate column name.
    """
    if declared:
        return declared
    if is_python_name(column):
        return column
    return f'column{fieldnum}'


def reverse_fkey_name(table_key, fields, declared=None) -> str:
    """The key a reverse foreign key is filed under on the referenced relation.

    ``_reverse_fkey_<declared>`` when a name was declared for it. Otherwise
    the historical one, built from the database, schema, relation and column
    names joined by underscores -- which is what lets two different foreign
    keys spell the same: ``post(author_id)`` and ``post_author(id)``.
    """
    if declared:
        return f'{REVERSE_PREFIX}{declared}'
    name = f'{REVERSE_PREFIX}{"_".join(table_key)}.{".".join(fields)}'
    return name.replace('.', '_').replace(':', '_').replace('"', '')


def declared_reverse_name(fkey_name, table_key, fields):
    """The name declared for a reverse foreign key, or None.

    `table_key` and `fields` are the referencing relation and columns. A
    reverse key filed under another name than the derived one has been given
    a name of its own; that name is returned without the prefix.
    """
    if (fkey_name.startswith(REVERSE_PREFIX)
            and fkey_name != reverse_fkey_name(table_key, fields)):
        return fkey_name[len(REVERSE_PREFIX):]
    return None


def fkey_attribute(fkey_name: str) -> str:
    "The attribute a foreign key is exposed as when no alias is given."
    if fkey_name.startswith(REVERSE_PREFIX):
        return 'rfk_' + fkey_name[len(REVERSE_PREFIX):]
    return 'fk_' + fkey_name
