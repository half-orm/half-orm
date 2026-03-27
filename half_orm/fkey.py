# -*- coding: utf-8 -*-
# pylint: disable=protected-access

"""This module provides the FKey class."""

from half_orm.pg_meta import normalize_fqrn, normalize_qrn
from half_orm import utils

def _would_create_cycle(from_rel, to_rel):
    """Return True if adding from_rel → to_rel would create a cycle in _ho_join_to."""
    target_id = id(from_rel)
    visited = set()
    stack = [to_rel]
    while stack:
        rel = stack.pop()
        if id(rel) == target_id:
            return True
        if id(rel) in visited:
            continue
        visited.add(id(rel))
        stack.extend(rel._ho_join_to.values())
    return False


class FKey:
    """Foreign key class

    A foreign key is set by assigning to it a Relation object of the
    corresponding type (see FKey.set method).
    It is then used to construct the join query for Relation.ho_select
    method.
    """

    def __init__(self,
                 fk_name, relation, fk_sfqrn,
                 fk_names=None, fields=None, confupdtype=None, confdeltype=None):
        self.__relation = relation
        self.__to_relation = None
        self.__name = fk_name
        self.__is_set = False
        self.__fk_names = fk_names or []
        self.__fk_from = None
        self.__fk_to = None
        self.__confupdtype = confupdtype
        self.__confdeltype = confdeltype
        self.__fk_fqrn = fk_sfqrn
        self.__fields_names = fields
        self.__fields = [f'"{name}"' for name in fields]

    def __get_rel(self, fqtn):
        """Returns the relation class referenced by fqtn.
        First try model._import_class fallback to model.get_relation_class on ImportError.
        """
        return self.__relation._ho_model._import_class(fqtn)

    def __call__(self, __cast__=None, **kwargs):
        """Returns the relation referenced by the fkey.
        Uses the __cast__ if it is set.
        """
        f_relation = self.__get_rel(__cast__ or normalize_qrn(self.__fk_fqrn))(**kwargs)
        rev_fkey_name = f'_reverse_{f_relation.ho_id}'
        f_relation._ho_fkeys[rev_fkey_name] = FKey(
            rev_fkey_name,
            f_relation,
            f_relation._t_fqrn, self.__fields, self.__fk_names)
        f_relation._ho_fkeys[rev_fkey_name].set(self.__relation)
        return f_relation

    def values(self):
        return [list(elt.values()) for elt in self.__to_relation.ho_select(*self.__fk_names)]

    def set(self, __to):
        """Bind this foreign key to a relation, adding a JOIN condition.

        After calling ``.set(other_rel)``, queries on the owning relation
        automatically include a JOIN against ``other_rel`` filtered by
        ``other_rel``'s constraints.

        Args:
            __to (Relation): the relation to join against.

        Returns:
            self — for chaining.

        Raises:
            RuntimeError: if ``__to`` is not a :class:`~half_orm.relation.Relation` instance.
            RuntimeError: if setting this FK would create a cycle in the join graph.

        Example:
            ::

                # "is a post whose author's last name starts with 'Mar'"
                post = Post()
                post.author_fk.set(Author(last_name=('like', 'Mar%')))
                print(post.ho_count())

        .. versionadded:: 0.18.6
            Raises ``RuntimeError`` if setting this FK would create a cycle in
            the join graph.
        """
        # pylint: disable=import-outside-toplevel
        from half_orm.relation import Relation

        if not issubclass(__to.__class__, Relation):
            raise RuntimeError("Fkey.set excepts an argument of type Relation")
        from_ = self.__relation
        if _would_create_cycle(from_, __to):
            raise RuntimeError(
                f"FKey cycle detected: {from_._qrn} → {__to._qrn} closes a loop in the join chain.")
        self.__to_relation = __to
        self.__fk_from = from_
        self.__fk_to = __to
        self.__is_set = __to.ho_is_set()
        from_._ho_join_to[self] = __to
        return self

    def is_set(self):
        """Return if the foreign key is set (boolean)."""
        return self.__is_set

    @property
    def confupdtype(self):
        "on update configuration"
        return self.__confupdtype

    @property
    def confdeltype(self):
        "on delete configuration"
        return self.__confdeltype

    #@utils.trace
    def _join_query(self, orig_rel):
        """Returns the join_query, join_values of a foreign key.
        fkey interface: frel, from_, __to, fields, fk_names
        """
        from_ = self.__fk_from
        __to = self.__fk_to
        orig_rel_id = f'r{orig_rel.ho_id}'
        to_id = f'r{__to.ho_id}'
        from_id = f'r{from_.ho_id}'
        if __to._qrn == orig_rel._qrn:
            to_id = orig_rel_id
        if from_._qrn == orig_rel._qrn:
            from_id = orig_rel_id
        from_fields = (f'{from_id}.{name}' for name in self.__fields)
        to_fields = (f'{to_id}.{name}' for name in self.__fk_names)
        bounds = " and ".join(
            [f'{a} = {b}' for a, b in zip(to_fields, from_fields)])
        return f"({bounds})"

    #@utils.trace
    def _fkey_prep_select(self):
        return (self.__fields, self.__fk_to._ho_prep_select(*self.fk_names)) if self.__is_set else None

    @property
    def name(self):
        "Returns the internal name of the foreign key"
        return self.__name

    @property
    def remote(self):
        "Returns the fqtn of the foreign table and if the link is reverse"
        return {'fqtn': self()._t_fqrn[1:], 'reverse': self.__name.find('_reverse_fkey_') == 0}

    @property
    def fk_names(self):
        """Returns the names of the fields composing the foreign key in the foreign table."""
        return self.__fk_names

    @property
    def names(self):
        "Returns the names of the fields composing the foreign key in the table"
        return self.__fields_names

    def __repr__(self):
        """Representation of a foreign key
        """
        fields = list(self.__fields)
        fields = f"({', '.join(fields)})"
        repr_ = f"- {self.__name}: {fields}\n ↳ {normalize_fqrn(self.__fk_fqrn)}({', '.join(self.fk_names)})"
        if self.__is_set:
            repr_value = str(self.__fk_to)
            res = []
            for line in repr_value.split('\n'):
                res.append(f'     {line}')
            res = '\n'.join(res)
            repr_ = f'{repr_}\n{res}'
        return repr_
