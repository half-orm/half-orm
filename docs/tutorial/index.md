# halfORM Tutorial

Welcome to the comprehensive halfORM tutorial! This step-by-step guide will take you from installation to advanced usage patterns.

!!! tip "Before You Start"
    This tutorial assumes basic familiarity with:
    
    - **Python** (classes, decorators, basic OOP)
    - **SQL** (SELECT, INSERT, UPDATE, DELETE, basic joins)
    - **PostgreSQL** (connecting to a database, basic administration)
    
    If you're completely new to halfORM, start with the [Quick Start Guide](../quick-start.md) first!

## What You'll Learn

By the end of this tutorial, you'll be able to:

- ✅ **Install and configure** halfORM for your projects
- ✅ **Connect to databases** and work with existing schemas
- ✅ **Perform CRUD operations** with intuitive Python syntax
- ✅ **Navigate relationships** between tables efficiently
- ✅ **Create custom relation classes** with business logic
- ✅ **Write complex queries** with halfORM's powerful syntax
- ✅ **Handle transactions** safely for complex operations
- ✅ **Debug and optimize** your database interactions

## Tutorial Structure

### Part 1: Getting Started
| Chapter | Topic | Duration | Description |
|---------|-------|----------|-------------|
| **[1. Installation](installation.md)** | Setup & Config | 10 min | Install halfORM and configure database connections |
| **[2. First Steps](first-steps.md)** | Basic Usage | 15 min | Connect to databases, explore tables, basic CRUD |

### Part 2: Core Concepts  
| Chapter | Topic | Duration | Description |
|---------|-------|----------|-------------|
| **[3. Models & Relations](models-relations.md)** | Classes & Schemas | 20 min | Understanding relation classes, custom classes with `@register` |
| **[4. Foreign Keys](foreign-keys.md)** | Relationships | 25 min | Navigation, Fkeys configuration, relationship patterns |

### Part 3: Advanced Usage
| Chapter | Topic | Duration | Description |
|---------|-------|----------|-------------|
| **[5. Queries](queries.md)** | Advanced Querying | 30 min | Complex filters, joins, aggregations, performance |
| **[6. Transactions](transactions.md)** | Data Integrity | 20 min | Transaction decorators, error handling, rollbacks |

**Total estimated time: ~2 hours**

## Tutorial Database

Throughout this tutorial, we'll use a **blog application** schema that includes:

```sql
-- Authors table
CREATE TABLE blog.author (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    bio TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Posts table  
CREATE TABLE blog.post (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    author_id INTEGER REFERENCES blog.author(id) ON DELETE CASCADE,
    published_at TIMESTAMP,
    is_published BOOLEAN DEFAULT FALSE,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Comments table
CREATE TABLE blog.comment (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INTEGER REFERENCES blog.author(id) ON DELETE CASCADE,
    post_id INTEGER REFERENCES blog.post(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Tutorial Database Setup

We provide a complete setup script in [Chapter 1: Installation](installation.md#database-configuration-optional) that creates:

- **Sample schema** with the tables above
- **Test data** for realistic examples
- **Indexes** for performance
- **Views** for advanced examples

## Learning Path Recommendations

### 🚀 **I'm new to ORMs**
Start with **Chapter 1** and follow sequentially. Take time with each concept before moving on.

### 🔥 **I know other ORMs (Django, SQLAlchemy)**  
You can skim **Chapters 1-2** and focus on **Chapters 3-4** to understand halfORM's unique approach.

### ⚡ **I just need specific topics**
Jump directly to the relevant chapter - each chapter includes necessary context.

## Getting Help

Throughout the tutorial:

- 💡 **Tips** highlight best practices
- ⚠️ **Warnings** point out common pitfalls  
- 🔍 **Examples** show real-world usage
- 🏆 **Challenges** let you practice concepts

If you get stuck:

- Check the [Fundamentals](../fundamentals.md) if you haven't already
- Browse [Examples](../examples/index.md) for patterns
- Ask in [GitHub Discussions](https://github.com/half-orm/half-orm/discussions)

## Tutorial Philosophy

This tutorial follows halfORM's core principles:

1. **Database-First**: We work with existing schemas, not code-generated ones
2. **SQL Transparency**: You'll see exactly what SQL is generated
3. **PostgreSQL Native**: We leverage PostgreSQL's unique features
4. **Practical Focus**: Every example is based on real-world scenarios

---

**Ready to start?** Let's begin with [Chapter 1: Installation](installation.md)!

!!! note "Tutorial Feedback"
    This tutorial is actively maintained. If you find errors, have suggestions, or want to contribute examples, please [open an issue](https://github.com/half-orm/half-orm/issues) or [start a discussion](https://github.com/half-orm/half-orm/discussions).