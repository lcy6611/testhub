#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试知识图谱边管理功能（管理命令）"""
from django.core.management.base import BaseCommand
from apps.knowledge_graph.models import KgEntity, KgEdge
from apps.knowledge_graph.edge_ops import (
    create_manual_kg_edge,
    list_kg_edges_for_entity,
    confirm_suggested_kg_edges,
    reject_suggested_kg_edges,
    list_pending_suggested_edges
)
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = '测试知识图谱边管理功能'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== 知识图谱边管理功能测试 ===\n'))
        
        # 获取admin用户
        admin = User.objects.get(username='admin')
        
        # 1. 测试list_kg_edges_for_entity
        self.stdout.write('1. 测试list_kg_edges_for_entity...')
        tc23 = KgEntity.objects.get(entity_key='tc:23')
        edges = list_kg_edges_for_entity('tc:23', direction='both')
        entity_info = edges.get('entity')
        if entity_info:
            outgoing = len(edges.get('outgoing', []))
            incoming = len(edges.get('incoming', []))
            self.stdout.write(self.style.SUCCESS('   [OK] 边列表查询成功'))
            self.stdout.write('   Outgoing: ' + str(outgoing) + ', Incoming: ' + str(incoming))
        else:
            self.stdout.write(self.style.ERROR('   [FAIL] 实体不存在'))
        
        # 2. 测试create_manual_kg_edge
        self.stdout.write('\n2. 测试create_manual_kg_edge...')
        try:
            # 创建一个测试边
            doc_entity = KgEntity.objects.filter(entity_type='KbDocument', project_id=1).first()
            if doc_entity:
                edge = create_manual_kg_edge(
                    src=tc23,
                    dst=doc_entity,
                    relation_type='covers',
                    project_id=1,
                    created_by=admin,
                    meta={'test': 'manual'}
                )
                self.stdout.write(self.style.SUCCESS('   [OK] 手动创建边成功'))
                self.stdout.write('   Edge: ' + edge.src.entity_key + ' -[' + edge.relation_type + ']-> ' + edge.dst.entity_key)
            else:
                self.stdout.write(self.style.WARNING('   [SKIP] 没有KbDocument实体'))
        except Exception as e:
            self.stdout.write(self.style.ERROR('   [FAIL] ' + str(e)))
        
        # 3. 测试list_pending_suggested_edges
        self.stdout.write('\n3. 测试list_pending_suggested_edges...')
        pending = list_pending_suggested_edges(limit=100)
        self.stdout.write('   待确认边数: ' + str(len(pending)))
        if len(pending) > 0:
            self.stdout.write(self.style.SUCCESS('   [OK] 有待确认的边'))
        else:
            self.stdout.write(self.style.WARNING('   [INFO] 没有待确认的边'))
        
        # 4. 查看所有边
        self.stdout.write('\n4. 项目1的所有边...')
        all_edges = KgEdge.objects.filter(project_id=1)
        self.stdout.write('   边数: ' + str(all_edges.count()))
        for edge in all_edges[:10]:
            self.stdout.write('   - ' + edge.src.entity_key + ' -[' + edge.relation_type + ']-> ' + edge.dst.entity_key + ' (source=' + edge.source + ')')
        
        self.stdout.write(self.style.SUCCESS('\n=== 测试完成 ==='))
