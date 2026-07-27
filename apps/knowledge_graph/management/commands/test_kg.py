#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试知识图谱功能（管理命令）"""
from django.core.management.base import BaseCommand
from apps.knowledge_graph.registry import get_entity
from apps.knowledge_graph.query import get_entity_neighbors, get_subgraph, get_project_graph
from apps.knowledge_graph.coverage import get_project_coverage_report
from apps.knowledge_graph.models import KgEntity, KgEdge

class Command(BaseCommand):
    help = '测试知识图谱功能'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== 知识图谱功能测试 ===\n'))
        
        # 1. 检查数据
        self.stdout.write('1. 检查数据库...')
        entity_count = KgEntity.objects.count()
        edge_count = KgEdge.objects.count()
        self.stdout.write('   实体数: ' + str(entity_count))
        self.stdout.write('   边数: ' + str(edge_count))
        
        proj1_entities = KgEntity.objects.filter(project_id=1).count()
        proj1_edges = KgEdge.objects.filter(project_id=1).count()
        self.stdout.write('   项目1实体数: ' + str(proj1_entities))
        self.stdout.write('   项目1边数: ' + str(proj1_edges) + '\n')
        
        # 2. 测试get_entity
        self.stdout.write('2. 测试get_entity...')
        entity = get_entity('tc:23')
        if entity:
            msg = '   [OK] 找到实体: ' + entity.entity_key
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] 未找到实体'))
        
        # 3. 测试get_entity_neighbors
        self.stdout.write('\n3. 测试get_entity_neighbors...')
        neighbors = get_entity_neighbors('tc:23')
        entity_info = neighbors.get('entity')
        if entity_info:
            outgoing = len(neighbors.get('outgoing', []))
            incoming = len(neighbors.get('incoming', []))
            self.stdout.write(self.style.SUCCESS('   [OK] 邻居查询成功'))
            self.stdout.write('   Outgoing: ' + str(outgoing) + ', Incoming: ' + str(incoming))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] 实体不存在'))
        
        # 4. 测试get_subgraph
        self.stdout.write('\n4. 测试get_subgraph...')
        subgraph = get_subgraph('tc:23', depth=2, max_nodes=200)
        nodes = len(subgraph.get('nodes', []))
        edges = len(subgraph.get('edges', []))
        if nodes > 0:
            self.stdout.write(self.style.SUCCESS('   [OK] 子图查询成功'))
            self.stdout.write('   Nodes: ' + str(nodes) + ', Edges: ' + str(edges))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] 子图为空'))
        
        # 5. 测试get_project_graph
        self.stdout.write('\n5. 测试get_project_graph...')
        proj_graph = get_project_graph(1, depth=2, max_nodes=300)
        nodes = len(proj_graph.get('nodes', []))
        edges = len(proj_graph.get('edges', []))
        if nodes > 0:
            self.stdout.write(self.style.SUCCESS('   [OK] 项目图谱查询成功'))
            self.stdout.write('   Nodes: ' + str(nodes) + ', Edges: ' + str(edges))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] 项目图谱为空'))
        
        # 6. 测试get_project_coverage_report
        self.stdout.write('\n6. 测试get_project_coverage_report...')
        coverage = get_project_coverage_report(1, limit=100)
        detail = coverage.get('detail')
        if not detail:
            summary = coverage.get('summary', {})
            self.stdout.write(self.style.SUCCESS('   [OK] 覆盖度报告生成成功'))
            self.stdout.write('   测试用例数: ' + str(summary.get('test_case_count', 0)))
            self.stdout.write('   有covers边的用例数: ' + str(summary.get('test_cases_with_covers', 0)))
            self.stdout.write('   覆盖的需求数: ' + str(summary.get('covered_requirement_count', 0)))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] ' + str(detail)))
        
        self.stdout.write(self.style.SUCCESS('\n=== 测试完成 ==='))
