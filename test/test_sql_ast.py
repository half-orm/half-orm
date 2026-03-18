# -*- coding: utf-8 -*-

"""Unit tests for the sql_ast module.

These tests verify the structure → SQL rendering without any database
connection, ensuring that each AST node produces the expected SQL string
and values list.
"""

import unittest
from half_orm.sql_ast import (
    FieldExpr, And, Or, Not, Raw, Group, SetOp,
    Join, Returning,
    Select, Insert, Update, Delete,
)


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------

class TestFieldExpr(unittest.TestCase):
    def test_simple_eq(self):
        expr = FieldExpr('r1."name"', "=", "%s::text", "Alice")
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."name" = %s::text')
        self.assertEqual(vals, ["Alice"])

    def test_like(self):
        expr = FieldExpr('r1."name"', "like", "%s::text", "A%")
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."name" like %s::text')
        self.assertEqual(vals, ["A%"])

    def test_in(self):
        expr = FieldExpr('r1."id"', "in", "%s", (1, 2, 3))
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."id" = ANY(%s)')
        self.assertEqual(vals, [(1, 2, 3)])

    def test_is_null(self):
        expr = FieldExpr('r1."deleted"', "is", "%s", None)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."deleted" is NULL')
        self.assertEqual(vals, [])

    def test_unaccent(self):
        expr = FieldExpr('r1."city"', "=", "%s::text", "Montréal", unaccent=True)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'unaccent(r1."city") = unaccent(%s::text)')
        self.assertEqual(vals, ["Montréal"])

    def test_array_any(self):
        expr = FieldExpr('r1."tags"', "=", "%s", "python", array_any=True)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, '%s = ANY(r1."tags")')
        self.assertEqual(vals, ["python"])


class TestAnd(unittest.TestCase):
    def test_empty(self):
        sql, vals = And([]).to_sql()
        self.assertEqual(sql, "")
        self.assertEqual(vals, [])

    def test_single(self):
        expr = And([FieldExpr('r1."a"', "=", "%s", 1)])
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."a" = %s')
        self.assertEqual(vals, [1])

    def test_multiple(self):
        expr = And([
            FieldExpr('r1."a"', "=", "%s", 1),
            FieldExpr('r1."b"', ">", "%s", 2),
        ])
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."a" = %s  and r1."b" > %s')
        self.assertEqual(vals, [1, 2])


class TestOr(unittest.TestCase):
    def test_multiple(self):
        expr = Or([
            FieldExpr('r1."a"', "=", "%s", 1),
            FieldExpr('r1."b"', "=", "%s", 2),
        ])
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'r1."a" = %s or\n    r1."b" = %s')
        self.assertEqual(vals, [1, 2])


class TestNot(unittest.TestCase):
    def test_negation(self):
        expr = Not(FieldExpr('r1."x"', "=", "%s", 5))
        sql, vals = expr.to_sql()
        self.assertEqual(sql, 'not (r1."x" = %s)')
        self.assertEqual(vals, [5])


class TestRaw(unittest.TestCase):
    def test_literal(self):
        sql, vals = Raw("TRUE").to_sql()
        self.assertEqual(sql, "TRUE")
        self.assertEqual(vals, [])

    def test_with_values(self):
        sql, vals = Raw("x = %s", [42]).to_sql()
        self.assertEqual(sql, "x = %s")
        self.assertEqual(vals, [42])


class TestGroup(unittest.TestCase):
    def test_wraps_in_parens(self):
        expr = Group(And([
            FieldExpr('r1."a"', "=", "%s", 1),
            FieldExpr('r1."b"', "=", "%s", 2),
        ]))
        sql, vals = expr.to_sql()
        self.assertEqual(sql, '(r1."a" = %s  and r1."b" = %s)')
        self.assertEqual(vals, [1, 2])


class TestSetOp(unittest.TestCase):
    def test_and_op(self):
        left = Group(And([FieldExpr('r1."a"', "=", "%s", 1)]))
        right = Group(And([FieldExpr('r1."b"', "=", "%s", 2)]))
        expr = SetOp(left, "and", right)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, '(r1."a" = %s) and\n    (r1."b" = %s)')
        self.assertEqual(vals, [1, 2])

    def test_or_op(self):
        left = Group(And([FieldExpr('r1."x"', "=", "%s", 10)]))
        right = Group(And([FieldExpr('r1."y"', "=", "%s", 20)]))
        expr = SetOp(left, "or", right)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, '(r1."x" = %s) or\n    (r1."y" = %s)')
        self.assertEqual(vals, [10, 20])

    def test_and_not(self):
        left = Group(And([FieldExpr('r1."a"', "=", "%s", 1)]))
        right = Group(And([FieldExpr('r1."b"', "=", "%s", 2)]))
        expr = SetOp(left, "and not", right)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, '(r1."a" = %s) and not\n    (r1."b" = %s)')
        self.assertEqual(vals, [1, 2])

    def test_no_right(self):
        left = Raw("TRUE")
        expr = SetOp(left, "and", None)
        sql, vals = expr.to_sql()
        self.assertEqual(sql, "TRUE")
        self.assertEqual(vals, [])

    def test_nested_set_ops(self):
        """(a=1 and b=2) or (c=3 and not d=4)"""
        ab = SetOp(
            Group(And([FieldExpr('r1."a"', "=", "%s", 1)])),
            "and",
            Group(And([FieldExpr('r1."b"', "=", "%s", 2)])),
        )
        cd = SetOp(
            Group(And([FieldExpr('r1."c"', "=", "%s", 3)])),
            "and not",
            Group(And([FieldExpr('r1."d"', "=", "%s", 4)])),
        )
        top = SetOp(Group(ab), "or", Group(cd))
        sql, vals = top.to_sql()
        self.assertIn("or", sql)
        self.assertEqual(vals, [1, 2, 3, 4])


