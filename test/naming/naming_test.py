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
from half_orm.model_errors import NamingError
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
    assert "use '_reverse_fkey_owned'." in message


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
    ('@ho_name', None),
    ('see @ho_name x', None),
    ('@ho_named x', None),
    ('@ho_name x y', None),
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
