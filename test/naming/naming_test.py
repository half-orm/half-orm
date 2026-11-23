#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""Names half_orm derives from the catalog must not collide silently: a
clash is an error when the Model is created, listing every problem, and is
settled by a declaration -- a comment in the database, or an argument of
Model."""

import os

import pytest

from half_orm import naming, relation_errors
from half_orm.fkey import FKey
from half_orm.field import Field
from half_orm.model import Model, CONF_DIR
from half_orm.model_errors import NamingError, NamingWarning
from half_orm.relation import Relation
from ..init import model

CONF = 'halftest_naming'
DB = 'halftest'

SETUP = '''
create schema honame;
create table honame.author (id int primary key);
-- post(author_id) and post_author(id): one reverse name for two foreign keys
create table honame.post (
    id int primary key,
    author_id int constraint post_author_fk references honame.author(id));
create table honame.post_author (
    pk int primary key,
    id int constraint post_author_id_fk references honame.author(id));
create table honame.attrs (
    id int primary key,
    "a b" int,          -- becomes column2 ...
    column2 int,        -- ... which exists
    fk_owner int,       -- the attribute of the constraint below
    owner_id int constraint owner references honame.author(id),
    ho_count int,       -- a method of Relation
    _ho_fields int      -- an attribute of Relation
);
-- spelled alike without quotes
create schema "honame.x";
create table "honame.x".c (id int primary key);
create table honame."x.c" (id int primary key);
insert into honame.author values (1), (2);
insert into honame.post values (10, 1), (11, 1), (12, 2);
insert into honame.post_author values (20, 2);
insert into honame.attrs values (1, 5, 6, 7, 1, 8, 9);
'''
TEARDOWN = 'drop schema if exists honame cascade; drop schema if exists "honame.x" cascade;'

REVERSE_LEGACY = f'_reverse_fkey_{DB}_honame_post_author_id'

EVERY_PROBLEM = {
    ('reverse_fkey', REVERSE_LEGACY, 'honame.author'),
    ('attribute', 'column2', 'honame.attrs'),
    ('attribute', 'fk_owner', 'honame.attrs'),
    ('reserved', 'ho_count', 'honame.attrs'),
    ('reserved', '_ho_fields', 'honame.attrs'),
    ('qualified_name', 'honame.x.c', None),
}

# What settles all of it without touching the database.
FIELD_NAMES = {'honame.attrs': {
    'a b': 'a_b', 'fk_owner': 'owner_ref', 'ho_count': 'how_many', '_ho_fields': 'hf'}}
REVERSE_NAMES = {('honame.post', 'post_author_fk'): 'posts'}
IGNORE = ['honame.x.c']

COMMENTS = [
    ('constraint post_author_fk on honame.post', 'The author.\n@ho_reverse_name posts'),
    ('column honame.attrs."a b"', '@ho_name a_b'),
    ('column honame.attrs.fk_owner', 'Free text first.\n  @ho_name owner_ref  \nAnd after.'),
    ('column honame.attrs.ho_count', '@ho_name how_many'),
    ('column honame.attrs._ho_fields', '@ho_name hf'),
]


def _comment(target, text):
    literal = 'NULL' if text is None else "'" + text.replace("'", "''") + "'"
    model.execute_query(f'comment on {target} is {literal}')


def _problems(exc):
    return {(p.kind, p.name, p.relation) for p in exc.value.problems}


@pytest.fixture(scope='module', autouse=True)
def schema():
    conf = os.path.join(CONF_DIR, CONF)
    model.execute_query(TEARDOWN)
    model.execute_query(SETUP)
    with open(conf, 'w', encoding='utf-8') as file_:
        file_.write(
            '[database]\nname = halftest\nuser = halftest\n'
            'password = halftest\nhost = 127.0.0.1\n')
    try:
        yield
    finally:
        os.remove(conf)
        model.execute_query(TEARDOWN)


@pytest.fixture
def comments():
    for target, text in COMMENTS:
        _comment(target, text)
    try:
        yield
    finally:
        for target, _ in COMMENTS:
            _comment(target, None)


def open_model(**declarations):
    """A Model whose catalog is read now. The description is cached per
    server, database and declarations, and another test may have filled it."""
    a_model = Model(CONF, **declarations)
    a_model.reconnect(reload=True)
    return a_model


# -- detection ---------------------------------------------------------------

def test_every_problem_is_reported_at_once():
    with pytest.raises(NamingError) as exc:
        open_model()
    assert _problems(exc) == EVERY_PROBLEM
    assert exc.value.dbname == DB
    message = str(exc.value)
    assert '6 naming problems' in message
    assert "honame.post(author_id), constraint 'post_author_fk'" in message
    assert "honame.post_author(id), constraint 'post_author_id_fk'" in message


def test_a_refused_database_stays_refused():
    "the description read before must not serve the next Model"
    with pytest.raises(NamingError):
        open_model()
    with pytest.raises(NamingError):
        Model(CONF)


def test_the_connection_is_not_left_open_on_refusal():
    def backends():
        return model.execute_query(
            "select count(*) from pg_stat_activity where datname = %s", (DB,)
        ).fetchone()['count']
    before = backends()
    with pytest.raises(NamingError):
        Model(CONF, ignore=['no_such_schema.*'])
    assert backends() == before


def test_ignore_settles_what_it_removes():
    a_model = open_model(ignore='honame.post_author, honame.attrs, honame.x.c')
    assert not a_model.has_relation('honame.attrs')
    assert not a_model.has_relation('honame.post_author')
    author = a_model.get_relation_class('honame.author')()
    assert list(author._ho_fkeys) == [REVERSE_LEGACY]
    assert author._ho_fkeys[REVERSE_LEGACY]()._qrn == '"honame"."post"'


def test_ignore_takes_a_pattern():
    # Matched against the name as it reads without quotes, so "honame.x".c
    # goes with the rest although its schema is not `honame`.
    a_model = open_model(ignore=['honame.*'])
    assert [key for _, key in a_model._relations() if key[1].startswith('honame')] == []
    assert a_model.has_relation('actor.person')


# -- settling it on the Model -------------------------------------------------

def _check_settled(a_model):
    author = a_model.get_relation_class('honame.author')(id=1)
    assert set(author._ho_fkeys) == {'_reverse_fkey_posts', REVERSE_LEGACY, '_reverse_fkey_halftest_honame_attrs_owner_id'}
    # both foreign keys are there, each leading where it should
    assert author.rfk_posts()._qrn == '"honame"."post"'
    assert author.rfk_posts().ho_count() == 2
    legacy = getattr(author, 'rfk_' + REVERSE_LEGACY[len('_reverse_fkey_'):])
    assert legacy()._qrn == '"honame"."post_author"'

    attrs = a_model.get_relation_class('honame.attrs')()
    assert list(attrs._ho_fields) == [
        'id', 'a_b', 'column2', 'owner_ref', 'owner_id', 'how_many', 'hf']
    assert isinstance(attrs.fk_owner, FKey)
    assert isinstance(attrs.owner_ref, Field) and attrs.owner_ref.name == 'fk_owner'
    assert callable(attrs.ho_count) and not isinstance(attrs.ho_count, Field)
    assert isinstance(attrs._ho_fields, dict)
    # the columns are read and constrained through their declared names
    row = a_model.get_relation_class('honame.attrs')(a_b=5, how_many=8, hf=9).ho_get(
        'a_b', 'column2', 'owner_ref')
    assert row == {'a_b': 5, 'column2': 6, 'owner_ref': 7}
    assert attrs.fk_owner().ho_count() == 1


def test_declarations_on_the_model_settle_everything():
    _check_settled(open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE))


def test_declarations_in_comments_settle_everything(comments):
    _check_settled(open_model(ignore=IGNORE))


def test_the_model_wins_over_the_comment(comments):
    a_model = open_model(
        ignore=IGNORE,
        field_names={'honame.attrs': {'a b': 'from_model'}},
        reverse_names={('honame.post', 'post_author_fk'): 'from_model'})
    assert 'from_model' in a_model.get_relation_class('honame.attrs')()._ho_fields
    assert 'a_b' not in a_model.get_relation_class('honame.attrs')()._ho_fields
    assert '_reverse_fkey_from_model' in a_model.get_relation_class('honame.author')()._ho_fkeys


def test_a_derived_name_replaced_by_a_declaration_says_so():
    derived = f'_reverse_fkey_{DB}_honame_attrs_owner_id'
    a_model = open_model(
        field_names=FIELD_NAMES, ignore=IGNORE,
        reverse_names={**REVERSE_NAMES, ('honame.attrs', 'owner'): 'owned'})

    class Author(a_model.get_relation_class('honame.author')):
        Fkeys = {'rfk_owned': derived}

    with pytest.raises(relation_errors.WrongFkeyError) as exc:
        Author()
    message = str(exc.value)
    assert message.startswith(f"Can't find '{derived}'!\n'{derived}' is the name")
    assert "reverse foreign key from honame.attrs(owner_id)" in message
    assert ("given a name of its own, declared by "
            "Model(reverse_names={('honame.attrs', 'owner'): 'owned'}), "
            "which replaces it: use '_reverse_fkey_owned'.") in message


def _template_lines(relation):
    "The lines of the printed Fkeys template."
    text = repr(relation)
    return text[text.index('Fkeys = {'):].splitlines()[1:-1]


def test_the_template_offers_the_declared_name():
    author = open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
        ignore=IGNORE).get_relation_class('honame.author')()
    lines = _template_lines(author)
    assert "    'posts': '_reverse_fkey_posts'," in lines
    # a derived name keeps its derived attribute
    assert f"    'rfk_{REVERSE_LEGACY[len('_reverse_fkey_'):]}': '{REVERSE_LEGACY}'," in lines
    assert not any('FIX ME' in line for line in lines)
    # the offered template works once pasted
    class Author(open_model(
            field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
            ignore=IGNORE).get_relation_class('honame.author')):
        Fkeys = {'posts': '_reverse_fkey_posts'}
    assert Author(id=1).posts().ho_count() == 2


MODEL_ORIGIN = "declared by Model(reverse_names={('honame.post', 'post_author_fk'): '%s'})"


@pytest.mark.parametrize('declared, reason', [
    ('id', "is the column 'id' of honame.author."),
    ('ho_posts', 'is a name half_orm reserves for itself.'),
    (REVERSE_LEGACY.replace('_reverse_fkey_', 'rfk_'),
     f"is the attribute of the foreign key '{REVERSE_LEGACY}' of honame.author."),
])
def test_the_template_says_when_the_declared_name_is_taken(declared, reason):
    author = open_model(
        field_names=FIELD_NAMES, ignore=IGNORE,
        reverse_names={('honame.post', 'post_author_fk'): declared}
    ).get_relation_class('honame.author')()
    line, = [line for line in _template_lines(author)
             if f"'_reverse_fkey_{declared}'" in line]
    assert line == (
        f"    'rfk_{declared}': '_reverse_fkey_{declared}',  # FIX ME! "
        f"'{declared}', {MODEL_ORIGIN % declared}, {reason} "
        "Choose another alias for this foreign key, or declare another name")


def _author_with_a_posts_method(a_model):
    class Author(a_model.get_relation_class('honame.author')):
        def posts(self):
            "A method the alias would shadow."
    return Author


def test_the_template_says_which_class_holds_the_name():
    Author = _author_with_a_posts_method(open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE))
    line, = [line for line in _template_lines(Author())
             if "'_reverse_fkey_posts'" in line]
    assert line.startswith("    'rfk_posts': '_reverse_fkey_posts',  # FIX ME! ")
    assert f"is an attribute of {__name__}.{Author.__qualname__}." in line


def test_the_template_says_the_name_comes_from_a_comment(comments):
    Author = _author_with_a_posts_method(open_model(ignore=IGNORE))
    line, = [line for line in _template_lines(Author())
             if "'_reverse_fkey_posts'" in line]
    assert ("'posts', declared by '@ho_reverse_name' in the comment of the "
            "constraint 'post_author_fk' on honame.post, is an attribute") in line


def test_the_template_points_at_duplicate_constraints(comments):
    model.execute_query(
        'alter table honame.post add constraint post_author_fk_bis '
        'foreign key (author_id) references honame.author(id)')
    try:
        Author = _author_with_a_posts_method(open_model(
            ignore=IGNORE,
            reverse_names={('honame.post_author', 'post_author_id_fk'): 'owners'}))
        line, = [line for line in _template_lines(Author())
                 if "'_reverse_fkey_posts'" in line]
    finally:
        model.execute_query(
            'alter table honame.post drop constraint post_author_fk_bis')
    assert ("declared by '@ho_reverse_name' in the comment of one of the "
            "constraints 'post_author_fk', 'post_author_fk_bis' on honame.post "
            "(duplicates, same columns and target: drop one rather than name "
            "it), is an attribute") in line


def test_an_alias_in_fkeys_is_kept_and_not_flagged():
    class Author(open_model(
            field_names=FIELD_NAMES, ignore=IGNORE,
            reverse_names={('honame.post', 'post_author_fk'): 'id'}
    ).get_relation_class('honame.author')):
        Fkeys = {'rfk_writings': '_reverse_fkey_id'}
    assert "    'rfk_writings': '_reverse_fkey_id'," in _template_lines(Author())


def test_an_unknown_fkey_name_is_not_explained():
    class Author(open_model(
            field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
            ignore=IGNORE).get_relation_class('honame.author')):
        Fkeys = {'nope': '_reverse_fkey_nope'}

    with pytest.raises(relation_errors.WrongFkeyError) as exc:
        Author()
    assert 'is the name half_orm derives' not in str(exc.value)


# -- declarations that cannot be used -----------------------------------------

@pytest.mark.parametrize('declarations, problem', [
    ({'field_names': {'honame.attrs': {'a b': 'not valid'}}},
     ('declaration', 'not valid', 'honame.attrs')),
    ({'field_names': {'honame.attrs': {'a b': 'class'}}},
     ('declaration', 'class', 'honame.attrs')),
    ({'field_names': {'honame.attrs': {'a b': 'ho_select'}}},
     ('reserved', 'ho_select', 'honame.attrs')),
    ({'field_names': {'honame.attrs': {'a b': 'id'}}},
     ('attribute', 'id', 'honame.attrs')),
    ({'field_names': {'honame.attrs': {'no_such_column': 'x'}}},
     ('declaration', 'x', 'honame.attrs')),
    ({'field_names': {'honame.nope': {'id': 'x'}}},
     ('declaration', 'x', 'honame.nope')),
    ({'reverse_names': {('honame.post', 'no_such_constraint'): 'x'}},
     ('declaration', 'x', 'honame.post')),
    ({'reverse_names': {('honame.post', 'post_author_fk'): 'not valid'}},
     ('declaration', 'not valid', 'honame.post')),
])
def test_unusable_declaration(declarations, problem):
    merged = {
        'field_names': {'honame.attrs': dict(FIELD_NAMES['honame.attrs'])},
        'reverse_names': dict(REVERSE_NAMES), 'ignore': IGNORE}
    for key, value in declarations.items():
        if key == 'field_names':
            for relation, columns in value.items():
                merged['field_names'].setdefault(relation, {}).update(columns)
        else:
            merged[key].update(value)
    with pytest.raises(NamingError) as exc:
        open_model(**merged)
    assert problem in _problems(exc)


def test_a_declared_reverse_name_can_collide_too():
    with pytest.raises(NamingError) as exc:
        open_model(field_names=FIELD_NAMES, ignore=IGNORE, reverse_names={
            ('honame.post', 'post_author_fk'): 'same',
            ('honame.post_author', 'post_author_id_fk'): 'same'})
    assert _problems(exc) == {('reverse_fkey', '_reverse_fkey_same', 'honame.author')}
    problem, = exc.value.problems
    # Both already have a name: telling to name one of them would not help.
    assert problem.hint.startswith('this name was declared: declare a different one')
    assert all(member.endswith('named by Model(reverse_names=...)')
               for member in problem.members)


def test_a_declared_reverse_name_says_where_it_was_declared(comments):
    _comment('constraint post_author_id_fk on honame.post_author', '@ho_reverse_name posts')
    try:
        with pytest.raises(NamingError) as exc:
            open_model(ignore=IGNORE)
    finally:
        _comment('constraint post_author_id_fk on honame.post_author', None)
    problem, = [p for p in exc.value.problems if p.kind == 'reverse_fkey']
    assert problem.name == '_reverse_fkey_posts'
    assert problem.hint.startswith('this name was declared')
    assert all(member.endswith("named by '@ho_reverse_name' in its comment")
               for member in problem.members)


def test_an_undeclared_collision_says_to_name_one():
    with pytest.raises(NamingError) as exc:
        open_model()
    problem, = [p for p in exc.value.problems if p.kind == 'reverse_fkey']
    assert problem.hint.startswith('name one of them: ')
    assert not any('named by' in member for member in problem.members)


@pytest.mark.parametrize('arguments', [
    {'field_names': ['honame.attrs']},
    {'field_names': {'honame.attrs': 'a_b'}},
    {'reverse_names': {'honame.post': 'x'}},
    {'reverse_names': {('honame.post',): 'x'}},
])
def test_malformed_arguments_are_refused_before_connecting(arguments):
    with pytest.raises(ValueError):
        Model(CONF, **arguments)


# -- aliases given after the catalog was read ----------------------------------

def test_fkeys_alias_over_a_column_is_refused():
    a_model = open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE)

    class Attrs(a_model.get_relation_class('honame.attrs')):
        Fkeys = {'owner_id': 'owner'}

    with pytest.raises(NamingError) as exc:
        Attrs()
    assert _problems(exc) == {('attribute', 'owner_id', 'honame.attrs')}


def test_fkeys_alias_with_a_reserved_name_is_refused():
    a_model = open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE)

    class Attrs(a_model.get_relation_class('honame.attrs')):
        Fkeys = {'ho_select': 'owner'}

    with pytest.raises(NamingError) as exc:
        Attrs()
    assert _problems(exc) == {('reserved', 'ho_select', 'honame.attrs')}


# -- what identifies a Model ---------------------------------------------------

def test_models_declaring_different_names_share_nothing():
    one = open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE)
    other = open_model(
        field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
        ignore=IGNORE + ['honame.post_author'])
    same = Model(
        CONF, field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES, ignore=IGNORE)
    author = 'honame.author'
    assert one.get_relation_class(author) is same.get_relation_class(author)
    assert one.get_relation_class(author) is not other.get_relation_class(author)
    assert one.has_relation('honame.post_author')
    assert not other.has_relation('honame.post_author')


# -- unit ----------------------------------------------------------------------

@pytest.mark.parametrize('comment, expected', [
    ('@ho_name x', 'x'),
    ('text\n@ho_name x\nmore', 'x'),
    ('  @ho_name   x  ', 'x'),
    # malformed: returned as it is, to be reported, not taken for nothing
    ('@ho_name', ''),
    ('@ho_name x y', 'x y'),
    ("@ho_name x');drop table t;--", "x');drop table t;--"),
    ('see @ho_name x', None),
    ('@ho_named x', None),
    ('', None),
    (None, None),
])
def test_annotation(comment, expected):
    assert naming.annotation(comment, 'ho_name') == expected


def test_every_attribute_of_relation_is_reserved():
    """A column named like something Relation uses replaces it on the
    instance. Adding an attribute to Relation outside the reserved names
    would reopen that without a test failing -- except this one."""
    uncovered = [name for name in dir(Relation) if not naming.is_reserved(name)]
    assert uncovered == []


def test_instance_attributes_of_relation_are_reserved():
    person = model.get_relation_class('actor.person')()
    own = set(person.__dict__) - set(person._ho_fields) - person._ho_fkeys_attr
    assert [name for name in own if not naming.is_reserved(name)] == []


@pytest.mark.parametrize('name, python_name, read_as_written', [
    ('id', True, True),
    ('\u00e9t\u00e9', True, True),                  # été: NFKC already
    ('a b', False, True),
    ('class', False, True),
    ('\uff49\uff44', True, False),
    ('\ufb01le', True, False),
])
def test_python_names(name, python_name, read_as_written):
    assert naming.is_python_name(name) is python_name
    assert naming.is_read_as_written(name) is read_as_written


def test_python_reads_a_name_in_nfkc_form():
    "The reason for the warning: setattr keeps the string, the source does not."
    class Bare:
        "An object to set attributes on."
    obj = Bare()
    setattr(obj, 'id', 1)
    setattr(obj, '\uff49\uff44', 2)
    assert obj.ｉｄ == 1 and getattr(obj, '\uff49\uff44') == 2


# -- accepted in 2.x, refused in 3.0: a NamingWarning ----------------------------

def _warned(record):
    return [str(warning.message) for warning in record
            if issubclass(warning.category, NamingWarning)]


@pytest.mark.parametrize('declarations, attribute, expected', [
    ({'reverse_names': REVERSE_NAMES,
      'field_names': {**FIELD_NAMES, 'honame.attrs': {
          **FIELD_NAMES['honame.attrs'], 'a b': '\uff41_b'}}},
     ('honame.attrs', '\uff41_b'),
     "The name declared for the column 'a b' of honame.attrs, '\uff41_b', is not "
     "in the form Python reads it in: written in a program, it is 'a_b', another "
     "attribute. half_orm 3.0 will refuse this database: no Model will open "
     "on it until this is fixed."),
    ({'field_names': FIELD_NAMES,
      'reverse_names': {('honame.post', 'post_author_fk'): '\ufb01le'}},
     ('honame.author', 'rfk_\ufb01le'),
     "The reverse name declared for the constraint 'post_author_fk' of honame.post, "
     "'\ufb01le', is not in the form Python reads it in"),
])
def test_a_declared_name_python_would_misread_is_warned_about(
        declarations, attribute, expected):
    with pytest.warns(NamingWarning) as record:
        a_model = open_model(ignore=IGNORE, **declarations)
    assert any(message.startswith(expected) for message in _warned(record))
    relation, name = attribute
    # accepted as in 2.0
    assert hasattr(a_model.get_relation_class(relation)(), name)


@pytest.mark.parametrize('annotation', ['@ho_name a b', '@ho_name'])
def test_a_malformed_annotation_is_ignored_with_a_warning(comments, annotation):
    _comment('column honame.attrs."a b"', annotation)
    with pytest.raises(NamingError) as exc, pytest.warns(NamingWarning) as record:
        open_model(ignore=IGNORE)
    assert (f"The line '{annotation}' in the comment of the column 'a b' of "
            "honame.attrs holds no name and is ignored. half_orm 3.0 will "
            "refuse this database: no Model will open on it until this is "
            "fixed.") in _warned(record)
    # ignored, as in 2.0: the column2 clash it was meant to settle remains,
    # and the error says why
    assert ('attribute', 'column2', 'honame.attrs') in _problems(exc)
    clash, = [p for p in exc.value.problems if p.name == 'column2']
    assert (f"column 'a b'; its comment's line '{annotation}' holds no name "
            "and was ignored") in clash.members


def test_a_malformed_reverse_annotation_is_ignored_with_a_warning(comments):
    _comment('constraint post_author_fk on honame.post', '@ho_reverse_name the posts')
    with pytest.raises(NamingError) as exc, pytest.warns(NamingWarning) as record:
        open_model(ignore=IGNORE)
    assert any("'@ho_reverse_name the posts'" in message for message in _warned(record))
    assert ('reverse_fkey', REVERSE_LEGACY, 'honame.author') in _problems(exc)
    clash, = [p for p in exc.value.problems if p.kind == 'reverse_fkey']
    assert ("honame.post(author_id), constraint 'post_author_fk'; its comment's "
            "line '@ho_reverse_name the posts' holds no name and was ignored"
            ) in clash.members


def test_an_annotation_that_is_not_an_identifier_is_still_refused(comments):
    _comment('column honame.attrs."a b"', "@ho_name x');drop")
    with pytest.raises(NamingError) as exc:
        open_model(ignore=IGNORE)
    assert ('declaration', "x');drop", 'honame.attrs') in _problems(exc)


def test_a_column_python_would_misread_is_warned_about():
    model.execute_query('create table honame.wide (id int primary key, "\uff4e" int)')
    try:
        with pytest.warns(NamingWarning) as record:
            wide = open_model(ignore=IGNORE, field_names=FIELD_NAMES,
                              reverse_names=REVERSE_NAMES
                              ).get_relation_class('honame.wide')()
    finally:
        model.execute_query('drop table honame.wide')
    assert list(wide._ho_fields) == ['id', '\uff4e']
    assert any(message.startswith(
        "The name of the column '\uff4e' of honame.wide, '\uff4e', is not in the form")
        for message in _warned(record))


def test_an_fkeys_alias_python_would_misread_is_warned_about():
    class Author(open_model(
            field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
            ignore=IGNORE).get_relation_class('honame.author')):
        Fkeys = {'\uff50osts': '_reverse_fkey_posts'}
    with pytest.warns(NamingWarning) as record:
        author = Author(id=1)
    assert getattr(author, '\uff50osts')().ho_count() == 2
    assert any(message.startswith(
        "The alias in Fkeys of Author for the foreign key '_reverse_fkey_posts' "
        "of honame.author, '\uff50osts', is not in the form Python reads it in: "
        "written in a program, it is 'posts', another attribute. half_orm 3.0 "
        "will refuse this alias with a NamingError.") for message in _warned(record))


def test_a_naming_warning_can_be_made_an_error():
    "What 3.0 will do, available now."
    import warnings
    class Author(open_model(
            field_names=FIELD_NAMES, reverse_names=REVERSE_NAMES,
            ignore=IGNORE).get_relation_class('honame.author')):
        Fkeys = {'\uff50osts': '_reverse_fkey_posts'}
    with warnings.catch_warnings():
        warnings.simplefilter('error', NamingWarning)
        with pytest.raises(NamingWarning):
            Author()
