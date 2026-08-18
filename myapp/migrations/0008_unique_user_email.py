"""One email address identifies one account.

Buyer and seller are separate accounts here, so a person keeps two logins with
two different emails — the same arrangement Amazon uses for personal and
business accounts.

The form already refuses a duplicate email with a friendly message, but form
checks are skipped by the admin, the shell, and two signups landing at the same
instant. This adds the constraint in the database, which nothing bypasses.

It is raw SQL because `email` belongs to Django's own auth.User model, and a
migration in this app cannot AlterField another app's model. COLLATE NOCASE
makes it case-insensitive, so 'A@x.com' cannot be added alongside 'a@x.com'.

Note: this index is SQLite-specific. On PostgreSQL use
    CREATE UNIQUE INDEX ... ON auth_user (LOWER(email));
"""

from django.db import migrations

CREATE = """
CREATE UNIQUE INDEX IF NOT EXISTS myapp_auth_user_email_ci
ON auth_user (email COLLATE NOCASE);
"""

DROP = "DROP INDEX IF EXISTS myapp_auth_user_email_ci;"


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_product_image'),
        ('auth', '__first__'),
    ]

    operations = [
        migrations.RunSQL(CREATE, reverse_sql=DROP),
    ]
