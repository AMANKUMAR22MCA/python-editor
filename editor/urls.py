from django.urls import path
from . import views

urlpatterns = [
    path('', views.editor_view, name='editor'),
    # path('run/', views.run_code, name='run_code'),
]
