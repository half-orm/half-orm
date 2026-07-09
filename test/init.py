#!/usr/bin/env python3

import os
import sys
from datetime import date
from half_orm.model import Model
from half_orm.relation import singleton
from half_orm.transaction import Transaction

path = os.path.dirname(__file__)
sys.path.insert(0, f'{path}/halftest')

README = """
Create the database halftest First:
- psql template1 -f {}/sql/halftest.sql
This command will create:
- a user halftest.
  When prompted for the password type: halftest
- a database halftest

To drop halftest database and user when you're done with the tests:
- dropdb halftest; dropuser halftest
"""

model = Model('halftest', scope="halftest")
model_with_meta = Model('halftest', scope="halftest", with_half_orm_meta=True)

HALFTEST_STR = '''📋 Available relations for halftest:
r "actor"."person"            → The table actor.person contains the persons of the blogging system. The id attribute is a serial. Just pass first_name, last_name and birth_date to insert a new person.
r "blog"."comment"            → The table blog.comment contains all the comments made by a person on a post.
r "blog"."event"              → The table blog.event contains all the events of the blogging system. It inherits blog.post. It's just here to illustrate the inheriance in half_orm
r "blog"."post"               → The table blog.post contains all the post made by a person in the blogging system.
v "blog.view"."post_comment"  → This view joins: - comment, - author of the comment, - post, - author of the post.

📋 Relation Types:
  r: Table
  p: Partioned table
  v: View
  m: Materialized view
  f: Foreign data'''

HALFTEST_REL_LISTS = [
    ('r', ('halftest', 'actor', 'person')),
    ('r', ('halftest', 'blog', 'comment')),
    ('r', ('halftest', 'blog', 'event')),
    ('r', ('halftest', 'blog', 'post')),
    ('r', ('halftest', 'half_orm_meta', 'database')),
    ('r', ('halftest', 'half_orm_meta', 'hop_release')),
    ('r', ('halftest', 'half_orm_meta', 'hop_release_issue')),
    ('v', ('halftest', 'blog.view', 'post_comment')),
    ('v', ('halftest', 'half_orm_meta.view', 'hop_last_release')),
    ('v', ('halftest', 'half_orm_meta.view', 'hop_penultimate_release'))
]

HALFTEST_DESC = [
    ('r', ('halftest', 'actor', 'person'), []),
    ('r', ('halftest', 'blog', 'comment'), []),
    ('r', ('halftest', 'blog', 'event'), [('halftest', 'blog', 'post')]),
    ('r', ('halftest', 'blog', 'post'), []),
    ('v', ('halftest', 'blog.view', 'post_comment'), [])
]

GASTON = {
    'last_name': 'Lagaffe', 'first_name': 'Gaston', 'birth_date': '1957-02-28'
}

def name(letter, integer):
    return f"{letter}{chr(ord('a') + integer)}"

class HalfTest:
    def __init__(self):
        self.model = model
        assert model._scope == "halftest"
        self.dbname = model._dbname
        self.today = date.today()
        self.person_cls = model._import_class("actor.person")
        self.person_cls().ho_delete(delete_all=True)
        self.post_cls = model._import_class("blog.post")
        self.comment_cls = model._import_class("blog.comment")
        self.event_cls = model._import_class("blog.event")
        self.blog_view_cls = model._import_class("blog.view.post_comment")
        class PC(self.person_cls):
            def last_name(self):
                # a method with the name of a field.
                pass

        self._person = self.person_cls()
        self.gaston = self.person_cls(**GASTON)
        self.pc = PC()
        self.relation = model._import_class

        def init_pers(pers):
            sys.stderr.write('Initializing actor.person\n')
            self.person_cls().ho_delete(delete_all=True)
            self.post_cls().ho_delete(delete_all=True)
            for letter in 'abcdef':
                for i in range(10):
                    last_name = name(letter, i)
                    first_name = name(letter, 0)
                    birth_date = self.today
                    print(list(pers()))
                    pers(
                        last_name=last_name,
                        first_name=first_name,
                        birth_date=birth_date).ho_insert()

        if self.person_cls().ho_count() != 60:
            with Transaction(model):
                init_pers(self.person_cls())

halftest = HalfTest()
