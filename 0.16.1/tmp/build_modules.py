## Building a Project Structure

Now that we have the new foreign key, we can use it in our halfORM scripts.

First, let's create a `gitlab` directory where we'll put all our modules:

```sh
$ mkdir gitlab
$ export PYTHONPATH=$PWD
$ cd gitlab
```

In that directory, we'll create the `__init__.py` file that will handle the model shared between all modules:

```python title="__init__.py"
from half_orm.model import Model

model = Model('gitlab')
```

Let's test the `__init__.py` by reusing the script that lists the administrators:

```python title="admins.py"
import gitlab

Users = gitlab.model.get_relation_class('public.users')
# List the admin names
for admin in Users(admin=True).ho_select('name'):
    print(admin['name'])
```

Now let's create the modules `projects.py` and `users.py`:

```python title="projects.py"
import gitlab

class Projects(gitlab.model.get_relation_class('public.projects')):
    Fkeys = {
        'creator_fk': 'creator_fk'
    }
```

```python title="users.py"
import gitlab

class Users(gitlab.model.get_relation_class('public.users')):
    Fkeys = {
        'projects_rfk': '_reverse_fkey_gitlab_public_projects_creator_id'
    }
```

## Putting It All Together

Now we can use these modules in a practical script:

```python title="get_projects_created_by.py"
#!/usr/bin/env python3
"""
Get all projects created by a specific user.
Usage: get_projects_created_by.py <username>
"""
import sys
from gitlab.users import Users

def main():
    if len(sys.argv) != 2:
        print("Usage: get_projects_created_by.py <username>")
        print("Example: get_projects_created_by.py alice")
        sys.exit(1)

    username = sys.argv[1]

    try:
        user = Users(username=username)
        if user.ho_is_empty():
            print(f"❌ User '{username}' not found")
            sys.exit(1)

        project_count = user.projects_rfk().ho_count()
        projects = user.projects_rfk().ho_order_by('created_at DESC')

        if project_count == 0:
            print(f"📭 User '{username}' has no projects")
        else:
            print(f"📂 Projects created by '{username}' ({project_count} total):")
            for project in projects.ho_select('name', 'created_at'):
                print(f"  • {project['name']} (created: {project['created_at']})")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

Example output:
```sh
$ python get_projects_created_by.py alice
📂 Projects created by 'alice' (3 total):
  • awesome-project (created: 2024-01-15 14:30:00)
  • data-analysis-tool (created: 2024-01-10 09:15:00)  
  • documentation-site (created: 2024-01-05 16:45:00)
```
