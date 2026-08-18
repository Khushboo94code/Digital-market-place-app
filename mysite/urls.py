"""
URL configuration for mysite project.

For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as static_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
]

# django.conf.urls.static.static() returns an empty list whenever DEBUG is False,
# so relying on it meant every product image 404'd in production. This route
# replaces it and works in both modes.
#
# The pattern deliberately matches only 'images/', the cover art, which is meant
# to be public. Purchased files live in MEDIA_ROOT/uploads and are NOT routed
# here: serving that prefix handed any product to anyone who had the URL, with no
# login, order or payment involved. They are reachable only through
# myapp.views.download, which verifies the buyer paid.
#
# Django's static serve view does no caching and reads through the app process,
# which is acceptable at this size. Object storage (S3/Cloudflare R2) behind a CDN
# is the real fix when traffic grows.
urlpatterns += [
    re_path(r'^media/(?P<path>images/.*)$', static_serve, {'document_root': settings.MEDIA_ROOT}),
]
