from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "DormDesk"
admin.site.site_title = "DormDesk"
admin.site.index_title = "Общежитие"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.users.urls")),
    path("residency/", include("apps.residency.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("passes/", include("apps.passes.urls")),
    path("housing/", include("apps.housing.urls"))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
