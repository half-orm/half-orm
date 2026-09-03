import sys
from os import listdir, path

import psycopg

import half_orm
from half_orm import model_errors
from half_orm.model import CONF_DIR, Model

def print_help():
    """Print usage information"""
    print(f"[halfORM] version {half_orm.__version__}")
    print()
    print("Usage:")
    print("  python -m half_orm                    Show version and test connections")
    print("  python -m half_orm <database>         Show database structure")
    print("  python -m half_orm <database> <relation>  Show relation details")
    print("  python -m half_orm --help             Show this help message")
    print()
    print("Examples:")
    print("  python -m half_orm                    # Diagnostic mode")
    print("  python -m half_orm blog_tutorial      # Show blog_tutorial structure")
    print("  python -m half_orm blog_tutorial blog.author  # Show author table details")
    print()
    print("Documentation: https://half-orm.github.io/half-orm/")

def check_peer_authentication():
    try:
        template1 = Model('template1')
        print("✅ Connected to template1 database (default setup)")
    except psycopg.Error as exc:
        print(f'⚠️  Unable to connect to template1: {exc}.')

def check_databases_access():
    print(f"\n== Checking connections for files in HALFORM_CONF_DIR={CONF_DIR}")
    try:
        files = [file for file in listdir(CONF_DIR) if path.isfile(path.join(CONF_DIR, file))]
        if files:
            for cnx_file in files:
                try:
                    model = Model(cnx_file)
                    print(f"✅ {cnx_file}")
                except (psycopg.Error, model_errors.MalformedConfigFile) as exc:
                    sys.stderr.write(f'❌ {cnx_file}: {exc}\n')
        else:
            print("💡 No database configuration files found.")
            print(f"   To add database connections:")
            print(f"   • Create config files in: {CONF_DIR}")
            print(f"   • Or set different config directory: export HALFORM_CONF_DIR=/path/to/configs")
    except FileNotFoundError:
        sys.stderr.write(f"❌ '{CONF_DIR}' does not exist.\nChange HALFORM_CONF_DIR variable\n")
    sys.stderr.flush()
    print(f"\nCheck the documentation on https://half-orm.github.io/half-orm/half-an-hour/#1-connect-1-min")

def show_version():
    print(f"[halfORM] version {half_orm.__version__}")

def main():
    """Main CLI entry point with proper argument handling"""
    show_version()
    args_len = len(sys.argv)
    
    # Handle help requests
    if args_len > 1 and sys.argv[1] in ('--help', '-h', 'help'):
        print_help()
        return
    
    # Handle different argument patterns
    if args_len == 1:
        # Default diagnostic mode
        check_peer_authentication()
        check_databases_access()
        
    elif args_len == 2:
        # Show database structure
        database = sys.argv[1]
        if database == '':
            sys.stderr.write("❌ Empty database name\n")
            sys.exit(1)
        try:
            model = Model(database)
            print(model)
        except (psycopg.Error, model_errors.MalformedConfigFile) as exc:
            sys.stderr.write(f"❌ Error connecting to database '{database}': {exc}\n")
            sys.stderr.write(f"💡 Use 'python -m half_orm --help' for usage information\n")
            sys.exit(1)

    elif args_len == 3:
        # Show specific relation details
        database = sys.argv[1]
        relation = sys.argv[2]
        if database == '':
            sys.stderr.write("❌ Empty database name\n")
            sys.exit(1)
        if relation == '':
            sys.stderr.write("❌ Empty relation name\n")
            sys.exit(1)
        try:
            model = Model(database)
            relation_class = model.get_relation_class(relation)
            print(relation_class())
        except (psycopg.Error, model_errors.MalformedConfigFile, model_errors.UnknownRelation, model_errors.MissingSchemaInName) as exc:
            sys.stderr.write(f"❌ Error accessing relation '{relation}' in database '{database}': {exc}\n")
            sys.stderr.write(f"💡 Use 'python -m half_orm --help' for usage information\n")
            sys.exit(1)
            
    else:
        # Too many arguments
        sys.stderr.write(f"❌ Too many arguments provided\n")
        sys.stderr.write(f"💡 Use 'python -m half_orm --help' for usage information\n")
        sys.exit(1)

if __name__ == '__main__':
    main()