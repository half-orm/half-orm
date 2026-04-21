#!/usr/bin/env python
from half_orm.model import Model
from half_orm.relation import singleton

from unittest import TestCase
from ..init import halftest
from half_orm import model_errors, model

halftest = Model('halftest') # We connect to the PostgreSQL database
# print(halftest) to get the list of relations in the database

class Post(halftest.get_relation_class('blog.post')):
    """blog.post is a table of the halftest database (<schema>.<relation>)
    To get a full description of the relation, use print(Post())
    """
    Fkeys = { # we set some aliases for the foreign keys (direct AND reverse) (half_orm >= 0.6.5)
        'comments': '_reverse_fkey_halftest_blog_comment_post_id', # a post is referenced by comments
        'author': 'author' # the post references a person
    }

class Person(halftest.get_relation_class('actor.person')):
    Fkeys = {
        'posts': '_reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date',
        'comments': '_reverse_fkey_halftest_blog_comment_author_id'
    }
    @singleton # we ensure that self is a singleton of the actor.person table
    def add_post(self, title: str=None, content: str=None) -> dict:
        return self.posts(title=title, content=content).ho_insert() # we use the ho_insert method
    @singleton
    def add_comment(self, post: Post=None, content: str=None) -> dict:
        return self.comments(content=content, post_id=post.id.value, author_id=self.id.value).ho_insert()

def main():
    # let's define a Person set (a singleton here) by instanciating a set with some constraints
    gaston = Person(last_name='Lagaffe', first_name='Gaston', birth_date='1957-02-28')
    gaston.ho_delete() # the delete method
    gaston.ho_insert(upsert=True)
    post_dct = gaston.add_post(title='Easy', content='halfORM is fun!')
    post = Post(**post_dct)
    gaston.add_comment(content='This is a comment on the newly created post.', post=post)
    post.ho_update(title='Super easy')
    gaston.ho_delete()

class Test(TestCase):
    def setUp(self):
        self.gaston = Person(last_name='Lagaffe', first_name='Gaston', birth_date='1957-02-28')

    def tearDown(self):
        self.gaston.ho_delete()

    def test_readme(self):
        "it should run main"
        main()
