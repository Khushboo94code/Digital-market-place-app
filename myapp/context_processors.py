"""Extra variables added to every template.

base.html needs to know whether to draw the seller links, and every page extends
base.html — so the answer has to be present in every template context without
each view remembering to pass it.
"""

from .roles import is_seller


def roles(request):
    return {'is_seller': is_seller(request.user)}
