
from django.urls import path
from . import views

urlpatterns = [
    path('',views.index),
    path('product/<int:id>/',views.detail,name='detail'),
]