# ---------------------------------------------------------------------------
# JOIN
# ---------------------------------------------------------------------------

class TestJoin(unittest.TestCase):
    def test_simple_join(self):
        j = Join('"public"."post" as r99', '(r99."author_id" = r1."id")')
        sql, vals = j.to_sql()
        self.assertIn("join", sql)
        self.assertIn("r99", sql)
        self.assertIn('r99."author_id" = r1."id"', sql)
        self.assertEqual(vals, [])

    def test_join_with_where(self):
        j = Join(
            '"public"."post" as r99',
            '(r99."author_id" = r1."id")',
            where=FieldExpr('r99."status"', "=", "%s::text", "published"),
        )
        sql, vals = j.to_sql()
        self.assertIn('r99."status" = %s::text', sql)
        self.assertEqual(vals, ["published"])


# ---------------------------------------------------------------------------
# Returning
# ---------------------------------------------------------------------------

class TestReturning(unittest.TestCase):
    def test_single_column(self):
        self.assertEqual(Returning(["id"]).to_sql(), " returning id")

    def test_star(self):
        self.assertEqual(Returning(["*"]).to_sql(), " returning *")

    def test_multiple(self):
        self.assertEqual(Returning(["id", "name"]).to_sql(), " returning id, name")


# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------

class TestSelect(unittest.TestCase):
    def test_simple_select_all(self):
        stmt = Select(columns=["r1.*"], from_table='"public"."person" as r1')
        sql, vals = stmt.to_sql()
        self.assertIn("select", sql)
        self.assertIn("r1.*", sql)
        self.assertIn('"public"."person" as r1', sql)
        self.assertNotIn("where", sql)
        self.assertEqual(vals, [])

    def test_select_with_where(self):
        stmt = Select(
            columns=["r1.*"],
            from_table='"public"."person" as r1',
            where=And([FieldExpr('r1."name"', "=", "%s::text", "Alice")]),
        )
        sql, vals = stmt.to_sql()
        self.assertIn("where", sql)
        self.assertIn('r1."name" = %s::text', sql)
        self.assertEqual(vals, ["Alice"])

    def test_distinct(self):
        stmt = Select(columns=["r1.*"], from_table='"t" as r1', distinct=True)
        sql, _ = stmt.to_sql()
        self.assertIn("distinct", sql)

    def test_order_by(self):
        stmt = Select(columns=["r1.*"], from_table='"t" as r1', order_by="name")
        sql, _ = stmt.to_sql()
        self.assertIn("order by name", sql)

    def test_limit_offset(self):
        stmt = Select(columns=["r1.*"], from_table='"t" as r1', limit=10, offset=5)
        sql, _ = stmt.to_sql()
        self.assertIn("limit 10", sql)
        self.assertIn("offset 5", sql)

    def test_only(self):
        stmt = Select(columns=["r1.*"], from_table='"t" as r1', only=True)
        sql, _ = stmt.to_sql()
        self.assertIn("only", sql)

    def test_with_join(self):
        j = Join('"public"."post" as r2', '(r2."author_id" = r1."id")')
        stmt = Select(
            columns=["r1.*"],
            from_table='"public"."person" as r1',
            joins=[j],
            where=And([FieldExpr('r1."name"', "=", "%s", "Bob")]),
        )
        sql, vals = stmt.to_sql()
        self.assertIn("join", sql)
        self.assertIn("where", sql)
        self.assertEqual(vals, ["Bob"])

    def test_join_values_before_where_values(self):
        """JOIN values must come before WHERE values in the values list."""
        j = Join(
            '"public"."post" as r2',
            '(r2."author_id" = r1."id")',
            where=FieldExpr('r2."status"', "=", "%s", "active"),
        )
        stmt = Select(
            columns=["r1.*"],
            from_table='"public"."person" as r1',
            joins=[j],
            where=And([FieldExpr('r1."name"', "=", "%s", "Bob")]),
        )
        sql, vals = stmt.to_sql()
        self.assertEqual(vals, ["active", "Bob"])

    def test_no_where_when_empty_expr(self):
        stmt = Select(
            columns=["r1.*"],
            from_table='"t" as r1',
            where=And([]),
        )
        sql, vals = stmt.to_sql()
        self.assertNotIn("where", sql)
        self.assertEqual(vals, [])


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

