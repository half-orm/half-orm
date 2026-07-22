#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

from unittest import TestCase
from unittest.mock import patch
from datetime import date

from half_orm.field import Field
from half_orm.null import NULL, FieldDumper, NullDumper

from ..init import halftest, model

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.comment = halftest.comment_cls()
        self.today = halftest.today

    def tearDown(self):
        halftest.model.execute_query('alter table blog.post alter column content drop not null')
        halftest.model.reconnect(reload=True)

    def test_not_set_field(self):
        fields_set = {elt.is_set() for elt in self.pers._ho_fields.values()}
        self.assertTrue(fields_set, {False})

    def test_set_field(self):
        pers = self.pers(first_name='jojo')
        self.assertTrue(pers.first_name.is_set())

    def test_idem(self):
        pers = self.pers(first_name='jojo')
        self.assertIsInstance(pers.first_name, Field)

    def test_fields_names(self):
        field_names = set(self.pers._ho_fields.keys())
        self.assertEqual(
            field_names,
            {'id', 'first_name', 'last_name', 'birth_date', 'motto'})

    def test_relation_ref(self):
        first_name = self.pers.first_name
        self.assertEqual(id(first_name._relation), id(self.pers))

    def test_unset_field_with_none(self):
        pers = self.pers(first_name='jojo')
        pers.first_name.set(None)
        self.assertEqual(pers.ho_count(), self.pers.ho_count())
        self.assertFalse(pers.first_name.is_set())

    def test_is_not_null(self):
        post = halftest.post_cls()
        self.assertFalse(post.content.is_not_null())
        halftest.model.execute_query('alter table blog.post alter column content set not null')
        halftest.model.reconnect(reload=True)
        post = halftest.post_cls()
        self.assertTrue(post.content.is_not_null())
        halftest.model.execute_query('alter table blog.post alter column content drop not null')
        halftest.model.reconnect(reload=True)

    def test_relation(self):
        post = halftest.post_cls()
        self.assertEqual(post.content._relation, halftest.post_cls())

    def test_str_value(self):
        self.post.content = 10
        self.assertEqual(str(10), str(self.post.content))
        self.post.content = ('ilike', '%10%')
        self.assertEqual('%10%', str(self.post.content))
        self.post.content = date.today()
        self.assertEqual(str(date.today()), str(self.post.content))

    def test_wrong_value(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('=', 'b', 'c')
        self.assertEqual("Can't match ('=', 'b', 'c') with (comp, value)!", str(exc.exception))

    def test_null_value(self):
        self.post.content = NULL
        self.assertEqual(self.post.content._comp(), 'is')
        list(self.post)

    def test_comp_is_none_error(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('=', None)
        self.assertEqual("Can't have a None value with a comparator!", str(exc.exception))

    def test_comp_should_be_is_error(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('!=', NULL)
        self.assertEqual("comp should be 'is' or 'is not' with NULL value!", str(exc.exception))

    def test_comp_pct(self):
        self.post.content = ('%', 'what ever')
        self.assertEqual('%%', str(self.post.content._comp()))

    def test_unaccent(self):
        self.assertFalse(self.post.content.unaccent)
        # unaccent additionally requires the "unaccent" PostgreSQL extension
        # (see Field.unaccent's setter) — mocked here rather than depending
        # on whether the test database happens to have it installed.
        with patch.object(self.post.content._relation._ho_model, 'has_extension', return_value=True):
            self.post.content.unaccent = True
            self.assertTrue(self.post.content.unaccent)

        with self.assertRaises(RuntimeError) as exc:
            self.post.content.unaccent = 'true'
        self.assertEqual("unaccent value must be True or False!", str(exc.exception))

    def test_unaccent_ignored_when_extension_missing(self):
        with patch.object(self.post.content._relation._ho_model, 'has_extension', return_value=False):
            with self.assertWarns(UserWarning):
                self.post.content.unaccent = True
            self.assertFalse(self.post.content.unaccent)

    def test_name_property(self):
        self.assertEqual(self.post.content._name, self.post.content._Field__name)
        self.assertEqual(self.post.content._name, 'content')
        self.assertEqual(self.pers.last_name._name, 'last_name')

    def test_repr(self):
        self.assertEqual(repr(self.post.content), '(text)')
        self.assertEqual(repr(self.post.id), '(int4) NOT NULL')
        self.assertEqual(repr(self.pers.birth_date), '(date) NOT NULL')

        self.pers.birth_date = date.today()
        self.assertEqual(repr(self.pers.birth_date), f'(date) NOT NULL (birth_date = {date.today()})')

    def test_comps(self):
        self.post.content.set(['bonjour', 'au revoir'])
        self.assertIsInstance(self.post.content.value, tuple)
        self.post.content.set({'bonjour', 'au revoir'})
        self.assertIsInstance(self.post.content.value, tuple)
        self.assertEqual(self.post.content._where_repr('', id(self.post)), '"content" in %s')
        list(self.post)
        self.comment.tags.set('coucou')
        self.assertEqual(self.comment.tags._where_repr('', id(self.comment)), """%s = ANY("tags")""")
        list(self.comment)

    def test_py_type(self):
        self.assertEqual(str(self.comment.tags.py_type), 'typing.List[str]')

    def test_field_dumper_psycopg3_compat(self):
        """FieldDumper must not use self._tx (removed in psycopg 3.2+).

        Regression test: before the fix, FieldDumper.dump() and .upgrade()
        raised AttributeError: 'FieldDumper' object has no attribute '_tx'
        because psycopg 3.2 changed Dumper.__init__ to store self.connection
        instead of self._tx (a Transformer).
        """
        from psycopg.pq import Format

        conn = model._connection

        # --- dump() with a non-null Field value ---
        src = self.pers(**self.pers(last_name='aa').ho_get())
        field = src.last_name          # Field with value='aa'
        dumper = FieldDumper(type(field), conn)
        result = dumper.dump(field)    # raised AttributeError before fix
        self.assertIsNotNone(result)

        # --- upgrade() with a non-null Field must return self ---
        upgraded = dumper.upgrade(field, Format.TEXT)
        self.assertIs(upgraded, dumper)

        # --- dump() with a NULL Field value ---
        # Use a fresh relation instance: last_name is an attribute,
        # so src.last_name is the same object every time on the same instance.
        null_src = self.pers(**self.pers(last_name='ba').ho_get())
        null_field = null_src.last_name
        null_field.set(NULL)
        self.assertIsNone(dumper.dump(null_field))

        # --- upgrade() with a NULL Field must return a NullDumper ---
        upgraded = dumper.upgrade(null_field, Format.TEXT)
        self.assertIsInstance(upgraded, NullDumper)

        # --- dump() with a UUID Field value must produce valid UTF-8 text ---
        # Regression: PyFormat.AUTO caused psycopg to choose binary format for
        # UUIDs (16 raw bytes, not valid UTF-8), crashing PostgreSQL with
        # "invalid byte sequence for encoding UTF8".  PyFormat.TEXT is required.
        import uuid
        uuid_src = self.pers(**self.pers(last_name='aa').ho_get())
        uuid_field = uuid_src.birth_date   # date field — any non-string type works
        # Manually inject a UUID value to simulate the real-world case
        uuid_field._Field__value = uuid.UUID('35c418a5-2faa-4970-94e3-d0eedbc2542b')
        result = dumper.dump(uuid_field)
        self.assertIsInstance(result, (bytes, memoryview))
        # Must be valid UTF-8 (not raw binary bytes)
        bytes(result).decode('utf-8')

class TestJsonSchema(TestCase):
    """Field.json_schema — parsed @json block from column comment."""

    def setUp(self):
        self.post = halftest.post_cls()

    def test_json_schema_parsed_for_annotated_column(self):
        "blog.post.data has an @json comment — json_schema must return the parsed dict."
        schema = self.post.data.json_schema
        self.assertIsNotNone(schema)
        self.assertIsInstance(schema, dict)
        self.assertIn('lang', schema)
        self.assertEqual(schema['lang'], 'text')
        self.assertIn('views', schema)
        self.assertEqual(schema['views'], 'integer')
        self.assertIn('tags', schema)
        self.assertEqual(schema['tags'], ['text'])
        self.assertIn('items', schema)
        self.assertIsInstance(schema['items'], list)
        self.assertEqual(len(schema['items']), 1)
        self.assertEqual(schema['items'][0], {'id': 'uuid', 'name': 'text'})

    def test_json_schema_none_for_plain_column(self):
        "Columns without an @json comment must return None."
        self.assertIsNone(self.post.title.json_schema)
        self.assertIsNone(self.post.id.json_schema)


class TestHasDefaultValue(TestCase):
    """Field.has_default_value — default expression from pg_attrdef."""

    def setUp(self):
        self.pers = halftest.person_cls()

    def test_fields_with_default(self):
        "actor.person.id and motto have defaults — has_default_value must return the exact expression."
        self.assertEqual(self.pers.id.has_default_value, "nextval('actor.id_person'::regclass)")
        self.assertEqual(self.pers.motto.has_default_value, "''::text")

    def test_fields_without_default(self):
        "actor.person.first_name, last_name, birth_date have no default — has_default_value must be None."
        self.assertIsNone(self.pers.first_name.has_default_value)
        self.assertIsNone(self.pers.last_name.has_default_value)
        self.assertIsNone(self.pers.birth_date.has_default_value)
