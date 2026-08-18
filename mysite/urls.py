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
# so the previous version of this file meant every product image and every paid
# download 404'd in production. This route serves MEDIA_ROOT in both modes.
#
# Django's static serve view does no caching and reads the file through the app
# process, which is acceptable at this size. Moving uploads to object storage
# (S3/Cloudflare R2) behind a CDN is the real fix when traffic grows.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', static_serve, {'document_root': settings.MEDIA_ROOT}),
]
