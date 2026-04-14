#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

"""Systematic FK algebra tests, in the spirit of test/relation/algebra_test.py.

Data setup
----------
- 2 authors:  person_a (last_name='fk_alg_a'), person_b (last_name='fk_alg_b')
- 3 posts:    post_1 and post_2 written by person_a, post_3 written by person_b
- 4 comments: c1 (by a on post_1), c2 (by b on post_1),
              c3 (by a on post_3), c4 (by b on post_2)

Derived facts used in tests
----------------------------
- post_rfk(a) = {post_1, post_2}          count 2
- post_rfk(b) = {post_3}                  count 1
- comment_rfk(a) = {c1, c3}              count 2
- comment_rfk(b) = {c2, c4}              count 2
- posts written by a | posts commented on by a = {post_1, post_2, post_3}  count 3
- posts written by a & posts commented on by a = {post_1}                  count 1
"""

from unittest import TestCase
from half_orm.null import NULL

from ..init import halftest


class TestFKeyAlgebra(TestCase):
    """Set algebra properties on FK-navigated relations (single hop)."""

    def setUp(self):
        pers = halftest.person_cls
        post = halftest.post_cls
        comment = halftest.comment_cls

        self.person_a = pers(
            last_name='fk_alg_a', first_name='fk_alg_a', birth_date='1970-01-01'
        ).ho_insert()
        self.person_b = pers(
            last_name='fk_alg_b', first_name='fk_alg_b', birth_date='1970-01-01'
        ).ho_insert()

        def make_pers(row):
            return pers(
                last_name=row['last_name'],
                first_name=row['first_name'],
                birth_date=row['birth_date'],
            )

        pa = make_pers(self.person_a)
        pb = make_pers(self.person_b)

        r1 = pa.post_rfk(title='fk_alg post_1', content='c1').ho_insert()
        r2 = pa.post_rfk(title='fk_alg post_2', content='c2').ho_insert()
        r3 = pb.post_rfk(title='fk_alg post_3', content='c3').ho_insert()

        self.post_id_1 = r1['id']
        self.post_id_2 = r2['id']
        self.post_id_3 = r3['id']

        post(id=self.post_id_1).comment_rfk(
            content='fk_alg c1', author_id=self.person_a['id']
        ).ho_insert()
        post(id=self.post_id_1).comment_rfk(
            content='fk_alg c2', author_id=self.person_b['id']
        ).ho_insert()
        post(id=self.post_id_3).comment_rfk(
            content='fk_alg c3', author_id=self.person_a['id']
        ).ho_insert()
        post(id=self.post_id_2).comment_rfk(
            content='fk_alg c4', author_id=self.person_b['id']
        ).ho_insert()

        # Convenience accessors — fresh instances each time to avoid ho_id sharing
        self._pa = make_pers
        self._pb = make_pers
        self.pa_row = self.person_a
        self.pb_row = self.person_b

    def tearDown(self):
        halftest.person_cls(last_name=('like', 'fk_alg%')).ho_delete()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def pa(self):
        """Fresh person_a instance."""
        return halftest.person_cls(
            last_name=self.person_a['last_name'],
            first_name=self.person_a['first_name'],
            birth_date=self.person_a['birth_date'],
        )

    def pb(self):
        """Fresh person_b instance."""
        return halftest.person_cls(
            last_name=self.person_b['last_name'],
            first_name=self.person_b['first_name'],
            birth_date=self.person_b['birth_date'],
        )

    # ------------------------------------------------------------------
    # Basic navigation counts
    # ------------------------------------------------------------------

    def test_post_rfk_a_count(self):
        "person_a has 2 posts."
        self.assertEqual(self.pa().post_rfk().ho_count(), 2)

    def test_post_rfk_b_count(self):
        "person_b has 1 post."
        self.assertEqual(self.pb().post_rfk().ho_count(), 1)

    def test_comment_rfk_a_count(self):
        "person_a wrote 2 comments."
        self.assertEqual(
            halftest.comment_cls(author_id=self.person_a['id']).ho_count(), 2
        )

    def test_comment_rfk_b_count(self):
        "person_b wrote 2 comments."
        self.assertEqual(
            halftest.comment_cls(author_id=self.person_b['id']).ho_count(), 2
        )

    # ------------------------------------------------------------------
    # Union
    # ------------------------------------------------------------------

    def test_or_count(self):
        "Union of posts by a and posts by b = all 3 posts."
        result = self.pa().post_rfk() | self.pb().post_rfk()
        self.assertEqual(result.ho_count(), 3)

    def test_or_commutativity(self):
        "Union is commutative: a | b = b | a."
        ab = self.pa().post_rfk() | self.pb().post_rfk()
        ba = self.pb().post_rfk() | self.pa().post_rfk()
        self.assertEqual(ab.ho_count(), ba.ho_count())

    def test_or_idempotent(self):
        "Union is idempotent: a | a = a."
        posts_a = self.pa().post_rfk()
        posts_a2 = self.pa().post_rfk()
        self.assertEqual(
            (posts_a | posts_a2).ho_count(), posts_a.ho_count()
        )

    def test_or_neutral_element(self):
        "Empty set is the neutral element of union: a | ∅ = a."
        posts_a = self.pa().post_rfk()
        empty = halftest.post_cls(title=NULL)  # impossible title
        result = posts_a | empty
        self.assertEqual(result.ho_count(), posts_a.ho_count())

    # ------------------------------------------------------------------
    # Intersection
    # ------------------------------------------------------------------

    def test_and_disjoint(self):
        "Posts by a and posts by b are disjoint: a & b = ∅."
        result = self.pa().post_rfk() & self.pb().post_rfk()
        self.assertEqual(result.ho_count(), 0)

    def test_and_commutativity(self):
        "Intersection is commutative: a & b = b & a."
        ab = self.pa().post_rfk() & self.pb().post_rfk()
        ba = self.pb().post_rfk() & self.pa().post_rfk()
        self.assertEqual(ab.ho_count(), ba.ho_count())

    def test_and_idempotent(self):
        "Intersection is idempotent: a & a = a."
        posts_a = self.pa().post_rfk()
        posts_a2 = self.pa().post_rfk()
        self.assertEqual(
            (posts_a & posts_a2).ho_count(), posts_a.ho_count()
        )

    # ------------------------------------------------------------------
    # Difference
    # ------------------------------------------------------------------

    def test_sub_all(self):
        "Difference: (a | b) - b = a."
        all_posts = self.pa().post_rfk() | self.pb().post_rfk()
        posts_b = self.pb().post_rfk()
        result = all_posts - posts_b
        self.assertEqual(result.ho_count(), self.pa().post_rfk().ho_count())

    def test_sub_self(self):
        "A set minus itself is empty: a - a = ∅."
        posts_a = self.pa().post_rfk()
        posts_a2 = self.pa().post_rfk()
        self.assertEqual((posts_a - posts_a2).ho_count(), 0)

    # ------------------------------------------------------------------
    # Associativity and distributivity (single-hop)
    # ------------------------------------------------------------------

    def test_or_associativity(self):
        "(a | b) | c = a | (b | c)  using titles as surrogates for 3 sets."
        post = halftest.post_cls
        p1 = post(id=self.post_id_1)
        p2 = post(id=self.post_id_2)
        p3 = post(id=self.post_id_3)
        self.assertEqual(
            ((p1 | p2) | p3).ho_count(),
            (p1 | (p2 | p3)).ho_count(),
        )

    def test_and_associativity(self):
        "(a & b) & c = a & (b & c)."
        post = halftest.post_cls
        # Three overlapping sets by id range is hard with fixed data,
        # use universe intersection instead (all & all = all).
        all_fk_posts = halftest.post_cls(title=('like', 'fk_alg%'))
        a = all_fk_posts
        b = all_fk_posts
        c = all_fk_posts
        self.assertEqual(
            ((a & b) & c).ho_count(),
            (a & (b & c)).ho_count(),
        )

    # ------------------------------------------------------------------
    # Multi-hop chaining + algebra
    # ------------------------------------------------------------------

    def test_chain_union(self):
        "Comments on posts by a | comments on posts by b = all 4 comments."
        comments_via_a = self.pa().post_rfk().comment_rfk()
        comments_via_b = self.pb().post_rfk().comment_rfk()
        result = comments_via_a | comments_via_b
        # post_1 (3 comments? no — 2: c1 by a, c2 by b)
        # post_2 (1: c4 by b)
        # post_3 (1: c3 by a)
        # total distinct comments = 4
        self.assertEqual(result.ho_count(), 4)

    def test_chain_intersection(self):
        "Comments on posts by a & comments on posts by b."
        # post_1 is by a; c1 and c2 are on post_1
        # post_2 is by a; c4 is on post_2
        # post_3 is by b; c3 is on post_3
        # comments_via_a = {c1, c2, c4}, comments_via_b = {c3}
        # intersection = ∅
        comments_via_a = self.pa().post_rfk().comment_rfk()
        comments_via_b = self.pb().post_rfk().comment_rfk()
        result = comments_via_a & comments_via_b
        self.assertEqual(result.ho_count(), 0)

    # ------------------------------------------------------------------
    # Multi-path to the same relation (shared instance bug scenario)
    # ------------------------------------------------------------------

    def test_multipath_or_count(self):
        """Posts written by a | posts commented on by a.

        Two FK paths both ultimately reference the same person_a instance.
        The union should be {post_1, post_2, post_3} = 3.
        """
        pa = self.pa()
        posts_written = pa.post_rfk()
        # Use a separate pa instance to avoid the shared-instance problem
        pa2 = self.pa()
        posts_commented = pa2.comment_rfk().post_fk()
        result = posts_written | posts_commented
        # written by a: post_1, post_2
        # commented on by a: post_1 (c1), post_3 (c3)
        # union: post_1, post_2, post_3 → 3
        self.assertEqual(result.ho_count(), 3)

    def test_multipath_and_count(self):
        """Posts written by a & posts commented on by a = {post_1}."""
        pa = self.pa()
        posts_written = pa.post_rfk()
        pa2 = self.pa()
        posts_commented = pa2.comment_rfk().post_fk()
        result = posts_written & posts_commented
        self.assertEqual(result.ho_count(), 1)

    def test_multipath_or_commutativity(self):
        """(posts written by a | posts commented on by a) should be commutative."""
        pa1 = self.pa()
        pa2 = self.pa()
        written_first = pa1.post_rfk() | pa2.comment_rfk().post_fk()

        pb1 = self.pa()
        pb2 = self.pa()
        commented_first = pb1.comment_rfk().post_fk() | pb2.post_rfk()

        self.assertEqual(written_first.ho_count(), commented_first.ho_count())

    def test_multipath_shared_instance_or(self):
        """Same person instance used on both sides of | — exposes the shared-instance bug.

        When person_a is the SAME Python object on both sides, both FK chains
        share ho_id(person_a). _ho_build_joins deduplicates on ho_id, so one
        JOIN path may be dropped.  The correct count is 3.
        """
        pa = self.pa()
        # Both sides share the same `pa` instance
        posts_written = pa.post_rfk()
        posts_commented = pa.comment_rfk().post_fk()
        result = posts_written | posts_commented
        self.assertEqual(result.ho_count(), 3)