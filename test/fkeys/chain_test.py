#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import contextlib
import io
import random
from unittest import TestCase

from ..init import halftest

class Test(TestCase):
    "Fkeys chaining tests"
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.comment = halftest.comment_cls()
        self.authors = []
        self.posts = []
        self.comments = []
        self.posts_by_author = {}
        self.authors_by_post = {}
        self.author_of_comment = {}
        self.comments_by_post = {}
        self.comments_by_author = {}
        self.author_comments_on_his_own_post = set()
        for author_idx in range(3):
            name = f'fkeys chain tester {author_idx}'
            self.authors.append(
                halftest.person_cls(last_name=name, first_name=name, birth_date='1970-01-01')
                .ho_insert())
        for post_idx in range(5):
            author_id = self.authors[random.randint(0, len(self.authors) - 1)]['id']
            title = f"test chaining post {post_idx} by {author_id}"
            self.posts.append(
                halftest.person_cls(id=author_id).post_rfk(title=title, content=title)
                .ho_insert())
            post_id = self.posts[-1]['id']
            if not post_id in self.authors_by_post:
                self.authors_by_post[post_id] = []
            self.authors_by_post[post_id].append(author_id)
            if not author_id in self.posts_by_author:
                self.posts_by_author[author_id] = []
            self.posts_by_author[author_id].append(post_id)
        for post in self.posts:
            for comment_idx in range(3):
                post_id = post['id']
                author_id = self.authors[random.randint(0, len(self.authors) - 1)]['id']
                content = f"test chaining comment {comment_idx} by {author_id} on {post['title']}"
                self.comments.append(
                    halftest.post_cls(id=post_id).comment_rfk(content=content, author_id=author_id)
                    .ho_insert())
                comment_id = self.comments[-1]['id']
                self.author_of_comment[comment_id] = author_id
                if not author_id in self.comments_by_author:
                    self.comments_by_author[author_id] = []
                self.comments_by_author[author_id].append(comment_id)
                if not post_id in self.comments_by_post:
                    self.comments_by_post[post_id] = []
                if author_id in self.authors_by_post[post_id]:
                    self.author_comments_on_his_own_post.add(comment_id)
                self.comments_by_post[post_id].append(comment_id)

    def tearDown(self):
        halftest.person_cls(last_name=('like', 'fkeys chain tester%')).ho_delete()

    def test_chain_person_post_comment(self):
        "it should be possible to chain from person to comment via post"
        self.assertIsInstance(self.pers.post_rfk().comment_rfk(), halftest.comment_cls)

    def test_author_comments_on_his_own_post(self):
        "it should retreive the comments made on posts by the same author"
        nb_comments = 0
        for person in self.authors:
            person_id = person['id']
            person_first_name = person['first_name']
            comments = list(halftest.person_cls()
                .post_rfk(author_first_name=person_first_name)
                .comment_rfk(author_id=person_id))
            nb_comments += len(comments)
            for comment in comments:
                self.assertIn(comment['post_id'], self.posts_by_author[comment['author_id']])
                self.assertIn(comment['id'], self.author_comments_on_his_own_post)
        self.assertEqual(len(self.author_comments_on_his_own_post), nb_comments)

    def test_chain_post_comment_author(self):
        "it should be possible to chain from post to author via comment"
        self.assertIsInstance(self.post.comment_rfk().author_fk(), halftest.person_cls)

    def test_chain_comment_post_author(self):
        "it should be possible to chain from comment to author via post"
        self.assertIsInstance(self.comment().post_fk().author_fk(), halftest.person_cls)

    def test_ho_select_dedup_on_join(self):
        "ho_select should deduplicate rows when a JOIN produces duplicate PKs"
        # comment → post_fk → author_fk: one row per comment without dedup (5 posts × 3 comments = 15),
        # one row per distinct post-author with dedup.
        persons_with_join = self.comment.post_fk().author_fk()
        distinct_post_authors = {
            author_id
            for post in self.posts
            for author_id in self.authors_by_post[post['id']]
        }
        stderr_output = io.StringIO()
        with contextlib.redirect_stderr(stderr_output):
            result = list(persons_with_join.ho_select())
        self.assertEqual(len(result), len(distinct_post_authors))
        self.assertIn('duplicate(s) removed', stderr_output.getvalue())
