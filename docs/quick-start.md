# Quick Start Guide

Get up and running with halfORM in under 5 minutes. This guide will take you from installation to your first successful database operation.

!!! tip "Prerequisites"
    - Python 3.7 or higher
    - PostgreSQL 9.6 or higher
    - Basic familiarity with Python and SQL

## Step 1: Installation

Install halfORM using pip:

```bash
pip install half_orm
```

Verify installation with the new unified CLI:

```bash
half_orm version
```

Expected output:
```
halfORM Core: 0.16.0

No extensions installed
```

!!! info "Virtual Environment Recommended"
    For project isolation:
    ```bash
    python -m venv halfORM-env
    source halfORM-env/bin/activate  # Linux/Mac
    # or halfORM-env\Scripts\activate  # Windows
    pip install half_orm
    ```

## Step 2: Database Setup

For this guide, we'll create a simple blog database. If you already have a PostgreSQL database, skip to [Step 3](#step-3-explore-your-database).

### Create Example Database

```sql
-- Connect to PostgreSQL
CREATE DATABASE halfORM_quickstart;

-- Connect to the new database
\c halfORM_quickstart

-- Create schema
CREATE SCHEMA blog;

-- Create tables
CREATE TABLE blog.author (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE blog.post (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    author_id INTEGER REFERENCES blog.author(id),
    published_at TIMESTAMP DEFAULT NOW(),
    is_published BOOLEAN DEFAULT FALSE
);

-- Add sample data
INSERT INTO blog.author (name, email) VALUES 
    ('Alice Johnson', 'alice@example.com'),
    ('Bob Smith', 'bob@example.com');

INSERT INTO blog.post (title, content, author_id, is_published) VALUES 
    ('Welcome to halfORM', 'This is our first post!', 1, true),
    ('Database-First Development', 'Schema-first approach...', 1, true),
    ('Draft Post', 'Work in progress.', 2, false);

-- Create a simple view
CREATE VIEW blog.author_stats AS
SELECT 
    a.id,
    a.name,
    a.email,
    COUNT(p.id) as post_count
FROM blog.author a
LEFT JOIN blog.post p ON a.id = p.author_id
GROUP BY a.id, a.name, a.email;
```

## Step 3: Explore Your Database

Use the new unified CLI to explore your database:

```bash
# Inspect database structure
half_orm inspect halfORM_quickstart

# Detailed table inspection
half_orm inspect halfORM_quickstart blog.author
half_orm inspect halfORM_quickstart blog.post
```

Expected output:
```
📂 Schema: blog
  📋 author
  👁️ author_stats
  📋 post

Total: 3 relations
   📋: 2 tables
   👁️: 1 view
```

## Step 4: Configuration (Optional)

For local development with peer authentication, no configuration is needed. For specific connections:

```bash
# Create config directory
mkdir ~/.half_orm

# Create connection file
cat > ~/.half_orm/halfORM_quickstart << EOF
[database]
name = halfORM_quickstart
user = your_username
password = your_password
host = localhost
port = 5432
EOF
```

## Step 5: First Connection

```python
from half_orm.model import Model

# Connect to database
blog = Model('halfORM_quickstart')

# Show database structure
print(blog)
```

Expected output:
```
📋 Available relations:
r "blog"."author"
r "blog"."post"
v "blog"."author_stats"
```

## Step 6: Create Your First Classes

```python
from half_orm.model import Model

blog = Model('halfORM_quickstart')

# Create relation classes
Author = blog.get_relation_class('blog.author')
Post = blog.get_relation_class('blog.post')
AuthorStats = blog.get_relation_class('blog.author_stats')  # View

# Explore structure
print(Author())  # Shows complete table info
```

This displays columns, types, constraints, and foreign keys.

## Step 7: Basic Operations

### Create
```python
# Create new author
new_author = Author(
    name='Charlie Brown',
    email='charlie@example.com'
)

if new_author.ho_is_empty():
    result = new_author.ho_insert()
    print(f"Created: {result}")
```

### Read
```python
# Read all authors
for author in Author().ho_select('name', 'email'):
    print(f"{author['name']} ({author['email']})")

# Find specific author
alice = Author(name='Alice Johnson').ho_get()
print(f"Found: {alice.name}")
```

