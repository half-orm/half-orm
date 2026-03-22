# halfORM Documentation

[![PyPI version](https://img.shields.io/pypi/v/half_orm)](https://pypi.org/project/half-orm/)
[![Python versions](https://img.shields.io/badge/Python-%20≥%203.7-blue)](https://www.python.org)
[![PostgreSQL versions](https://img.shields.io/badge/PostgreSQL-%20≥%209.6-blue)](https://www.postgresql.org)
[![License](https://img.shields.io/pypi/l/half_orm?color=green)](https://pypi.org/project/half-orm/)
[![Tests](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml/badge.svg)](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml)

**The PostgreSQL-native ORM with unified tooling**

> halfORM lets you keep your database schema in SQL where it belongs, while giving you the comfort of Python for data manipulation. With the new unified CLI, manage everything from database inspection to full-stack development through a single command.

## Overview

halfORM is a lightweight, database-first Object-Relational Mapper designed specifically for PostgreSQL. Unlike traditional ORMs that impose their own schema management, halfORM adapts to your existing database structure, making it perfect for teams that prefer SQL-first development.

**Why halfORM?**

- **🎯 Database-First**: Your PostgreSQL schema is the source of truth
- **🔍 SQL Transparency**: See exactly what queries are generated
- **⚡ Zero Setup**: Connect to existing databases instantly
- **🚀 PostgreSQL Native**: Leverage advanced PostgreSQL features
- **🛠️ Unified CLI**: One command for all halfORM functionality

## What's New in 0.16

### 🎉 **Unified Command-Line Interface**

All halfORM functionality is now accessible through a single `half_orm` command:

```bash
# Core database inspection
half_orm inspect my_database
half_orm inspect my_database public.users

# Extension system with auto-discovery
half_orm --list-extensions

# Test the extension architecture
pip install git+https://github.com/half-orm/half-orm-test-extension
half_orm test-extension greet
```

### 🔌 **Extensible Architecture**

Extensions are automatically discovered and integrated:

```bash
# Install test extension
pip install git+https://github.com/half-orm/half-orm-test-extension

# Commands become available immediately
half_orm --list-extensions  # Shows installed extensions
half_orm test-extension greet  # Use extension commands
```

### 🔍 **Enhanced Database Inspection**

```bash
# List all database relations
half_orm inspect blog_db
#📂 Schema: public
#  📋 posts
#  📋 authors
#  📋 comments
#
#📂 Schema: analytics  
#  👁️ user_stats
#  📋 daily_reports

# Detailed relation inspection
half_orm inspect blog_db public.posts
# Shows table structure, constraints, and relationships
```

## Key Features

### 🔥 **Instant Database Access**
```python
from half_orm.model import Model

# Connect to your existing database
blog = Model('blog_db')

# Work with your tables immediately
Post = blog.get_relation_class('blog.post')
Author = blog.get_relation_class('blog.author')
```

### 🎨 **Custom Relation Classes**
```python
from half_orm.model import register
from half_orm.relation import singleton

@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {
        'author_fk': 'post_author_id_fkey'
    }

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_post_author_id'
    }
    
    @singleton
    def create_post(self, title, content):
        return self.posts_rfk(title=title, content=content).ho_insert()

# Foreign keys now return your custom classes!
post = Post(title='Welcome')
author = post.author_fk()  # Returns Author instance
author.create_post("New Post", "Content")  # Custom method available
```

### 🔍 **Intuitive Querying**
```python
# The object IS the filter - no .filter() needed
young_people = Person(birth_date=('>', '1990-01-01'))
gmail_users = Person(email=('ilike', '%@gmail.com'))

# Navigate relationships while filtering
alice_posts = Author(name=('ilike', 'alice%')).posts_rfk(is_published=True)

# Chain operations naturally
recent_posts = (Post(is_published=True)
    .ho_order_by('created_at desc')
    .ho_limit(10))
```

### 🔧 **PostgreSQL Native Features**
```python
# Use views, functions, and procedures
UserStats = blog.get_relation_class('analytics.user_stats')  # Database view
results = blog.execute_function('calculate_metrics', user_id=123)

# Advanced PostgreSQL data types work seamlessly
JsonData = blog.get_relation_class('app.json_table')
data = JsonData(metadata='{"type": "user", "premium": true}')  # JSONB support
```

## Quick Start

Get up and running in under 5 minutes:

1. **Install halfORM**
   ```bash
   pip install half_orm
   ```

2. **Test your installation**
   ```bash
   half_orm version
   # halfORM Core: 0.16.x
   # No extensions installed
   ```

3. **Configure connection**
   ```bash
   mkdir ~/.half_orm
   echo "[database]
   name = my_database
   user = username
   password = password
   host = localhost" > ~/.half_orm/my_database
   ```

4. **Explore your database**
   ```bash
   half_orm inspect my_database
   ```

5. **Start coding**
   ```python
   from half_orm.model import Model
   
   db = Model('my_database')
   Person = db.get_relation_class('public.person')
   
   # Create
   person = Person(name='Alice', email='alice@example.com')
   result = person.ho_insert()
   
   # Query
   for person in Person(email=('ilike', '%@gmail.com')):
       print(f"Found: {person['name']}")
   ```

**[👉 Full Quick Start Guide →](quick-start.md)**

## halfORM Ecosystem

### 🔌 **Current Extensions**

#### half-orm-test-extension
Demonstration extension for testing the architecture:

```bash
pip install git+https://github.com/half-orm/half-orm-test-extension
half_orm test-extension greet     # Hello, halfORM!
half_orm test-extension status    # Extension status
```

### 🚀 **Planned Extensions**

The following extensions are in development or planned:

- **half-orm-dev** - Development tools (based on [halfORM_dev](https://github.com/half-orm/halfORM_dev))
- **half-orm-api** - REST API generation 
- **half-orm-admin** - Admin interface generation
- **half-orm-monitoring** - Observability and monitoring tools

**[🔌 Browse Extension Ecosystem →](ecosystem/index.md)**

## Documentation Sections

<div class="grid cards" markdown>

-   🚀 **Quick Start**

    ---

    Get up and running with halfORM in minutes. Connect to your database and start working with your data immediately.

    **[Get Started →](quick-start.md)**

-   🧩 **Fundamentals**

    ---

    Core concepts that underpin halfORM's design and behavior. Essential reading for understanding the philosophy and patterns.

    **[Master the Basics →](fundamentals.md)**

-   📚 **Tutorial**

    ---

    Step-by-step guide covering all halfORM concepts from basic CRUD operations to advanced relationship navigation.

    **[Learn halfORM →](tutorial/index.md)**

-   📋 **API Reference**

    ---

    Complete documentation of all halfORM classes, methods, and functions with detailed examples.

    **[API Docs →](api/index.md)**

-   💡 **Examples**

    ---

    Real-world examples and patterns for common use cases like web applications, data analysis, and more.

    **[View Examples →](examples/index.md)**

-   📖 **Guides** 🚧

    ---

    In-depth guides on configuration, performance optimization, testing, and migrating from other ORMs.

    **[Browse Guides →](guides/index.md)**

-   🏗️ **Architecture** 🚧

    ---

    Understanding halfORM's internals, design principles, and how it works under the hood.

    **[Deep Dive →](architecture/index.md)**

-   🔌 **Ecosystem**

    ---

    Extensions, development tools, and the broader halfORM ecosystem for full-stack development.

    **[Explore Ecosystem →](ecosystem/index.md)**

</div>

## Why Choose halfORM?

### ✅ Perfect For

- **PostgreSQL-centric applications** - Leverage PostgreSQL's full power
- **Existing database projects** - Work with established schemas
- **SQL-comfortable teams** - Keep complex logic in the database
- **Rapid prototyping** - Get started instantly with unified tooling
- **Microservices** - Lightweight with no framework baggage
- **Full-stack development** - CLI extensions for complete workflows

### 🤔 Consider Alternatives If

- **Multi-database support needed** - halfORM is PostgreSQL-only
- **Django ecosystem** - Django ORM may integrate better
- **Code-first approach preferred** - You want to define models in Python
- **Heavy ORM features required** - Need lazy loading, identity maps, etc.

## Community & Support

- **[GitHub Repository](https://github.com/half-orm/half-orm)** - Source code and issue tracking
- **[Discussions](https://github.com/half-orm/half-orm/discussions)** - Community Q&A and ideas
- **[PyPI Package](https://pypi.org/project/half-orm/)** - Official releases

## Version History

### Version 0.16.x 🎉

!!! success "Current Development - New CLI Architecture"
    Major architectural update with unified command-line interface and extension system.

- **🛠️ Unified CLI**: All halfORM functionality through `half_orm` command
- **🔌 Extension System**: Automatic discovery and integration of extensions
- **🔍 Enhanced Inspection**: Improved database exploration with `half_orm inspect`
- **📦 Modular Architecture**: Core functionality separated from development tools
- **🎨 Better Developer Experience**: Consistent command patterns across all extensions

```bash
# New unified interface
half_orm inspect my_database
half_orm --list-extensions         # See all available tools
half_orm test-extension greet      # Use extension commands
```

### Version 0.15.0 🎉

!!! info "Previous Release - Custom Relation Classes"
    Major update with new custom relation classes and breaking changes.

- **🎨 New `@register` decorator** for custom relation classes with business logic
- **🔗 Enhanced foreign key navigation** with custom class resolution  
- **📚 Complete documentation rewrite** with improved structure
- **⚠️ Breaking change**: HOP packager moved to separate `halfORM_dev` package

### Migration from 0.15.x

!!! tip "Easy Migration"
    halfORM 0.16 is backward compatible with 0.15.x code. Only CLI usage changes:

    ```bash
    # Old approach (still works)
    python -m half_orm inspect my_database
    
    # New unified approach
    half_orm inspect my_database
    
    # Development tools will require separate package
    pip install half-orm-dev  # When available
    ```

---

!!! tip "Ready to start?"
    Jump into the [Quick Start Guide](quick-start.md) or explore the [Tutorial](tutorial/index.md) for a comprehensive introduction to halfORM.

**Made with ❤️ for PostgreSQL and Python developers**