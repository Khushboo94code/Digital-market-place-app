"""Stop the browser reusing a page rendered for a different user.

Django sends `Vary: Cookie` but no `Cache-Control`, so browsers fall back to
heuristic caching and the back/forward cache restores whole pages from memory.
The navbar is built per user, so a page cached while a seller was signed in can
reappear for a buyer — complete with Dashboard and Sales links.

`no-store` is the only directive the back/forward cache honours, so it is what
this sets.
"""

from django.utils.cache import add_never_cache_headers


class NoStoreHtmlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only HTML pages carry the navbar. Leave media and downloads cacheable.
        content_type = response.headers.get('Content-Type', '')
        if content_type.startswith('text/html'):
            add_never_cache_headers(response)

        return response
