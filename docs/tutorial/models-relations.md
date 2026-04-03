# Chapter 3: Models & Relations

In the previous chapter, you learned how to connect to databases and perform basic CRUD operations. Now we'll dive deeper into halfORM's core concepts: Models and custom Relation classes. You'll learn how to add business logic to your data classes and create a more maintainable codebase.

!!! important "Prerequisites"
    This chapter builds on core halfORM concepts. Ensure you're familiar with:
    
    - **[halfORM Fundamentals](../fundamentals.md)** - Essential concepts including Model architecture, schema requirements, and method naming conventions
    - **[Chapter 2: First Steps](first-steps.md)** - Basic CRUD operations and relation class creation
    
    Pay special attention to the [Database-First Strategy](../fundamentals.md#database-first-strategy) and [Schema Requirements](../fundamentals.md#schema-requirements) sections in Fundamentals.

## Chapter Objectives

By the end of this chapter, you'll understand:

- **Custom relation classes** - Creating classes with business logic and clean interfaces
- **The `@register` decorator** - Overriding auto-generated classes with your custom implementations
- **Fkeys configuration** - Clean foreign key aliases for better code readability
- **Class organization** - Best practices for structuring your halfORM code
- **Inheritance patterns** - Working with PostgreSQL table inheritance

## Model Class Deep Dive

!!! info "Model Fundamentals"
    The Model class architecture and responsibilities are covered in detail in [Model Architecture](../fundamentals.md). This section focuses on practical usage patterns.

### Model as a Relation Factory

When you call `get_relation_class()`, the model returns a generated class that inherits from `Relation`. Classes are created once and cached:

```python
from half_orm.model import Model

blog = Model('blog_tutorial')

# Each call returns the same cached class
Author1 = blog.get_relation_class('blog.author')
Author2 = blog.get_relation_class('blog.author')
print(Author1 is Author2)  # → True (same class object)

print(Author1.__name__)  # → 'Table_BlogTutorialBlogAuthor'
print(Author1.__bases__)  # → (<class 'half_orm.relation.Relation'>,)

# You can inspect the generated class
print(Author1())  # Shows complete table structure
```

### Model Metadata Discovery

Models automatically discover and cache database structure:

```python
# Explore what's in your database
print(blog)  # Shows all relations

# Check if a relation exists
if blog.has_relation('blog.author'):
    Author = blog.get_relation_class('blog.author')

# Get detailed metadata
relations = blog.desc()  # List of all relations with inheritance info
```

## Auto-Generated Relation Classes

When you call `get_relation_class()`, halfORM generates a class with all the necessary attributes and methods based on your database schema.

### What Gets Generated Automatically

```python
Author = blog.get_relation_class('blog.author')

# Fields become attributes
author = Author()
print(author.first_name)  # → Field object
print(author.email)       # → Field object

# Foreign keys are available
print(author._ho_fkeys.keys())  # → All available foreign keys

# Metadata is attached
print(author._ho_metadata['description'])  # → Table comment
print(author._ho_pkey)  # → Primary key fields
```

### Working with Auto-Generated Classes

```python
# You can use auto-generated classes directly
Author = blog.get_relation_class('blog.author')
Post = blog.get_relation_class('blog.post')

# Create and manipulate data
alice = Author(
    first_name='Alice', 
    last_name='Johnson', 
    email='alice@example.com'
).ho_insert()

# Navigate relationships using the full foreign key names
alice_posts = alice._ho_fkeys['_reverse_fkey_blog_tutorial_blog_post_author_id']()
print(f"Alice has {alice_posts.ho_count()} posts")
```

**The Problem**: Foreign key names are long and hard to remember. Business logic gets scattered across your application.

## Creating Custom Relation Classes

Custom relation classes let you add business logic, create readable foreign key aliases, and encapsulate domain-specific operations.

### Basic Custom Class Structure

```python
from half_orm.model import Model

blog = Model('blog_tutorial')

class Author(blog.get_relation_class('blog.author')):
    """Custom Author class with business methods"""
    
    # Clean foreign key aliases
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    def get_full_name(self):
        """Return author's full name"""
        return f"{self.first_name.value} {self.last_name.value}"
    
    def get_post_count(self):
        """Get total number of posts by this author"""
        return self.posts_rfk().ho_count()
    
    def create_post(self, title, content):
        """Create a new post for this author"""
        return self.posts_rfk(
            title=title,
            content=content
        ).ho_insert()

# Usage
alice = Author(email='alice@example.com').ho_get()
print(alice.get_full_name())  # → "Alice Johnson"
print(f"Posts: {alice.get_post_count()}")  # → "Posts: 3"

# Clean foreign key access
for post in alice.posts_rfk():
    print(post['title'])
```

### The Fkeys Dictionary

The `Fkeys` dictionary maps friendly names to actual foreign key constraint names:

```python
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        # Alias: Actual constraint name
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }

# Now you can use clean names
author = Author().ho_get()
author.posts_rfk()     # Instead of author._ho_fkeys['_reverse_fkey_...']()
author.comments_rfk()  # Much more readable!
```

!!! tip "Finding Foreign Key Names"
    When you print a relation class (`print(Author())`), halfORM shows you the exact foreign key names to copy into your `Fkeys` dictionary.

### Adding Business Logic

Custom classes are perfect for encapsulating domain logic:

```python
from datetime import datetime, timedelta

class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    def is_active_writer(self, days=30):
        """Check if author has posted recently"""
        cutoff = datetime.now() - timedelta(days=days)
        recent_posts = self.posts_rfk(created_at=('>', cutoff))
        return recent_posts.ho_count() > 0
    
    def get_statistics(self):
        """Get comprehensive author statistics"""
        all_posts = self.posts_rfk()
        published_posts = all_posts(is_published=True)
        
        return {
            'total_posts': all_posts.ho_count(),
            'published_posts': published_posts.ho_count(),
            'draft_posts': all_posts(is_published=False).ho_count(),
            'total_comments': self.comments_rfk().ho_count()
        }
    
    def publish_all_drafts(self):
        """Publish all draft posts for this author"""
        drafts = self.posts_rfk(is_published=False)
        return drafts.ho_update(
            is_published=True,
            published_at=datetime.now()
        )

# Usage
alice = Author(email='alice@example.com').ho_get()

if alice.is_active_writer():
    stats = alice.get_statistics()
    print(f"Alice has {stats['published_posts']} published posts")
    
    # Publish remaining drafts
    if stats['draft_posts'] > 0:
        alice.publish_all_drafts()
        print(f"Published {stats['draft_posts']} draft posts")
```

## The @register Decorator

The `@register` decorator is halfORM's powerful feature that replaces the auto-generated base class with your custom class in the model's class cache. This makes your custom classes the default whenever that relation is accessed, including through foreign key navigation.

### Without @register

```python
# Regular custom class
class Author(blog.get_relation_class('blog.author')):
    def get_full_name(self):
        return f"{self.first_name.value} {self.last_name.value}"

class Post(blog.get_relation_class('blog.post')):
    Fkeys = {'author_fk': 'post_author_id_fkey'}

# Problem: Foreign keys return generic classes
post = Post(title='My Post').ho_get()
author = post.author_fk().ho_get()  # Returns generic Author class
# author.get_full_name()  # ❌ Method doesn't exist!
```

### With @register

```python
from half_orm.model import register

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    def get_full_name(self):
        return f"{self.first_name.value} {self.last_name.value}"
    
    def create_post(self, title, content):
        return self.posts_rfk(title=title, content=content).ho_insert()

@register  
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {'author_fk': 'post_author_id_fkey'}
    
    def get_author_name(self):
        return self.author_fk().ho_get().get_full_name()

# Magic: Foreign keys now return YOUR custom classes!
post = Post(title='My Post').ho_get()
author = post.author_fk().ho_get()  # Returns YOUR Author class!
print(author.get_full_name())       # ✅ Method available!

# Works in both directions
alice = Author(email='alice@example.com').ho_get()
for post in alice.posts_rfk():  # Each post is YOUR Post class
    post_obj = Post(**post)
    print(post_obj.get_author_name())  # Your custom methods work!
```

### How @register Works

When you use `@register`, halfORM:

1. **Replaces the auto-generated class** in the model's class cache with your custom class
2. **Returns your class** whenever that relation is requested via `get_relation_class()`
3. **Uses your class** in foreign key navigation automatically
4. **Preserves your methods** and custom `Fkeys` across all relation access

```python
# Before registration
Author1 = blog.get_relation_class('blog.author')  # Auto-generated class
print(Author1.__name__)  # → 'Table_BlogTutorialBlogAuthor'

# Registration happens at import time
@register
class Author(blog.get_relation_class('blog.author')):
    def get_full_name(self):
        return f"{self.first_name.value} {self.last_name.value}"

# After registration - same call now returns YOUR class
Author2 = blog.get_relation_class('blog.author')  # Returns your Author class
print(Author2 is Author)  # → True (same class object)
```

## Advanced Custom Class Patterns

### Working with the @singleton Decorator

For methods that should work on single records, use the `@singleton` decorator:

```python
from half_orm.model import register
from half_orm.relation import singleton

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    @singleton
    def create_post(self, title, content, published=False):
        """Create a new post for this author."""
        return self.posts_rfk(
            title=title, 
            content=content, 
            is_published=published
        ).ho_insert()
    
    @singleton
    def get_published_posts(self):
        """Get all published posts by this author."""
        return self.posts_rfk(is_published=True)
    
    @singleton
    def get_stats(self):
        """Get author statistics."""
        all_posts = self.posts_rfk()
        published = all_posts(is_published=True)
        return {
            'total_posts': all_posts.ho_count(),
            'published_posts': published.ho_count(),
            'draft_posts': all_posts.ho_count() - published.ho_count()
        }

@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {'author_fk': 'post_author_id_fkey'}
    
    @singleton
    def publish(self):
        """Publish this post."""
        from datetime import datetime
        return self.ho_update(is_published=True, published_at=datetime.now())
    
    @singleton
    def unpublish(self):
        """Unpublish this post."""
        return self.ho_update(is_published=False)
    
    @singleton
    def get_author_name(self):
        """Get the name of this post's author."""
        return self.author_fk().get_full_name()  # No ho_get() needed with @singleton

# Test the custom classes
if __name__ == "__main__":
    # Find Alice - no ho_get() needed with @singleton methods
    alice = Author(name='Alice Johnson')
    
    # Create a post using custom method
    new_post = alice.create_post(
        title="halfORM Custom Classes", 
        content="This post was created using a custom method!",
        published=True
    )
    print(f"✅ Created post: {new_post}")
    
    # Get author statistics
    stats = alice.get_stats()
    print(f"📊 Alice's stats: {stats}")
    
    # Navigate from post to author using custom method
    post = Post(title='Welcome to halfORM')
    author_name = post.get_author_name()
    print(f"📝 '{post.title.value}' was written by: {author_name}")
```

!!! tip "The `@singleton` decorator"
    Use `@singleton` when you need to ensure that the object you are operating on defines a singleton in your relation. This eliminates the need for `.ho_get()` calls in your business methods.

### Complex Business Logic Examples

```python
from datetime import datetime, timedelta
from half_orm.model import register
from half_orm.relation import singleton

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'posts_rfk': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    @singleton
    def get_engagement_score(self, days_back=30):
        """Calculate author engagement score based on recent activity"""
        cutoff = datetime.now() - timedelta(days=days_back)
        
        # Recent posts and comments
        recent_posts = self.posts_rfk(published_at=('>', cutoff), is_published=True)
        recent_comments = self.comments_rfk(created_at=('>', cutoff))
        
        # Calculate metrics
        post_count = recent_posts.ho_count()
        comment_count = recent_comments.ho_count()
        total_views = sum(p['view_count'] for p in recent_posts.ho_select('view_count'))
        
        # Engagement score formula
        return (post_count * 10) + (comment_count * 2) + (total_views * 0.1)
    
    @singleton
    def get_popular_posts(self, min_views=50, limit=5):
        """Get this author's most popular posts"""
        return (self.posts_rfk(is_published=True, view_count=('>=', min_views))
                .ho_order_by('view_count DESC')
                .ho_limit(limit))
    
    @singleton
    def archive_old_drafts(self, days_old=90):
        """Archive drafts older than specified days"""
        cutoff = datetime.now() - timedelta(days=days_old)
        old_drafts = self.posts_rfk(
            is_published=False,
            created_at=('<', cutoff)
        )
        
        archived_count = old_drafts.ho_update(
            title=self.title + ' [ARCHIVED]',
            content='[This draft was automatically archived]'
        )
        
        return archived_count

@register  
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {
        'author_fk': 'post_author_id_fkey',
        'comments_rfk': '_reverse_fkey_blog_tutorial_blog_comment_post_id'
    }
    
    @singleton
    def get_engagement_metrics(self):
        """Get detailed engagement metrics for this post"""
        comments = self.comments_rfk()
        approved_comments = comments(is_approved=True)
        
        # Calculate engagement rate
        views = self.view_count.value or 0
        comment_rate = (approved_comments.ho_count() / views * 100) if views > 0 else 0
        
        return {
            'views': views,
            'total_comments': comments.ho_count(),
            'approved_comments': approved_comments.ho_count(),
            'comment_rate': round(comment_rate, 2)
        }
    
    @singleton
    def moderate_comments(self, approve_all=False):
        """Moderate comments on this post"""
        pending_comments = self.comments_rfk(is_approved=False)
        
        if approve_all:
            return pending_comments.ho_update(is_approved=True)
        else:
            # Return comments for manual review
            return list(pending_comments.ho_select('id', 'content', 'created_at'))
    
    @singleton
    def suggest_tags(self):
        """Suggest tags based on content analysis"""
        content = self.content.value or ""
        title = self.title.value or ""
        
        # Simple keyword-based tag suggestions
        suggestions = []
        text = (content + " " + title).lower()
        
        tag_keywords = {
            'python': ['python', 'django', 'flask', 'pip'],
            'postgresql': ['postgresql', 'postgres', 'sql', 'database'],
            'performance': ['performance', 'optimization', 'speed', 'efficient'],
            'tutorial': ['tutorial', 'guide', 'how-to', 'introduction']
        }
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in text for keyword in keywords):
                suggestions.append(tag)
        
        return suggestions

# Usage examples
if __name__ == "__main__":
    # Author engagement analysis
    alice = Author(email='alice@example.com')
    engagement = alice.get_engagement_score(days_back=30)
    print(f"Alice's 30-day engagement score: {engagement}")
    
    # Popular posts
    popular = alice.get_popular_posts(min_views=100, limit=3)
    print(f"Alice's top posts: {[p['title'] for p in popular.ho_select('title')]}")
    
    # Post analytics
    post = Post(title='Getting Started with halfORM')
    metrics = post.get_engagement_metrics()
    print(f"Post metrics: {metrics}")
    
    # Tag suggestions
    suggestions = post.suggest_tags()
    print(f"Suggested tags: {suggestions}")
```

### Working with PostgreSQL Inheritance

halfORM handles PostgreSQL table inheritance naturally:

```python
# PostgreSQL: CREATE TABLE blog.event (...) INHERITS (blog.post);

@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {'author_fk': 'post_author_id_fkey'}

@register  
class Event(blog.get_relation_class('blog.event')):
    # Inherits all Post functionality + event-specific fields
    Fkeys = {'author_fk': 'event_author_id_fkey'}
    
    @singleton
    def is_upcoming(self):
        from datetime import datetime
        return self.begin.value > datetime.now()
    
    @singleton
    def get_duration(self):
        """Calculate event duration in hours"""
        if self.begin.value and self.end.value:
            delta = self.end.value - self.begin.value
            return delta.total_seconds() / 3600
        return None

# Events are also Posts
event = Event(title='Conference')
print(event.title.value)  # Inherited from Post
print(event.is_upcoming())  # Event-specific method
```

## Best Practices for Custom Classes

### 1. Use @register for Production Code

```python
# ❌ Don't: Manual class usage in production
Author = blog.get_relation_class('blog.author')
author = Author().ho_get()

# ✅ Do: Register your classes for automatic resolution
@register
class Author(blog.get_relation_class('blog.author')):
    pass

# Now all foreign key navigation uses your class automatically
```

### 2. Keep Business Logic in Relation Classes

```python
@register
class Order(blog.get_relation_class('shop.order')):
    Fkeys = {'items_rfk': '_reverse_fkey_shop_order_item_order_id'}
    
    @singleton
    def calculate_total(self):
        """Business logic belongs in the relation class"""
        total = 0
        for item in self.items_rfk():
            total += item['price'] * item['quantity']
        return total
    
    @singleton
    def can_be_cancelled(self):
        """Domain rules encapsulated in the class"""
        return self.status.value in ['pending', 'confirmed']
    
    @singleton  
    def apply_discount(self, percentage):
        """Complex business operations"""
        if not self.can_be_cancelled():
            raise ValueError("Cannot apply discount to processed order")
        
        current_total = self.calculate_total()
        discount_amount = current_total * (percentage / 100)
        
        return self.ho_update(
            discount_amount=discount_amount,
            total_amount=current_total - discount_amount
        )
```

### 3. Use Descriptive Fkey Aliases

```python
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        # ✅ Clear and descriptive
        'posts': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments': '_reverse_fkey_blog_tutorial_blog_comment_author_id',
        'published_posts': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        
        # ❌ Avoid unclear names  
        # 'rfk1': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        # 'data': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    def get_published_posts(self):
        """Use the descriptive alias in business logic"""
        return self.posts(is_published=True)
```

### 4. Organize Your Classes Effectively

```python
# blog_models.py
from half_orm.model import Model, register
from half_orm.relation import singleton
from datetime import datetime, timedelta

blog = Model('blog_tutorial')

@register
class Author(blog.get_relation_class('blog.author')):
    """Authors who write posts and comments"""
    Fkeys = {
        'posts': '_reverse_fkey_blog_tutorial_blog_post_author_id',
        'comments': '_reverse_fkey_blog_tutorial_blog_comment_author_id'
    }
    
    @singleton
    def get_stats(self):
        return {
            'posts': self.posts().ho_count(),
            'published_posts': self.posts(is_published=True).ho_count()
        }

@register  
class Post(blog.get_relation_class('blog.post')):
    """Blog posts with content"""
    Fkeys = {
        'author': 'post_author_id_fkey',
        'comments': '_reverse_fkey_blog_tutorial_blog_comment_post_id'
    }
    
    @singleton
    def publish(self):
        return self.ho_update(
            is_published=True,
            published_at=datetime.now()
        )

# Usage in other modules
from blog_models import Author, Post

alice = Author(email='alice@example.com')
stats = alice.get_stats()
```

### 5. Handle Edge Cases Gracefully

```python
@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {'posts': '_reverse_fkey_blog_tutorial_blog_post_author_id'}
    
    @singleton
    def get_latest_post(self):
        """Get the most recent post, handling case of no posts"""
        latest_posts = (self.posts(is_published=True)
                       .ho_order_by('published_at DESC')
                       .ho_limit(1))
        
        if latest_posts.ho_is_empty():
            return None
        
        return latest_posts.ho_get()
    
    @singleton
    def safe_delete(self):
        """Delete author only if they have no published posts"""
        published_posts = self.posts(is_published=True)
        
        if not published_posts.ho_is_empty():
            raise ValueError(
                f"Cannot delete author with {published_posts.ho_count()} published posts"
            )
        
        # Delete drafts first
        drafts = self.posts(is_published=False)
        drafts.ho_delete()
        
        # Then delete the author
        return self.ho_delete()
```

## Chapter Summary

Congratulations! You've mastered the core concepts of halfORM's Models and Relations architecture. Let's recap what you've learned:

### ✅ Key Concepts Mastered

**Custom Relation Classes**
- Add business logic methods to your data classes
- Use `Fkeys` dictionary for clean foreign key aliases
- Encapsulate domain-specific operations

**The @register Decorator**
- Replaces auto-generated classes with your custom classes
- Makes foreign key navigation return YOUR classes automatically
- Enables clean, maintainable code architecture

**Advanced Patterns**
- `@singleton` decorator for single-record operations
- Complex business logic encapsulation
- PostgreSQL table inheritance support

**Best Practices**
- Organize classes in dedicated modules
- Use descriptive Fkey aliases
- Handle edge cases gracefully
- Keep business logic in relation classes

### 🎯 Skills You Can Now Apply

- Create custom relation classes with sophisticated business methods
- Set up clean foreign key aliases using `Fkeys`
- Use `@register` to make your classes the default across your application
- Organize your halfORM code for maintainability
- Work with PostgreSQL table inheritance
- Handle complex domain logic within your data classes

### 💡 Architecture Benefits You've Gained

- **Automatic class resolution** through foreign key navigation
- **Centralized business logic** in appropriate data classes
- **Clean, readable code** with descriptive method names
- **Type safety** through custom class methods
- **Maintainable codebase** with clear separation of concerns

## What's Next?

Now that you understand Models and Relations, you're ready to master relationship navigation. In the next chapter, [Foreign Keys](foreign-keys.md), you'll learn:

- **Advanced navigation patterns** - Chaining relationships efficiently
- **Complex relationship handling** - Many-to-many, self-references
- **Query optimization** - Reducing database calls across tables
- **Relationship constraints** - Using foreign keys for filtering

The foreign key system is where halfORM really shines, letting you navigate complex database relationships with intuitive Python syntax.

!!! tip "Additional Resources"
    - **[halfORM Fundamentals](../fundamentals.md)** - Core concepts reference
    - **[Model API Reference](../api/model.md)** - Complete Model class documentation
    - **[Relation API Reference](../api/relation.md)** - All Relation methods and properties  
    - **[Examples](../examples/index.md)** - Real-world usage patterns

---

**Ready to master relationships?** Continue to [Chapter 4: Foreign Keys](foreign-keys.md)!