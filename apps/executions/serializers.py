from rest_framework import serializers
from .models import TestPlan, TestRun, TestRunCase, TestRunCaseHistory, TestRunCaseStep
from apps.testcases.models import TestCase
from apps.users.serializers import UserSimpleSerializer


class TestRunCaseStepSerializer(serializers.ModelSerializer):
    """执行步骤（步骤级状态）序列化器。"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    executed_by_name = serializers.CharField(source='executed_by.username', read_only=True, default='')

    class Meta:
        model = TestRunCaseStep
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'executed_at', 'executed_by']


class TestRunCaseHistorySerializer(serializers.ModelSerializer):
    executed_by = UserSimpleSerializer(read_only=True)

    class Meta:
        model = TestRunCaseHistory
        fields = ('id', 'status', 'actual_result', 'comments', 'executed_by', 'executed_at')

class TestRunCaseSimpleSerializer(serializers.ModelSerializer):
    testcase = serializers.StringRelatedField()
    class Meta:
        model = TestRunCase
        fields = ('id', 'testcase', 'status')

class TestRunCaseDetailSerializer(serializers.ModelSerializer):
    testcase = serializers.StringRelatedField()
    executed_by = UserSimpleSerializer(read_only=True)
    history = TestRunCaseHistorySerializer(many=True, read_only=True)
    step_records = TestRunCaseStepSerializer(many=True, read_only=True)
    testcase_id = serializers.IntegerField(source='testcase.id', read_only=True)

    class Meta:
        model = TestRunCase
        fields = ('id', 'testcase', 'testcase_id', 'status', 'priority', 'actual_result', 'comments',
                 'defects', 'elapsed_time', 'executed_by', 'executed_at', 'created_at',
                 'updated_at', 'history', 'step_records')

class TestRunSerializer(serializers.ModelSerializer):
    run_cases = TestRunCaseSimpleSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = TestRun
        fields = ('id', 'name', 'status', 'assignee', 'progress', 'run_cases')
    
    def get_progress(self, obj):
        return obj.progress_stats


class TestPlanSerializer(serializers.ModelSerializer):
    creator = UserSimpleSerializer(read_only=True)
    projects = serializers.StringRelatedField(many=True, read_only=True)
    version = serializers.StringRelatedField()

    class Meta:
        model = TestPlan
        fields = ('id', 'name', 'projects', 'version', 'creator', 'created_at', 'is_active')


class TestPlanDetailSerializer(serializers.ModelSerializer):
    test_runs = TestRunSerializer(many=True, read_only=True)
    creator = UserSimpleSerializer(read_only=True)
    projects = serializers.StringRelatedField(many=True, read_only=True)
    version = serializers.StringRelatedField()

    class Meta:
        model = TestPlan
        fields = '__all__'

class TestRunCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestRunCase
        fields = '__all__'
