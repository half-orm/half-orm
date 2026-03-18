# Testing

## Inspecting query construction with `ho_where_display()`

`ho_where_display()` lets you inspect the JOIN and WHERE clauses built on a `Relation`
object without triggering any SQL execution. This is the recommended way to assert that
the constraints set on an object match expectations.

### Return value

```python
result = relation.ho_where_display()
```

Returns `None` if no constraint is set, otherwise a dict:

| Key | Type | Content |
|-----|------|---------|
| `'joins'` | `list[str]` | One SQL JOIN string per joined relation |
| `'where'` | `str \| None` | WHERE expression with `%s` placeholders |
| `'values'` | `list[str]` | Values in order (join values first, then where values) |

### Examples

#### Simple field constraint

```python
post = Post(title='Easy')
result = post.ho_where_display()

assert result['where'] == '("title" = %s::text)'
assert result['values'] == ['Easy']
assert result['joins'] == []
```

#### Composite constraint

```python
person = Person(last_name=('ilike', 'la%'), first_name='Gaston')
result = person.ho_where_display()

assert '("last_name" ilike %s' in result['where']
assert '("first_name" = %s' in result['where']
assert 'la%' in result['values']
assert 'Gaston' in result['values']
```

#### FK join constraint

```python
person = Person(last_name='Lagaffe')
posts = person.post_rfk(title='Easy')
result = posts.ho_where_display()

assert len(result['joins']) == 1          # one JOIN toward actor.person
assert result['where'] == '("title" = %s::text)'
assert 'Lagaffe' in result['values']
assert 'Easy' in result['values']
# join values appear before where values
assert result['values'].index('Lagaffe') < result['values'].index('Easy')
```

#### No constraint

```python
assert Post().ho_where_display() is None
```

### Using `ho_where_display()` in unit tests

```python
from unittest import TestCase

class TestQueryConstruction(TestCase):
    def test_fk_join_is_built(self):
        person = Person(last_name='Lagaffe')
        posts = person.post_rfk(title='Easy')
        result = posts.ho_where_display()

        self.assertIsNotNone(result)
        self.assertEqual(len(result['joins']), 1)
        self.assertIn('Lagaffe', result['values'])
        self.assertIn('Easy', result['values'])
```