### Update
```python
# Update author
Author(id=42).ho_assert_is_singleton().ho_update(
    email='charlie.brown@newdomain.com'
)
```

### Delete
```python
# Delete author
Author(id=42).ho_assert_is_singleton().ho_delete()
```

## Step 8: Working with Relationships

```python
from half_orm.model import register

# Define custom classes with clean foreign key aliases
@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts': '_reverse_fkey_halfORM_quickstart_blog_post_author_id'
    }

@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {
        'author': 'post_author_id_fkey'
    }

# Navigate relationships with clean syntax
alice = Author(name='Alice Johnson').ho_get()
alice_posts = alice.posts()
print(f"Alice has {alice_posts.ho_count()} posts")

# Get author from post - work with the relation
post = Post(id=1)
for author in post.author():
    print(f"Author: {author['name']}")
```
```

!!! tip "Why @register?"
    `@register` makes your custom classes the default everywhere. Foreign key navigation automatically returns YOUR classes with clean `Fkeys` aliases instead of long constraint names.

## Step 9: Query and Filter

```python
# Basic filtering
published_posts = Post(is_published=True)

# Pattern matching
gmail_authors = Author(email=('ilike', '%@gmail.com'))

# Comparison operators
recent_posts = Post(published_at=('>', '2024-01-01'))

# Chaining operations
query = (Post(is_published=True)
         .ho_order_by('published_at DESC')
         .ho_limit(5))

for post in query.ho_select('title', 'published_at'):
    print(f"{post['title']} - {post['published_at']}")

# Working with views
for stats in AuthorStats().ho_select('name', 'post_count'):
    print(f"{stats['name']}: {stats['post_count']} posts")
```

## Key Concepts

### NULL vs None
```python
from half_orm.null import NULL

# ❌ Wrong - ignores field
Author(email=None)

# ✅ Correct - filters NULL values
Author(email=NULL)
```

### Builder vs Executor Pattern
```python
# ✅ Build query first
query = Post(is_published=True).ho_order_by('title')

# ✅ Then execute
results = query.ho_select('title')

# ❌ Cannot chain after execution
# results.ho_order_by('date')  # Error!
```

## Extensions (Test Example)

halfORM 0.16 introduces an extensible architecture. Try it with the test extension:

```bash
# Install test extension
pip install git+https://github.com/half-orm/half-orm-test-extension

# List available extensions
half_orm --list-extensions

# Use the test extension
half_orm test-extension greet
half_orm test-extension status
```

Expected output:
```
Available extensions:
  • test-extension v0.1.0
    Simple test extension for halfORM ecosystem
    Commands: greet, status

🔍 halfORM Test Extension Status
===================================
Extension name: test-extension
Version: 0.1.0
Description: Simple test extension for halfORM ecosystem

Hello, halfORM!
```

### Coming Soon
```bash
# Development tools (in development)
pip install half-orm-dev
half_orm dev new my_project

# API generation (planned)
pip install half-orm-litestar-api
half_orm litestar-api generate
```

## Next Steps

✅ **You're ready!** You can now:
- Connect to any PostgreSQL database
- Perform CRUD operations
- Navigate relationships
- Build filtered queries

### Continue Learning:
- **[Learn halfORM in half an hour](half-an-hour.md)** - Complete walkthrough, in order
- **[Fundamentals](fundamentals.md)** - Core concepts deep dive
- **[Examples](examples/index.md)** - Real-world patterns

### Common Next Questions:
- **Custom classes?** → [Custom classes and business logic](half-an-hour.md#11-custom-classes-and-business-logic-2-min)
- **Complex queries?** → [Predicate algebra](half-an-hour.md#9-predicate-algebra-5-min)
- **Transactions?** → [Transactions](half-an-hour.md#10-transactions-5-min)

## Troubleshooting

### Connection Issues
```python
# Test connection
from half_orm.model import Model
try:
    db = Model('your_database')
    print("✅ Connected!")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Common Fixes
- Check PostgreSQL is running
- Verify database name and credentials
- Ensure user has necessary permissions

!!! question "Need Help?"
    - [GitHub Discussions](https://github.com/half-orm/half-orm/discussions)
    - [GitHub Issues](https://github.com/half-orm/half-orm/issues)

---

**You're now ready to build PostgreSQL applications with halfORM!** 🚀
```