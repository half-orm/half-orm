# Chapter 5: Queries

In previous chapters, you learned halfORM basics and how to create custom classes. Now we'll explore halfORM's powerful querying capabilities. You'll learn how to build complex queries, optimize performance, and handle advanced relationship navigation.

!!! important "Prerequisites"
    This chapter assumes you understand halfORM's core concepts. If you haven't already, please read:
    
    - **[halfORM Fundamentals](../fundamentals.md)** - Essential concepts like object-as-filter, declarative programming, and set operations
    - **[Tutorial Chapter 2: First Steps](first-steps.md)** - Basic CRUD operations
    - **[Tutorial Chapter 3: Models & Relations](models-relations.md)** - Custom classes and the `@register` decorator

## Chapter Objectives

By the end of this chapter, you'll master:

- **Complex filtering patterns** - Advanced operators and multi-condition queries  
- **Query optimization** - Minimizing database calls and improving performance
- **Advanced ordering and limiting** - Sophisticated result control
- **Subquery patterns** - Using halfORM queries within other queries
- **Performance debugging** - Using `ho_mogrify()` and query analysis
- **Database-first solutions** - When to use views and functions instead of complex Python code

## Advanced Filtering Patterns

Building on the [fundamental filtering concepts](../fundamentals.md#object-as-filter-pattern), let's explore more sophisticated querying patterns.

### Complex Multi-Condition Queries

```python
from half_orm.model import Model

blog = Model('blog_tutorial')
Author = blog.get_relation_class('blog.author')
Post = blog.get_relation_class('blog.post')

# Multiple conditions (AND by default)
experienced_authors = Author(
    is_active=True,
    birth_date=('<', '1990-01-01'),
    email=('not ilike', '%test%')
)

# Date ranges using set operations
this_year_posts = (Post(published_at=('>=', '2024-01-01')) & 
                   Post(published_at=('<=', '2024-12-31')) &
                   Post(is_published=True))

# Pattern matching with exclusions
quality_posts = Post(
    title=('not ilike', '%draft%'),
    content=('~', r'\w{100,}'),  # At least 100 word characters
    view_count=('>', 10)
)
```

### Advanced Set Operations

Remember that [Relations are Python sets](../fundamentals.md#relations-as-python-sets), so you can combine them with boolean logic:

```python
# Complex boolean combinations
prolific_authors = Author().posts_rfk(ho_count=('>', 5))  # Authors with 5+ posts
popular_authors = Author().posts_rfk(view_count=('>', 100))  # Authors of popular posts
gmail_authors = Author(email=('ilike', '%@gmail.com'))

# Find popular Gmail authors who are prolific
featured = (popular_authors & gmail_authors & prolific_authors)

# Find authors who write but don't use Gmail
non_gmail_writers = prolific_authors - gmail_authors

# Complex exclusions
active_non_test = (Author(is_active=True) - 
                  Author(email=('ilike', '%test%')) - 
                  Author(email=('ilike', '%example%')))
```

### Regular Expression Patterns

PostgreSQL's powerful regex support is available through halfORM:

```python
# POSIX regular expressions
valid_slugs = Post(slug=('~', r'^[a-z0-9-]+$'))  # Valid URL slugs
phone_authors = Author(bio=('~*', r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'))  # Contains phone

# Complex content analysis
structured_posts = Post(
    content=('~', r'##\s+.+'),  # Contains markdown headers
    content=('~', r'```\w+'),   # Contains code blocks
    is_published=True
)
```

### Working with NULL Values

```python
from half_orm.null import NULL

# Authors with complete profiles
complete_authors = Author(
    bio=('is not', NULL),
    birth_date=('is not', NULL)
)

# Posts without excerpts
posts_needing_excerpts = Post(
    excerpt=('is', NULL),
    is_published=True
)

# NULL comparisons
recent_or_null = Post(
    published_at=('>', '2024-01-01') | Post(published_at=('is', NULL))
)
```

## Advanced Query Operations

### Understanding Query Execution

Before diving into advanced patterns, it's crucial to understand when SQL actually executes:

```python
# ❌ COMMON MISTAKE: Trying to modify after execution
def get_sorted_authors_wrong():
    authors = Author().ho_select('name', 'email')  # SQL executes - returns generator
    return authors.ho_order_by('name')  # ❌ ERROR! Cannot modify generator

# ✅ CORRECT: Build complete query first
def get_sorted_authors_right():
    authors = Author().ho_order_by('name')  # Builds query - no SQL yet
    return authors.ho_select('name', 'email')  # SQL executes with ORDER BY
```

!!! warning "Execution vs Building"
    **Query Builders**: `ho_order_by()`, `ho_limit()`, `ho_offset()`, `ho_where()`, set operations (`&`, `|`, `-`)
    
    **Query Executors**: `ho_select()`, `ho_count()`, `ho_is_empty()`, `ho_insert()`, `ho_update()`, `ho_delete()`
    
    Once you call an executor, you get results - not a query object!

!!! info "Learn More"
    For a complete explanation of halfORM's query execution model, see [Method Categories in Fundamentals](../fundamentals.md#method-categories-builders-vs-executors).

### Dynamic Ordering

```python
# Dynamic sort direction
def get_posts(sort_by='created_at', direction='DESC'):
    sort_clause = f"{sort_by} {direction}"
    return Post(is_published=True).ho_order_by(sort_clause)

# Multiple column ordering with priorities
top_posts = (Post(is_published=True)
            .ho_order_by('view_count DESC, published_at DESC, title ASC'))

# Conditional ordering
def get_author_posts(author_id, sort_recent_first=True):
    posts = Post(author_id=author_id, is_published=True)
    if sort_recent_first:
        return posts.ho_order_by('published_at DESC')
    else:
        return posts.ho_order_by('title ASC')
```

### Pagination Patterns

```python
def get_paginated_posts(page=1, per_page=10):
    """Get paginated posts with metadata"""
    offset = (page - 1) * per_page
    
    posts_query = Post(is_published=True).ho_order_by('published_at DESC')
    
    # Get total count for pagination metadata
    total_posts = posts_query.ho_count()
    
    # Get page data
    posts = posts_query.ho_limit(per_page).ho_offset(offset)
    
    return {
        'posts': list(posts.ho_select('title', 'published_at', 'view_count')),
        'page': page,
        'per_page': per_page,
        'total': total_posts,
        'pages': (total_posts + per_page - 1) // per_page  # Ceiling division
    }

# Usage
page_data = get_paginated_posts(page=2, per_page=5)
print(f"Page {page_data['page']} of {page_data['pages']}")
for post in page_data['posts']:
    print(f"- {post['title']}")
```

### Efficient Field Selection Strategies

```python
# Minimal field selection for lists
def get_post_index(limit=None, offset=None):
    """Get a generator of lightweight post list for index pages"""
    return Post(is_published=True).ho_select(
        'id', 'title', 'excerpt', 'published_at', 'view_count',
        limit=limit,
        offset=offset,
        order_by='published_at DESC'
    )   

# Full selection for detail views
def get_post_detail(post_id):
    """Get a dict of complete post data for detail view"""
    return list(Post(id=post_id))[0]  # All columns

# Custom field combinations
def get_author_summary():
    """Get a generator of author data optimized for summary cards"""
    return Author(is_active=True).ho_select(
        'id', 'first_name', 'last_name', 'email'
    )
```

## Relationship Navigation in Queries

### Chaining Relationships with Filters

```python
# Find comments by active authors on popular posts
popular_post_comments = (Post(view_count=('>', 100))
                        .comments_rfk(is_approved=True)
                        .author_fk(is_active=True))

# Authors who comment on their own posts
self_commenters = (Author(is_active=True)
                  .posts_rfk(is_published=True)
                  .comments_rfk()
                  .author_fk())  # This should match the original author

# Multi-level navigation with conditions
trending_author_latest_posts = (Post(view_count=('>', 50))
                               .author_fk(is_active=True)
                               .posts_rfk(published_at=('>', '2024-06-01')))
```

### Relationship Existence Queries

```python
# Authors who have posts
authors_with_posts = Author().posts_rfk()

# Authors who have never posted
authors_without_posts = Author() - Author().posts_rfk()

# Authors with approved comments
authors_with_approved_comments = Author().comments_rfk(is_approved=True)

# Posts with no comments
posts_without_comments = Post(is_published=True) - Post().comments_rfk()
```

## Performance Optimization

### Query Analysis and Debugging

Use `ho_mogrify()` to understand query performance:

```python
# Analyze complex queries
complex_query = (Author(is_active=True)
                .posts_rfk(is_published=True, view_count=('>', 50))
                .ho_order_by('published_at DESC')
                .ho_limit(10))

# See the generated SQL
print("=== Generated SQL ===")
complex_query.ho_mogrify()

# Execute and time the query
import time
start = time.time()
results = list(complex_query.ho_select('title', 'view_count'))
end = time.time()
print(f"Query executed in {end - start:.3f} seconds")
```

### SQL Trace Mode

For comprehensive debugging during development and testing, you can enable SQL trace mode to automatically display all executed queries along with their caller context:

```python
from half_orm.model import Model

blog = Model('halftest')

# Enable SQL trace mode
blog.sql_trace = True

# Now all queries will show:
# 1. Where they were called from (file, line, function)
# 2. The actual SQL query executed

Person = blog.get_relation_class('actor.person')
Post = blog.get_relation_class('blog.post')

# This will automatically print trace information
person = Person(last_name='aa')
results = list(person)
```

**Output:**
```
SQL TRACE:
  File: tmp/test_sql_trace.py:17
  Function: <module>
  Code: results = list(person)
select
  r136347531037616.*
from
   "actor"."person" as r136347531037616
  
where
    (r136347531037616."last_name" = 'aa'::text)
```

**Benefits:**
- Automatically tracks all SQL queries without manual instrumentation
- Shows exact code location that triggered each query
- Particularly useful for:
  - Test debugging - identify unexpected queries
  - Performance analysis - see query patterns
  - Learning - understand halfORM's SQL generation

**Disable when done:**
```python
blog.sql_trace = False
```

!!! tip "ho_mogrify() vs sql_trace"
    - Use `ho_mogrify()` to inspect a **specific** query before execution
    - Use `sql_trace = True` to monitor **all** queries automatically with caller context
    - Combine both for maximum debugging insight during development

### Minimizing Database Calls

```python
# ❌ Inefficient - multiple queries
def get_author_stats_slow(author_id):
    author = Author(id=author_id).ho_get()
    posts = author.posts_rfk()
    published = posts(is_published=True)
    
    return {
        'name': f"{author.first_name.value} {author.last_name.value}",
        'total_posts': posts.ho_count(),          # Query 1
        'published_posts': published.ho_count(),  # Query 2  
        'draft_posts': posts(is_published=False).ho_count(),  # Query 3
        'total_views': sum(p['view_count'] for p in published)  # Query 4 + N queries
    }

# ✅ Efficient - fewer queries with strategic data loading
def get_author_stats_fast(author_id):
    author = Author(id=author_id).ho_get()
    
    # Get all posts at once with needed fields
    all_posts = list(author.posts_rfk().ho_select('is_published', 'view_count'))
    
    # Calculate stats in Python
    published_posts = [p for p in all_posts if p['is_published']]
    
    return {
        'name': f"{author.first_name.value} {author.last_name.value}",
        'total_posts': len(all_posts),
        'published_posts': len(published_posts),
        'draft_posts': len(all_posts) - len(published_posts),
        'total_views': sum(p['view_count'] for p in published_posts)
    }
```

### Using EXISTS for Existence Checks

```python
# ✅ Efficient existence checks
if not Author(email='new@example.com').ho_is_empty():
    print("Email already exists")

# ✅ Efficient counting for small numbers
draft_count = Post(is_published=False).ho_count()
if draft_count > 0:
    print(f"You have {draft_count} drafts")

# ❌ Avoid loading data just to check existence
# if len(list(Author(email='new@example.com'))) > 0:  # Don't do this
```

## Database-First Advanced Patterns

### When to Create Views

For complex queries that you use frequently, consider database views:

```sql
-- Create a materialized view for expensive analytics
CREATE MATERIALIZED VIEW blog.author_analytics AS
SELECT 
    a.id,
    a.first_name || ' ' || a.last_name as full_name,
    a.email,
    COUNT(DISTINCT p.id) as total_posts,
    COUNT(DISTINCT CASE WHEN p.is_published THEN p.id END) as published_posts,
    COALESCE(SUM(p.view_count), 0) as total_views,
    COALESCE(AVG(p.view_count), 0) as avg_views_per_post,
    COUNT(DISTINCT c.id) as total_comments,
    MAX(p.published_at) as last_post_date
FROM blog.author a
LEFT JOIN blog.post p ON a.id = p.author_id
LEFT JOIN blog.comment c ON a.id = c.author_id
GROUP BY a.id, a.first_name, a.last_name, a.email;

-- Add indexes for performance
CREATE INDEX idx_author_analytics_total_posts ON blog.author_analytics(total_posts);
CREATE INDEX idx_author_analytics_total_views ON blog.author_analytics(total_views);
```

```python
# Use the view in halfORM for fast analytics
AuthorAnalytics = blog.get_relation_class('blog.author_analytics')

# Fast queries on pre-calculated data
top_authors = (AuthorAnalytics(published_posts=('>', 5))
               .ho_order_by('total_views DESC')
               .ho_limit(10))

for author in top_authors.ho_select('full_name', 'total_posts', 'total_views'):
    print(f"{author['full_name']}: {author['total_posts']} posts, {author['total_views']} views")

# Refresh the materialized view when needed
blog.execute("REFRESH MATERIALIZED VIEW blog.author_analytics")
```

### Using PostgreSQL Functions for Complex Logic

```sql
-- Create a function for complex search
CREATE OR REPLACE FUNCTION blog.search_content(
    search_term TEXT,
    limit_results INTEGER DEFAULT 10
) RETURNS TABLE(
    post_id INTEGER,
    title VARCHAR,
    relevance_score NUMERIC,
    author_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.title,
        (
            CASE WHEN p.title ILIKE '%' || search_term || '%' THEN 10 ELSE 0 END +
            CASE WHEN p.excerpt ILIKE '%' || search_term || '%' THEN 5 ELSE 0 END +
            CASE WHEN p.content ILIKE '%' || search_term || '%' THEN 1 ELSE 0 END
        )::NUMERIC as relevance_score,
        a.first_name || ' ' || a.last_name as author_name
    FROM blog.post p
    JOIN blog.author a ON p.author_id = a.id
    WHERE p.is_published = TRUE
    AND (
        p.title ILIKE '%' || search_term || '%' OR
        p.excerpt ILIKE '%' || search_term || '%' OR  
        p.content ILIKE '%' || search_term || '%'
    )
    ORDER BY relevance_score DESC
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;
```

```python
# Use the function from halfORM
def search_posts(term, limit=10):
    """Search posts using PostgreSQL function"""
    results = blog.execute_function('blog.search_content', term, limit)
    return [{
        'post_id': row['post_id'],
        'title': row['title'],
        'relevance_score': row['relevance_score'],
        'author_name': row['author_name']
    } for row in results]

# Usage
search_results = search_posts('postgresql')
for result in search_results:
    print(f"{result['title']} by {result['author_name']} (score: {result['relevance_score']})")
```

## Subquery Patterns

### Using halfORM Queries as Subqueries

While halfORM excels at declarative queries, sometimes you need subquery-like patterns:

```python
# Find authors who have more posts than the average
def get_prolific_authors():
    # First, calculate average posts per author
    all_authors = Author()
    total_authors = all_authors.ho_count()
    total_posts = Post().ho_count()
    avg_posts = total_posts / total_authors if total_authors > 0 else 0
    
    # Find authors above average
    prolific = []
    for author in all_authors:
        post_count = author.posts_rfk().ho_count()
        if post_count > avg_posts:
            prolific.append({
                'author': author,
                'post_count': post_count,
                'above_average': post_count - avg_posts
            })
    
    return sorted(prolific, key=lambda x: x['post_count'], reverse=True)

# Usage
prolific_authors = get_prolific_authors()
for author_data in prolific_authors:
    author = author_data['author']
    name = f"{author.first_name.value} {author.last_name.value}"
    print(f"{name}: {author_data['post_count']} posts (+{author_data['above_average']:.1f} above avg)")
```

### Complex Aggregation Patterns

```python
def get_engagement_metrics(days_back=30):
    """Calculate engagement metrics for recent posts"""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    recent_posts = Post(
        is_published=True,
        published_at=('>', cutoff_date)
    )
    
    metrics = []
    for post in recent_posts.ho_select('id', 'title', 'view_count', 'published_at'):
        comments = Post(id=post['id']).comments_rfk()
        approved_comments = comments(is_approved=True)
        
        # Calculate engagement score
        days_since_publish = (datetime.now() - post['published_at']).days + 1
        views_per_day = post['view_count'] / days_since_publish
        comments_per_day = approved_comments.ho_count() / days_since_publish
        
        engagement_score = (views_per_day * 0.1) + (comments_per_day * 2)
        
        metrics.append({
            'post_id': post['id'],
            'title': post['title'],
            'views': post['view_count'],
            'comments': approved_comments.ho_count(),
            'days_live': days_since_publish,
            'engagement_score': engagement_score
        })
    
    return sorted(metrics, key=lambda x: x['engagement_score'], reverse=True)

# Get top engaging posts
top_engaging = get_engagement_metrics(days_back=7)[:5]
for post in top_engaging:
    print(f"{post['title']}: {post['engagement_score']:.2f} engagement score")
```

## Advanced Use Cases

### Batch Operations with Transactions

```python
from half_orm.transaction import transaction

@transaction
def bulk_update_posts(author_id, updates):
    """Bulk update multiple posts with transaction safety"""
    author = Author(id=author_id)
    posts = author.posts_rfk(is_published=False)  # Only drafts
    
    updated_count = 0
    for post in posts:
        try:
            # Apply updates
            post.ho_update(**updates)
            updated_count += 1
        except Exception as e:
            print(f"Failed to update post {post.id.value}: {e}")
            raise  # This will rollback the entire transaction
    
    return updated_count

# Usage
try:
    count = bulk_update_posts(author_id=1, updates={
        'is_published': True,
        'published_at': datetime.now()
    })
    print(f"Successfully published {count} posts")
except Exception as e:
    print(f"Bulk update failed: {e}")
```

### Dynamic Query Building

```python
def build_dynamic_post_query(filters):
    """Build a post query from dynamic filters"""
    query = Post(is_published=True)
    
    # Apply filters dynamically
    if 'author_id' in filters:
        query = query & Post(author_id=filters['author_id'])
    
    if 'min_views' in filters:
        query = query & Post(view_count=('>=', filters['min_views']))
    
    if 'published_after' in filters:
        query = query & Post(published_at=('>=', filters['published_after']))
    
    if 'published_before' in filters:
        query = query & Post(published_at=('<=', filters['published_before']))
    
    if 'title_contains' in filters:
        query = query & Post(title=('ilike', f"%{filters['title_contains']}%"))
    
    if 'tags' in filters:
        # Posts that have any of the specified tags
        tag_query = Post()
        for tag_id in filters['tags']:
            tag_posts = Post().post_tags_rfk(tag_id=tag_id)
            tag_query = tag_query | tag_posts
        query = query & tag_query
    
    return query

# Usage
filters = {
    'min_views': 50,
    'published_after': '2024-01-01',
    'published_before': '2024-12-31',
    'title_contains': 'postgresql',
    'tags': [1, 3, 5]  # Python, PostgreSQL, Performance tags
}

dynamic_query = build_dynamic_post_query(filters)
results = dynamic_query.ho_order_by('view_count DESC').ho_limit(20)

print(f"Found {results.ho_count()} posts matching criteria")
for post in results.ho_select('title', 'view_count'):
    print(f"- {post['title']} ({post['view_count']} views)")
```

### Caching Query Results

```python
from functools import lru_cache
from datetime import datetime, timedelta

class PostAnalytics:
    def __init__(self, blog_model):
        self.blog = blog_model
        self.Post = blog_model.get_relation_class('blog.post')
        self.Author = blog_model.get_relation_class('blog.author')
    
    @lru_cache(maxsize=128)
    def get_top_posts_cached(self, days_back=7, limit=10):
        """Cached version of top posts query"""
        cutoff = datetime.now() - timedelta(days=days_back)
        
        query = (self.Post(is_published=True, published_at=('>', cutoff))
                .ho_order_by('view_count DESC')
                .ho_limit(limit))
        
        return tuple(query.ho_select('id', 'title', 'view_count'))
    
    def get_top_posts(self, days_back=7, limit=10, use_cache=True):
        """Get top posts with optional caching"""
        if use_cache:
            return list(self.get_top_posts_cached(days_back, limit))
        else:
            cutoff = datetime.now() - timedelta(days=days_back)
            query = (self.Post(is_published=True, published_at=('>', cutoff))
                    .ho_order_by('view_count DESC')
                    .ho_limit(limit))
            return list(query.ho_select('id', 'title', 'view_count'))
    
    def clear_cache(self):
        """Clear cached results"""
        self.get_top_posts_cached.cache_clear()

# Usage
analytics = PostAnalytics(blog)

# First call - hits database
top_posts = analytics.get_top_posts(days_back=7, limit=5)
print("Top posts (from database):")
for post in top_posts:
    print(f"- {post['title']}: {post['view_count']} views")

# Second call - uses cache
top_posts_cached = analytics.get_top_posts(days_back=7, limit=5)
print("\nTop posts (from cache):")
for post in top_posts_cached:
    print(f"- {post['title']}: {post['view_count']} views")

# Clear cache when data changes
analytics.clear_cache()
```

## Common Query Patterns

### Searching and Filtering

```python
def search_and_filter_posts(search_term=None, author_id=None, tag_ids=None, 
                           min_views=None, published_after=None, published_before=None, limit=20):
    """Comprehensive search and filter function"""
    query = Post(is_published=True)
    
    # Text search
    if search_term:
        search_query = (Post(title=('ilike', f'%{search_term}%')) |
                       Post(excerpt=('ilike', f'%{search_term}%')) |  
                       Post(content=('ilike', f'%{search_term}%')))
        query = query & search_query
    
    # Author filter
    if author_id:
        query = query & Post(author_id=author_id)
    
    # View count filter
    if min_views:
        query = query & Post(view_count=('>=', min_views))
    
    # Date range filters
    if published_after:
        query = query & Post(published_at=('>=', published_after))
    
    if published_before:
        query = query & Post(published_at=('<=', published_before))
    
    # Tag filter (posts must have ALL specified tags)
    if tag_ids:
        for tag_id in tag_ids:
            tagged_posts = Post().post_tags_rfk(tag_id=tag_id)
            query = query & tagged_posts
    
    return (query.ho_order_by('published_at DESC')
                 .ho_limit(limit)
                 .ho_select('id', 'title', 'excerpt', 'published_at', 'view_count'))

# Usage examples
recent_python_posts = search_and_filter_posts(
    search_term='python',
    min_views=10,
    published_after='2024-01-01'
)

author_popular_posts = search_and_filter_posts(
    author_id=1,
    min_views=50,
    limit=10
)
```

### Reporting Queries

```python
def generate_content_report(start_date, end_date):
    """Generate comprehensive content report"""
    
    # Date range filter using set operations
    date_filter = (Post(published_at=('>=', start_date)) & 
                   Post(published_at=('<=', end_date)) &
                   Post(is_published=True))
    
    # Basic stats
    total_posts = date_filter.ho_count()
    total_views = sum(p['view_count'] for p in date_filter.ho_select('view_count'))
    total_comments = Post().comments_rfk().ho_count()
    
    # Author performance
    author_stats = {}
    for author in Author(is_active=True):
        author_posts = author.posts_rfk() & date_filter
        post_count = author_posts.ho_count()
        if post_count > 0:
            author_views = sum(p['view_count'] for p in author_posts.ho_select('view_count'))
            author_stats[f"{author.first_name.value} {author.last_name.value}"] = {
                'posts': post_count,
                'views': author_views,
                'avg_views': author_views / post_count
            }
    
    # Top performing posts
    top_posts = (date_filter.ho_order_by('view_count DESC')
                           .ho_limit(5)
                           .ho_select('title', 'view_count', 'published_at'))
    
    return {
        'period': {'start': start_date, 'end': end_date},
        'totals': {
            'posts': total_posts,
            'views': total_views,
            'comments': total_comments,
            'avg_views_per_post': total_views / total_posts if total_posts > 0 else 0
        },
        'authors': dict(sorted(author_stats.items(), 
                              key=lambda x: x[1]['views'], reverse=True)),
        'top_posts': list(top_posts)
    }

# Generate monthly report
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=30)

report = generate_content_report(start_date.strftime('%Y-%m-%d'), 
                                end_date.strftime('%Y-%m-%d'))

print(f"Content Report: {report['period']['start']} to {report['period']['end']}")
print(f"Total Posts: {report['totals']['posts']}")
print(f"Total Views: {report['totals']['views']}")
print(f"Average Views per Post: {report['totals']['avg_views_per_post']:.1f}")

print("\nTop Authors:")
for author, stats in list(report['authors'].items())[:3]:
    print(f"  {author}: {stats['posts']} posts, {stats['views']} views")

print("\nTop Posts:")
for post in report['top_posts']:
    print(f"  {post['title']}: {post['view_count']} views")
```

## Performance Best Practices

### 1. Use Appropriate Query Methods

```python
# ✅ For checking existence
if not Author(email='test@example.com').ho_is_empty():
    print("Email exists")

# ✅ For counting
post_count = Author(id=1).posts_rfk().ho_count()

# ✅ For getting a single record
author = Author(id=1).ho_get()

# ✅ For iterating all records
for post in Post(is_published=True):
    print(post['title'])

# ✅ For specific columns only
for author in Author().ho_select('first_name', 'last_name'):
    print(f"{author['first_name']} {author['last_name']}")
```

### 2. Minimize Relationship Traversals

```python
# ❌ Inefficient - multiple queries
def get_post_with_author_slow(post_id):
    post = Post(id=post_id).ho_get()
    author = post.author_fk().ho_get()
    return {
        'title': post.title.value,
        'author_name': f"{author.first_name.value} {author.last_name.value}"
    }

# ✅ More efficient - fewer queries
def get_post_with_author_fast(post_id):
    post = Post(id=post_id).ho_get()
    # Get just the author ID from the post, then fetch author name efficiently
    author = Author(id=post.author_id.value).ho_select('first_name', 'last_name').ho_get()
    return {
        'title': post.title.value,
        'author_name': f"{author['first_name']} {author['last_name']}"
    }
```

### 3. Use Database Features

```python
# ✅ Let PostgreSQL handle complex operations
# Instead of complex Python logic, create a database view or function

# Example: Use a view for complex joins
TopAuthors = blog.get_relation_class('blog.top_authors_view')  # Assuming view exists
top_performers = TopAuthors(month_year='2024-01').ho_limit(10)

# ✅ Use PostgreSQL aggregation functions when available
# Instead of: sum(p['view_count'] for p in posts)
# Use a database view or function that calculates this
```

## Chapter Summary

### ✅ Advanced Concepts Mastered

**Complex Filtering**
- Multi-condition queries with boolean logic
- Regular expression patterns and NULL handling
- Advanced set operations and relationship existence queries

**Query Optimization**
- Performance analysis with `ho_mogrify()`
- Efficient field selection and pagination patterns
- Minimizing database calls through strategic query design

**Advanced Patterns**
- Subquery-like patterns using halfORM
- Dynamic query building and batch operations
- Caching strategies for frequently-used queries

**Database-First Solutions**
- When to use PostgreSQL views for complex analytics
- Leveraging PostgreSQL functions for business logic
- Materialized views for expensive calculations

### 🎯 Skills You Can Now Apply

- Build sophisticated multi-table queries with optimal performance
- Implement complex search and filtering functionality
- Create efficient reporting and analytics queries
- Debug and optimize query performance
- Choose appropriate database-first solutions for complex requirements

### 💡 Key Performance Principles

1. **Understand your queries** - Use `ho_mogrify()` to see generated SQL
2. **Minimize database calls** - Fetch what you need in fewer trips
3. **Use appropriate methods** - `ho_count()` vs loading data, `ho_is_empty()` vs iteration
4. **Leverage PostgreSQL** - Views and functions for complex logic
5. **Cache wisely** - Store expensive query results when appropriate

## What's Next?

You've mastered halfORM's querying capabilities! In the next chapter, [Transactions](transactions.md), you'll learn:

- **Transaction management** - Ensuring data consistency
- **Error handling** - Rollback on failures
- **Batch operations** - Efficient bulk updates
- **Isolation levels** - Controlling concurrent access

Transactions are crucial for maintaining data integrity in production applications.

!!! tip "Additional Resources"
    - **[halfORM Fundamentals](../fundamentals.md)** - Core concepts reference
    - **[Relation API Reference](../api/relation.md)** - Complete query method documentation
    - **[Examples](../examples/index.md)** - Real-world query patterns
    - **[Performance Guide](../guides/performance.md)** - Advanced optimization techniques

---

**Ready for data integrity?** Continue to [Chapter 6: Transactions](transactions.md)!