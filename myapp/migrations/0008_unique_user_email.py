"""One email address identifies one account.

Buyer and seller are separate accounts here, so a person keeps two logins with
two different emails — the same arrangement Amazon uses for personal and
business accounts.

The form already refuses a duplicate email with a friendly message, but form
checks are skipped by the admin, the shell, and two signups landing at the same
instant. This adds the constraint in the database, which nothing bypasses.

It is raw SQL because `email` belongs to Django's own auth.User model, and a
migration in this app cannot AlterField another app's model.

The case-insensitive part has no portable spelling, so the statement is chosen
per backend at run time:

  * SQLite   — `email COLLATE NOCASE`
  * Postgres — a functional index on `LOWER(email)`

Sending SQLite's COLLATE NOCASE to Postgres raises `collation "nocase" for
encoding "UTF8" does not exist`, which fails the whole deploy, so the two are
kept apart rather than merged into one string.
"""

from django.db import migrations

SQLITE_CREATE = """
CREATE UNIQUE INDEX IF NOT EXISTS myapp_auth_user_email_ci
ON auth_user (email COLLATE NOCASE);
"""

POSTGRES_CREATE = """
CREATE UNIQUE INDEX IF NOT EXISTS myapp_auth_user_email_ci
ON auth_user (LOWER(email));
"""

DROP = "DROP INDEX IF EXISTS myapp_auth_user_email_ci;"

CREATE_BY_VENDOR = {
    'sqlite': SQLITE_CREATE,
    'postgresql': POSTGRES_CREATE,
}


def create_index(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    try:
        sql = CREATE_BY_VENDOR[vendor]
    except KeyError:
        raise NotImplementedError(
            f'No case-insensitive unique email index defined for database '
            f'vendor {vendor!r}. Add one to CREATE_BY_VENDOR in '
            f'{__name__} before deploying on this backend.'
        )
    schema_editor.execute(sql)


def drop_index(apps, schema_editor):
    schema_editor.execute(DROP)


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_product_image'),
        ('auth', '__first__'),
    ]

    operations = [
        migrations.RunPython(create_index, drop_index),
    ]
