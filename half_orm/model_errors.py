"""This module provides the errors for the model module."""

class NamingWarning(FutureWarning):
    """A name half_orm accepts in 2.x and will refuse in 3.0.

    A name Python would read as another one (not in NFKC form), or an
    annotation line that holds no name. Read from the database, it will make
    3.0 refuse the database (NamingError when the Model is created); given
    as an Fkeys alias, it will make 3.0 refuse the alias. Turn it into an error now with
    ``-W error::half_orm.model_errors.NamingWarning``, or
    ``warnings.simplefilter('error', NamingWarning)``.
    """

class MissingConfigFile(Exception):
    """The config file has not been found."""
    def __init__(self, filename):
        self.filename = filename
        Exception.__init__(self, f'Missing config file: {filename}')

class MalformedConfigFile(Exception):
    """The config file is malformed.

    The missing parameters are indicated in the error message.
    """
    def __init__(self, filename, msg, missing_param):
        self.filename = filename
        Exception.__init__(
            self,
            f"Malformed config file: {filename}\n{msg}: {missing_param}")

class UnknownRelation(Exception):
    """The FQRN doesn't match any relation in the database."""
    def __init__(self, sfqrn):
        self.dbname = sfqrn[0]
        self.schema = sfqrn[1]
        self.relation = sfqrn[2]
        Exception.__init__(self, f"'{sfqrn[1]}.{sfqrn[2]}' does not exist in the database {sfqrn[0]}.")

class MissingSchemaInName(Exception):
    """The QRN should contain a schema name."""
    def __init__(self, qrn):
        Exception.__init__(self, f"do you mean 'public.{qrn}'?")


class NamingProblem:
    """One thing that keeps the names of a database from being used as they are.

    Attributes:
        kind (str): ``'reverse_fkey'`` (two foreign keys filed under one
            name), ``'attribute'`` (two attributes of a relation with one
            name), ``'reserved'`` (a column named like something Relation
            uses), ``'qualified_name'`` (two relations spelled alike without
            quotes) or ``'declaration'`` (a declared name that cannot be
            used).
        name (str): the name in dispute.
        relation (str | None): ``schema.relation`` it is in dispute on.
        members (list[str]): what is competing for it.
        hint (str): what to do about it.
    """
    def __init__(self, kind, name, relation, members, hint):
        self.kind = kind
        self.name = name
        self.relation = relation
        self.members = list(members)
        self.hint = hint

    def __str__(self):
        where = f' on {self.relation}' if self.relation else ''
        lines = [f'- [{self.kind}] {self.name!r}{where}']
        lines += [f'    {member}' for member in self.members]
        lines.append(f'  -> {self.hint}')
        return '\n'.join(lines)

    def __repr__(self):
        return f'NamingProblem({self.kind!r}, {self.name!r}, {self.relation!r})'


class NamingError(Exception):
    """Names derived from the catalog collide, or a declared name is unusable.

    Raised when a Model is created or reloaded. Every problem is listed, in
    the message and in :attr:`problems`: until they are all settled no Model
    can be opened on the database with these declarations. See
    :mod:`half_orm.naming` for how to settle them.

    Attributes:
        dbname (str): the database.
        problems (list[NamingProblem]): everything that was found.
    """
    def __init__(self, dbname, problems):
        self.dbname = dbname
        self.problems = list(problems)
        count = len(self.problems)
        Exception.__init__(
            self,
            f"{count} naming problem{'s' if count > 1 else ''} in database "
            f"'{dbname}':\n"
            + '\n'.join(str(problem) for problem in self.problems)
            + "\nGive one side of each a name of its own -- an '@ho_name' or "
            "'@ho_reverse_name' line in a comment, or the field_names, "
            "reverse_names and ignore arguments of Model. "
            "See half_orm.naming.")
