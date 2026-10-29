# Delete Your Repository Layer

Part 4 of six in *Relation-Oriented Programming*. [Series index](index.md)

Here's a question about a blog schema of four tables: `author`, `post`,
`comment`, and `comment_type`, whose DDL is in the
[series index](index.md#the-running-example). *Who are the reviewers of a given post?* A
reviewer is an author who left a comment of type `review` on it.

In any ORM codebase written in the last fifteen years, the answer lives in a
service or a repository, and it looks like this:

```python
class PostService:
    def get_reviewers(self, post_id):
        return (session.query(Author)
            .join(Comment, Comment.author_id == Author.id)
            .join(CommentType, Comment.comment_type == CommentType.name)
            .filter(Comment.post_id == post_id,
                    CommentType.name == 'review').all())
```

One method, three tables, every join condition spelled out, and one class that has
to know the internal structure of all three relations at once.

Now the same question in halfORM:

```python
class CommentType(db.get_relation_class('blog.comment_type')):
    Fkeys = {'rfk_comments': ...}

    def reviews(self):
        return CommentType(name='review').rfk_comments()

class Comment(db.get_relation_class('blog.comment')):
    Fkeys = {'fk_comment_type': ..., 'fk_author': ...}

    def reviewers(self):
        return self.fk_comment_type().reviews().fk_author()

class Post(db.get_relation_class('blog.post')):
    Fkeys = {'rfk_comments': ...}

    def reviewers(self):
        return self.rfk_comments().reviewers()
```

Three one-line methods, each on the class of the relation it describes, each
delegating to its neighbour. No join condition appears anywhere. The query
assembles itself as the delegation chain unwinds, and `Post(id=42).reviewers()`
produces a single SQL query with three joins.

I call this **predicate locality**: every business predicate belongs on the
`Relation` subclass of the entity it describes. It is, as far as I can tell, the
most consequential thing about relation-oriented programming that isn't about
queries at all.

## Three properties fall out

**It's set-general.** `Post.reviewers()` works on *any* `Post` predicate. One
post, all published posts, every post by a given author, with no modification:

```python
Post(id=42).reviewers()                       # reviewers of one post
Post(published=True).reviewers()              # reviewers of all published posts
Author(name='Alice').rfk_posts().reviewers()  # reviewers of Alice's posts
```

The service version takes a `post_id`. To ask the second question you either
call it in a loop (and now you have an N+1 problem in your service layer) or you
rewrite it to accept a collection and rewrite the filter to match. The halfORM
version never knew how many posts there were, because the argument was never a
post id. It was a set.

**Knowledge stays where it belongs.** `Post.reviewers()` has no idea what a
review is. It knows it has comments, and it knows comments know about reviewers.
The definition of "review" (the string `'review'`, the fact that it's a row in
`comment_type` at all) lives in `CommentType`, which is the only class that
should know. Rename the type, add a second reviewing type, change the semantics:
you touch `CommentType.reviews()` and nothing else.

That's Parnas's information-hiding criterion, applied with an unusually clean
decomposition rule. Parnas's hard question is always *what should each module
hide?* Here the answer is given to you: each class hides its own slice of the
schema. And the delegation chain is the Law of Demeter applied to relational
navigation: no class knows anything beyond its immediate neighbours in the FK
graph. Cognitive load at each node is bounded by that node's degree.

**Every level is independently testable.** Because each method is anchored to one
relation, you can test it against that relation alone:

```python
from half_orm.testing import (assertConstraintsMatch,
                              assertTablePath, assertSamePredicate)

REVIEW_CONSTRAINT = dict(table='blog.comment_type', field='name', value='review')

class TestCommentType(TestCase):
    def test_reviews(self):
        reviews = CommentType().reviews()
        self.assertIsInstance(reviews, Comment)
        assertConstraintsMatch(reviews, **REVIEW_CONSTRAINT)

class TestComment(TestCase):
    def test_reviewers(self):
        reviewers = Comment().reviewers()
        self.assertIsInstance(reviewers, Author)
        assertConstraintsMatch(reviewers, **REVIEW_CONSTRAINT)
        assertTablePath(reviewers,
            'blog.comment', 'blog.comment_type', 'blog.comment', 'blog.author')

    def test_reviewers_delegates_to_comment_type(self):
        comment = Comment()
        assertSamePredicate(
            comment.reviewers(),
            comment.fk_comment_type().reviews().fk_author())

class TestPost(TestCase):
    def test_reviewers(self):
        reviewers = Post(id=42).reviewers()
        self.assertIsInstance(reviewers, Author)
        assertConstraintsMatch(reviewers, table='blog.post', field='id', value=42)
        assertConstraintsMatch(reviewers, **REVIEW_CONSTRAINT)
```

No SQL is executed. No fixture data is required. These assertions operate on the
*structure of the predicate*: which tables it involves, which constraints it
carries, whether one method really delegates to another.

And look at `REVIEW_CONSTRAINT`. The same constant is asserted at all three
levels. That's not repetition; it's the evidence. `Post.reviewers()` is correct
only because the `comment_type.name = 'review'` constraint introduced three
delegations down survives the whole chain intact. Seeing the identical constant
pass at every level is a direct, readable proof that it does.

The test suite ends up isomorphic to the code, which is isomorphic to the schema.
One class per relation, one test class per relation, each testing only what its
class knows.

## Why the Repository pattern exists at all

Now the uncomfortable bit. Putting query logic on the entity class isn't just
unusual in ORM codebases; it's actively discouraged. Fowler's Repository pattern
and most Domain-Driven Design practice say the opposite: domain objects model
behaviour, repositories own queries, and the boundary between them is
load-bearing architecture.

I think that boundary is, in substantial part, a workaround.

Consider what an ORM entity actually is. It's a proxy tied to a session,
carrying implicit state, with attributes that may or may not be loaded and that
may issue queries when touched. Putting query logic on an object like that is
dangerous: your method's behaviour depends on whether `self` is attached,
detached, or expired; on whether the session is open; on what's already in the
identity map. So the community developed the correct response to that
constraint: move the queries somewhere the constraint doesn't apply. That's the
Repository.

Remove the constraint and the workaround loses its reason to exist.

A halfORM `Relation` subclass is a stateless predicate. There's no session
attachment, no identity, no lazy attribute, no loaded-or-not ambiguity. Calling a
method on it composes a new predicate and returns it. There is no state to be
wrong about, so there is nothing a query method on the class can break.

And the relational model imposes the decomposition criterion, rather than an
architectural convention layered on top of the code: one class per relation, one
predicate per business concept, anchored to the relation that holds it. **The
schema is the decomposition.** You don't choose a module boundary and defend it in
review; the foreign-key graph already drew it.

Which is not nothing, incidentally. "Where should this go?" is one of the most
expensive recurring questions in a codebase, and most architectural patterns are
attempts to answer it in advance. Here the answer is mechanical: which relation
does this predicate constrain? That class.

## It generalises

The blog example is the minimal non-trivial case. The pattern holds for any
acyclic FK graph. For a path R₁ →ᶠ¹ R₂ →ᶠ² ⋯ →ᶠⁿ Rₙ, a predicate defined on R₁
composes predicates on R₂ … Rₙ through n−1 delegating methods, each O(1) in code
written. Depth doesn't hurt you: a five-hop query is five one-line methods, and
each one is readable in isolation because none of them can see past its
neighbours.

Compare that to the service-layer version at five hops, which is a single method
containing five join conditions and knowledge of five tables' internals, and which
has to be rewritten every time any of those five schemas changes.

## The adoption problem

The main thing that goes wrong when experienced developers pick up halfORM is
that they keep the repository.

It's a trained habit. Years of separating mapping artefacts from business
objects teaches you to treat a generated class as infrastructure (plumbing you
shouldn't put domain logic into), and so people generate their model, then build
a service layer on top of it and write the same joins they always wrote. It
works. It just throws away most of the benefit, because now the query logic is
centralised again, it isn't set-general again, and no class owns its own
predicates again.

FK aliases, `@singleton` guards, and domain operations belong *inside* the
`Relation` subclass. half-orm-dev makes this explicit in the generated files
themselves, with a developer zone that the code generator is guaranteed never to
touch, which is the subject of a later post in this series. But the shift is
mental before it's technical, and it's the prerequisite for the rest.

If you take one thing from this essay: the Repository pattern was a correct
response to session-bound entity proxies. If you don't have session-bound entity
proxies, check whether you still need the response.

---

*The testing helpers used here are documented in [Testing](../api/testing.md).*
