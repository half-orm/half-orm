"This module provides the factory function"

import sys
from functools import wraps

from half_orm import pg_meta
from half_orm import model_errors
from half_orm import utils
from half_orm.relation import Relation

def register_class(relation_class):
    """Register a :class:`~half_orm.relation.Relation` subclass with its Model.

    After registration, FK navigation and factory calls return instances of
    the custom subclass instead of the generated base class, making
    ``Fkeys`` aliases and custom methods available throughout.

    Args:
        relation_class: a class that subclasses the result of
            :meth:`~half_orm.model.Model.get_relation_class`.

    Returns:
        relation_class — the decorated class, unchanged.

    Raises:
        ValueError: if ``relation_class`` is not a valid relation subclass.

    Example:
        Register a class:
            ```python
            from half_orm.model import Model, register

            blog = Model('blog')

            @register
            class Author(blog.get_relation_class('blog.author')):
                Fkeys = {'post_rfk': '_reverse_fkey_blog_blog_post_author_id'}
            ```
    """
    try:
        rel_id = id(relation_class)
        if rel_id in relation_class._rels_ids:
            return relation_class
        model = relation_class._ho_model
        dbname = model._dbname
        # The triple the class was generated for, not `_qrn` taken apart on
        # its last dot: for a relation whose own name holds a dot that gave
        # the key of another relation, and registered the class in its place.
        key = tuple(relation_class._t_fqrn)
        model._classes_[dbname][key] = relation_class
        relation_class._rels_ids[rel_id] = key
        return relation_class
    except AttributeError as exc:
        raise ValueError(f"Invalid relation class: {exc}")

def factory(dct):
    """Factory function that generates a `Relation` subclass corresponding to a PostgreSQL relation.

    Args:
        dct (dict): a dictionary containing the following keys:
            - 'fqrn' (tuple): a fully qualified relation name, which is a tuple of 3 strings:
                the database name, the schema name and the relation name.
            - 'model' (Model): an instance of the `Model` class representing the database model.

    Returns:
        A `Relation` subclass that corresponds to the specified PostgreSQL relation.
        The class name is generated using the database name, the schema name and the relation name,
        and it inherits from the `Relation` class.

    Raises:
        UnknownRelationError: if the specified relation does not exist in the database.
    """
    def _gen_class_name(rel_kind, sfqrn):
        """Generates class name from relation kind and FQRN tuple"""
        class_name = "".join([elt.capitalize() for elt in
                            [elt.replace('.', '') for elt in sfqrn]])
        return f"{rel_kind}_{class_name}"

    bases = [Relation,]
    tbl_attr = {}
    tbl_attr['_ho_fkeys_properties'] = False
    tbl_attr['_qrn'] = pg_meta.normalize_qrn(dct['fqrn'])

    tbl_attr.update(dict(zip(['_dbname', '_schemaname', '_relationname'], dct['fqrn'])))
    model = dct['model']
    model._classes_.setdefault(tbl_attr['_dbname'], {})
    tbl_attr['_ho_model'] = model
    tbl_attr['_ho_fields_aliases'] = dct is not None and dct.get('fields_aliases', {}) or {}
    dbname, schema, relation = dct['fqrn']
    rel_class = None
    if model._classes_.get(dbname):
        rel_class = model._classes_[dbname].get((dbname, schema, relation))
    if not rel_class:
        try:
            metadata = model._relation_metadata(dct['fqrn'])
        except KeyError as exc:
            raise model_errors.UnknownRelation(dct['fqrn']) from exc
        if metadata['inherits']:
            metadata['inherits'].sort()
            bases = []
            for parent_fqrn in metadata['inherits']:
                # Quoted, so that a dot in either part stays where it is.
                parent_qtn = pg_meta.normalize_qrn(parent_fqrn)
                parent_class = model._import_class(parent_qtn)
                bases.append(parent_class)
        tbl_attr['_ho_metadata'] = metadata
        tbl_attr['_t_fqrn'] = dct['fqrn']
        tbl_attr['_fqrn'] = pg_meta.normalize_fqrn(dct['fqrn'])
        tbl_attr['_ho_kind'] = pg_meta.REL_CLASS_NAMES[metadata['tablekind']]
        class_name = _gen_class_name(pg_meta.REL_CLASS_NAMES[metadata['tablekind']], dct['fqrn'])
        rel_class = type(class_name, tuple(bases), tbl_attr)
        model._classes_[tbl_attr['_dbname']][dct['fqrn']] = rel_class
    return rel_class
