"""Who is allowed to do what.

Seller status is asked for in views, templates and tests, so the question is
answered in exactly one place. Swapping Groups for something else later means
changing only this file.
"""

# The server's own name for the role. Deliberately a constant and never read
# from a request: if the browser could supply the group name, anyone could post
# their way into any role.
SELLER_GROUP = 'Seller'


def is_seller(user):
    # is_authenticated is checked first on purpose. AnonymousUser has no .groups,
    # so reading it would raise AttributeError; `and` stops at the first false.
    return user.is_authenticated and user.groups.filter(name=SELLER_GROUP).exists()
