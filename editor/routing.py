from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/run_code/$', consumers.RunCodeConsumer.as_asgi()),
]