class TestInsert(unittest.TestCase):
    def test_simple(self):
        stmt = Insert(
            table='"public"."person"',
            columns=['"name"', '"age"'],
            placeholders=["%s", "%s"],
            values=["Alice", 30],
        )
        sql, vals = stmt.to_sql()
        self.assertEqual(sql, 'insert into "public"."person" ("name", "age") values (%s, %s)')
        self.assertEqual(vals, ["Alice", 30])

    def test_with_returning(self):
        stmt = Insert(
            table='"public"."person"',
            columns=['"name"'],
            placeholders=["%s"],
            values=["Alice"],
            returning=Returning(["*"]),
        )
        sql, vals = stmt.to_sql()
        self.assertIn("returning *", sql)


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

class TestUpdate(unittest.TestCase):
    def test_simple(self):
        stmt = Update(
            table='"public"."person"',
            set_clause=[('"name" = %s', "Bob")],
            where=And([FieldExpr('"id"', "=", "%s", 42)]),
        )
        sql, vals = stmt.to_sql()
        self.assertIn('update "public"."person" set "name" = %s', sql)
        self.assertIn("where", sql)
        self.assertEqual(vals, ["Bob", 42])

    def test_with_fk_where(self):
        stmt = Update(
            table='"t"',
            set_clause=[('"x" = %s', 1)],
            where=And([FieldExpr('"id"', "=", "%s", 10)]),
            fk_where='("fk_col") in (%s)',
            fk_values=[99],
        )
        sql, vals = stmt.to_sql()
        self.assertIn('("fk_col") in (%s)', sql)
        self.assertEqual(vals, [1, 10, 99])

    def test_no_where(self):
        stmt = Update(table='"t"', set_clause=[('"x" = %s', 1)])
        sql, vals = stmt.to_sql()
        self.assertNotIn("where", sql)
        self.assertEqual(vals, [1])

    def test_with_returning(self):
        stmt = Update(
            table='"t"',
            set_clause=[('"x" = %s', 1)],
            returning=Returning(["x"]),
        )
        sql, _ = stmt.to_sql()
        self.assertIn("returning x", sql)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

class TestDelete(unittest.TestCase):
    def test_simple(self):
        stmt = Delete(
            table='"public"."person"',
            where=And([FieldExpr('"id"', "=", "%s", 42)]),
        )
        sql, vals = stmt.to_sql()
        self.assertEqual(sql, 'delete from "public"."person" where "id" = %s')
        self.assertEqual(vals, [42])

    def test_delete_all(self):
        stmt = Delete(table='"public"."person"')
        sql, vals = stmt.to_sql()
        self.assertEqual(sql, 'delete from "public"."person"')
        self.assertEqual(vals, [])

    def test_with_fk_where(self):
        stmt = Delete(
            table='"t"',
            where=And([FieldExpr('"id"', "=", "%s", 1)]),
            fk_where='("fk") in (%s)',
            fk_values=[2],
        )
        sql, vals = stmt.to_sql()
        self.assertIn('"id" = %s', sql)
        self.assertIn('("fk") in (%s)', sql)
        self.assertEqual(vals, [1, 2])

    def test_with_returning(self):
        stmt = Delete(
            table='"t"',
            where=And([FieldExpr('"id"', "=", "%s", 1)]),
            returning=Returning(["*"]),
        )
        sql, _ = stmt.to_sql()
        self.assertIn("returning *", sql)


# ---------------------------------------------------------------------------
# Integration-style: compose a realistic query
# ---------------------------------------------------------------------------

class TestRealisticComposition(unittest.TestCase):
    def test_select_with_join_and_set_op(self):
        """Simulates: Person(name='A') | Person(name='B') with a joined Post."""
        where = Group(SetOp(
            Group(And([FieldExpr('r1."name"', "=", "%s::text", "A")])),
            "or",
            Group(And([FieldExpr('r1."name"', "=", "%s::text", "B")])),
        ))
        j = Join(
            '"public"."post" as r2',
            '(r2."author_id" = r1."id")',
            where=FieldExpr('r2."published"', "=", "%s::bool", True),
        )
        stmt = Select(
            columns=["r1.*"],
            from_table='"public"."person" as r1',
            joins=[j],
            where=where,
            order_by="r1.name",
            limit=50,
        )
        sql, vals = stmt.to_sql()
        # Structure checks
        self.assertIn("select", sql)
        self.assertIn("join", sql)
        self.assertIn("where", sql)
        self.assertIn("order by r1.name", sql)
        self.assertIn("limit 50", sql)
        # Values ordering: join values first, then where values
        self.assertEqual(vals, [True, "A", "B"])

    def test_negated_set_op(self):
        """Simulates: -(Person(name='A') & Person(age=30))"""
        inner = Group(SetOp(
            Group(And([FieldExpr('r1."name"', "=", "%s", "A")])),
            "and",
            Group(And([FieldExpr('r1."age"', "=", "%s", 30)])),
        ))
        where = Not(inner)
        stmt = Select(
            columns=["r1.*"],
            from_table='"public"."person" as r1',
            where=where,
        )
        sql, vals = stmt.to_sql()
        self.assertIn("not (", sql)
        self.assertEqual(vals, ["A", 30])


if __name__ == "__main__":
    unittest.main()
