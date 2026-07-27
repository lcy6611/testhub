from django.contrib import admin

from .models import KgEdge, KgEntity


@admin.register(KgEntity)
class KgEntityAdmin(admin.ModelAdmin):
    list_display = ("entity_key", "entity_type", "label", "project_id", "updated_at")
    search_fields = ("entity_key", "label", "ref_id")
    list_filter = ("entity_type",)


@admin.register(KgEdge)
class KgEdgeAdmin(admin.ModelAdmin):
    list_display = ("src", "relation_type", "dst", "project_id", "created_at")
    list_filter = ("relation_type",)
    search_fields = ("src__entity_key", "dst__entity_key")
