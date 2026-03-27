# Model

:class:`Model` connects to a PostgreSQL database and acts as a factory for
:class:`~half_orm.relation.Relation` subclasses. One `Model` instance per
database is enough — it is shared across all relation classes.

```python
from half_orm.model import Model

blog = Model('blog')
Author = blog.get_relation_class('blog.author')
```

See [Learn halfORM in half an hour](../half-an-hour.md) for a full walkthrough.

---

## Connecting

::: half_orm.model.Model
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members: false

::: half_orm.model.Model.get_relation_class
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.ping
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.disconnect
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Async connection

::: half_orm.model.Model.aconnect
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.adisconnect
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Executing raw SQL

These methods execute SQL directly. Prefer the
:class:`~half_orm.relation.Relation` methods for standard CRUD operations.

::: half_orm.model.Model.execute_query
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.execute_function
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.call_procedure
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Inspection

::: half_orm.model.Model.has_relation
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.model.Model.sql_trace
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Decorator

::: half_orm.relation_factory.register_class
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3