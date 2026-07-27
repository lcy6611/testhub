from rest_framework import serializers
from .models import Defect, ReleaseConclusion


class DefectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Defect
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReleaseConclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseConclusion
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
