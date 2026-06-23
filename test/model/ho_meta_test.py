#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from unittest import TestCase

from ..init import model


class TestHoMeta(TestCase):
    def setUp(self):
        self.meta = model.ho_meta()

    # -- structure globale --------------------------------------------------

    def test_returns_dict(self):
        "ho_meta() doit retourner un dict"
        self.assertIsInstance(self.meta, dict)

    def test_keys_are_schema_slash_table(self):
        "les clés doivent être de la forme '<schema>/<table>'"
        for key in self.meta:
            self.assertIn('/', key, msg=f"clé inattendue : {key!r}")

    def test_known_relations_present(self):
        "les relations principales de halftest doivent être présentes"
        for expected in ('actor/person', 'blog/post', 'blog/comment', 'blog/event'):
            self.assertIn(expected, self.meta, msg=f"{expected!r} absent de ho_meta()")

    # -- structure d'une entrée ---------------------------------------------

    def test_entry_top_level_keys(self):
        "chaque entrée doit contenir les clés attendues"
        required = {'schema', 'table', 'kind', 'pk_fields', 'fields', 'fk_deps', 'reverse_fks'}
        for key, entry in self.meta.items():
            self.assertEqual(required, set(entry.keys()), msg=f"clés incorrectes pour {key!r}")

    def test_schema_and_table_match_key(self):
        "schema/table de l'entrée doit correspondre à la clé"
        for key, entry in self.meta.items():
            schema, table = key.split('/', 1)
            self.assertEqual(entry['schema'], schema)
            self.assertEqual(entry['table'], table)

    def test_kind_is_valid(self):
        "kind doit être l'un des types PostgreSQL connus"
        valid_kinds = {'r', 'v', 'm', 'p', 'f'}
        for key, entry in self.meta.items():
            self.assertIn(entry['kind'], valid_kinds, msg=f"kind invalide pour {key!r}")

    def test_pk_fields_is_list(self):
        "pk_fields doit être une liste"
        for key, entry in self.meta.items():
            self.assertIsInstance(entry['pk_fields'], list, msg=f"{key!r}")

    # -- champs -------------------------------------------------------------

    def test_fields_is_list(self):
        "fields doit être une liste"
        for key, entry in self.meta.items():
            self.assertIsInstance(entry['fields'], list, msg=f"{key!r}")

    def test_field_keys(self):
        "chaque champ doit avoir les clés attendues"
        required = {'name', 'sql_type', 'json_type', 'is_pk', 'not_null', 'has_default'}
        for key, entry in self.meta.items():
            for field in entry['fields']:
                self.assertEqual(required, set(field.keys()),
                                 msg=f"clés de champ incorrectes dans {key!r}")

    def test_field_bool_flags(self):
        "is_pk, not_null, has_default doivent être des booléens"
        for key, entry in self.meta.items():
            for field in entry['fields']:
                for flag in ('is_pk', 'not_null', 'has_default'):
                    self.assertIsInstance(field[flag], bool,
                                         msg=f"{flag} non bool dans {key!r}/{field['name']}")

    def test_json_type_values(self):
        "json_type doit être l'une des valeurs JSON schema connues"
        valid = {'string', 'integer', 'number', 'boolean', 'date', 'datetime', 'json'}
        for key, entry in self.meta.items():
            for field in entry['fields']:
                self.assertIn(field['json_type'], valid,
                              msg=f"json_type inattendu '{field['json_type']}' dans {key!r}/{field['name']}")

    # -- actor/person : assertions concrètes --------------------------------

    def test_person_kind(self):
        "actor/person est une table (kind='r')"
        self.assertEqual(self.meta['actor/person']['kind'], 'r')

    def test_person_pk(self):
        "actor/person a (first_name, last_name, birth_date) comme clé primaire"
        pk = self.meta['actor/person']['pk_fields']
        self.assertEqual(sorted(pk), ['birth_date', 'first_name', 'last_name'])

    def test_person_fields_names(self):
        "actor/person doit avoir les colonnes attendues"
        names = {f['name'] for f in self.meta['actor/person']['fields']}
        for col in ('id', 'first_name', 'last_name', 'birth_date'):
            self.assertIn(col, names)

    def test_person_pk_fields_marked(self):
        "actor/person : first_name, last_name, birth_date doivent être is_pk=True"
        fields = {f['name']: f for f in self.meta['actor/person']['fields']}
        for col in ('first_name', 'last_name', 'birth_date'):
            self.assertTrue(fields[col]['is_pk'], msg=f"{col} devrait être is_pk")

    # -- clés étrangères ----------------------------------------------------

    def test_fk_deps_is_list(self):
        "fk_deps doit être une liste"
        for key, entry in self.meta.items():
            self.assertIsInstance(entry['fk_deps'], list, msg=f"{key!r}")

    def test_reverse_fks_is_list(self):
        "reverse_fks doit être une liste"
        for key, entry in self.meta.items():
            self.assertIsInstance(entry['reverse_fks'], list, msg=f"{key!r}")

    def test_fk_entry_keys(self):
        "chaque fk_dep doit avoir local_fields, remote_schema, remote_table, remote_fields"
        required = {'local_fields', 'remote_schema', 'remote_table', 'remote_fields'}
        for key, entry in self.meta.items():
            for fk in entry['fk_deps']:
                self.assertTrue(required.issubset(set(fk.keys())),
                                msg=f"clés fk_dep incomplètes dans {key!r}")

    def test_reverse_fk_entry_keys(self):
        "chaque reverse_fk doit avoir les clés fk + is_singleton"
        required = {'local_fields', 'remote_schema', 'remote_table', 'remote_fields', 'is_singleton'}
        for key, entry in self.meta.items():
            for rfk in entry['reverse_fks']:
                self.assertTrue(required.issubset(set(rfk.keys())),
                                msg=f"clés reverse_fk incomplètes dans {key!r}")

    def test_comment_has_fk_to_post(self):
        "blog/comment doit avoir une FK vers blog/post"
        fk_deps = self.meta['blog/comment']['fk_deps']
        targets = [(fk['remote_schema'], fk['remote_table']) for fk in fk_deps]
        self.assertIn(('blog', 'post'), targets)
