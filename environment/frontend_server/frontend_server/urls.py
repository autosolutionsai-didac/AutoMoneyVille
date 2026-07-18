"""frontend_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, re_path
from translator import views as translator_views

urlpatterns = [
    # API endpoints (backend-driven simulation)
    path("api/movements/", translator_views.api_movements, name="api_movements"),
    path("api/health/", translator_views.api_health, name="api_health"),
    path("api/status/", translator_views.api_status, name="api_status"),
    path("api/save/", translator_views.api_save, name="api_save"),
    path("api/simulate/", translator_views.api_simulate, name="api_simulate"),
    path("api/saves/", translator_views.api_saves, name="api_saves"),
    path("api/town-center/", translator_views.api_town_center, name="api_town_center"),
    path(
        "api/town-center/requests/",
        translator_views.api_town_center_request,
        name="api_town_center_request",
    ),
    path(
        "api/town-center/requests/<str:request_id>/transition/",
        translator_views.api_town_center_request_transition,
        name="api_town_center_request_transition",
    ),
    path(
        "api/town-center/rewards/",
        translator_views.api_town_center_reward,
        name="api_town_center_reward",
    ),
    path(
        "api/town-center/requests/<str:request_id>/record-delivery/",
        translator_views.api_town_center_record_delivery,
        name="api_town_center_record_delivery",
    ),
    path(
        "api/persona/<str:persona_name>/state/",
        translator_views.api_persona_state,
        name="api_persona_state",
    ),
    path(
        "api/replay/<str:sim_code>/<str:step>/persona/<str:persona_name>/state/",
        translator_views.api_replay_persona_state,
        name="api_replay_persona_state",
    ),
    path("api/events/", translator_views.api_events, name="api_events"),
    # Page views
    re_path(r"^$", translator_views.landing, name="landing"),
    re_path(r"^simulator_home$", translator_views.home, name="home"),
    re_path(
        r"^demo/(?P<sim_code>[\w-]+)/(?P<step>[\w-]+)/(?P<play_speed>[\w-]+)/$",
        translator_views.demo,
        name="demo",
    ),
    re_path(
        r"^replay/(?P<sim_code>[\w-]+)/(?P<step>[^/]+)/$",
        translator_views.replay,
        name="replay",
    ),
    re_path(
        r"^replay_persona_state/(?P<sim_code>[\w-]+)/(?P<step>[\w-]+)/(?P<persona_name>[\w-]+)/$",
        translator_views.replay_persona_state,
        name="replay_persona_state",
    ),
    re_path(r"^path_tester/$", translator_views.path_tester, name="path_tester"),
    re_path(
        r"^path_tester_update/$",
        translator_views.path_tester_update,
        name="path_tester_update",
    ),
    path("admin/", admin.site.urls),
]
