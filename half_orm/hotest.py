# pylint: disable=protected-access

import unittest
from typing import List
from half_orm.relation import Relation

def _walk_attributes(obj, path: str):
    """Follow `path` as a dotted attribute path on `obj`.

    This was `eval(f"relation().{alias}")`, which let the string be any Python
    expression while every caller only ever named an attribute -- including
    the test files half-orm-dev generates, which reach the same object through
    `rel.__dict__[alias]`.
    """
    for name in path.split('.'):
        obj = getattr(obj, name)
    return obj


class HoTestCase(unittest.TestCase):
    def hotAssertIsPkey(self, relation: Relation, field_names: List[str]):
        "it shoud be the primary key"
        pkey = set(relation()._ho_pkey.keys())
        if set(field_names) != pkey:
            raise self.fail(f'PKey failure: {set(field_names)} != {pkey}')

    def hotAssertIsUnique(self, relation: Relation, fields_names: List[str]):
        "Checks if a list of fields is unique for the relation."
        if set(fields_names) == set(relation._ho_pkey.keys()):
            return # OK it's the primary key
        for field_name in fields_names:
            field = relation()._ho_fields[field_name]
            if not field._Field__metadata['uniq']:
                raise self.fail(f"'{fields_names}' is not unique.")

    def hotAssertIsNotNull(self, relation: Relation, field_name: str):
        if not relation()._ho_fields[field_name].is_not_null():
            raise self.fail(f"'{field_name}' is not 'not null'.")

    def hotAssertReferences(self, relation: Relation, fk_name: str, f_relation: Relation):
        referenced = relation()._ho_fkeys[fk_name]()
        if referenced._qrn != f_relation._qrn:
            raise self.fail(f"{relation.__class__.__name__}()._ho_fkeys['{fk_name}']() does not reference {f_relation.__name__}")

    def hotAssertAliasReferences(self, relation: Relation, alias: str, f_relation: Relation):
        """Check that `alias` on `relation` points at `f_relation`.

        `alias` names an attribute, or a dotted path of them.
        """
        referenced = _walk_attributes(relation(), alias)
        if referenced()._qrn != f_relation._qrn:
            raise self.fail(f"{relation.__class__.__name__}.{alias}() does not reference {f_relation.__name__}")

    def __check_update_action(self, relation: Relation, fk_name: str, update_type: str):
        return self.assertEqual(relation()._ho_fkeys[fk_name].confupdtype, update_type)

    def __check_delete_action(self, relation: Relation, fk_name: str, delete_type: str):
        return self.assertEqual(relation()._ho_fkeys[fk_name].confdeltype, delete_type)

    def hotAssertOnUpdateNoAction(self, relation: Relation, fk_name: str):
        return self.__check_update_action(relation, fk_name, 'a')

    def hotAssertOnUpdateRestict(self, relation: Relation, fk_name: str):
        return self.__check_update_action(relation, fk_name, 'r')

    def hotAssertOnUpdateCascade(self, relation: Relation, fk_name: str):
        return self.__check_update_action(relation, fk_name, 'c')

    def hotAssertOnUpdateSetNull(self, relation: Relation, fk_name: str):
        return self.__check_update_action(relation, fk_name, 'n')

    def hotAssertOnUpdateSetDefault(self, relation: Relation, fk_name: str):
        return self.__check_update_action(relation, fk_name, 'd')

    def hotAssertOnDeleteNoAction(self, relation: Relation, fk_name: str):
        return self.__check_delete_action(relation, fk_name, 'a')

    def hotAssertOnDeleteRestict(self, relation: Relation, fk_name: str):
        return self.__check_delete_action(relation, fk_name, 'r')

    def hotAssertOnDeleteCascade(self, relation: Relation, fk_name: str):
        return self.__check_delete_action(relation, fk_name, 'c')

    def hotAssertOnDeleteSetNull(self, relation: Relation, fk_name: str):
        return self.__check_delete_action(relation, fk_name, 'n')

    def hotAssertOnDeleteSetDefault(self, relation: Relation, fk_name: str):
        return self.__check_delete_action(relation, fk_name, 'd')

