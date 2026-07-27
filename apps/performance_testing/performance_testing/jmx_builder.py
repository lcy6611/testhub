# -*- coding: utf-8 -*-
"""
JMX 构建：在线编排 → JMX；JMX 导入 → 解析 + 危险组件检测 + 参数覆盖。
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from xml.etree import ElementTree as ET
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DANGEROUS_COMPONENTS = ["JSR223", "BeanShell", "BeanShellSampler", "BSFSampler", "Groovy"]


def detect_dangerous_components(jmx_content: str) -> List[str]:
    """检测 JMX 中的危险脚本组件。"""
    found: List[str] = []
    if not jmx_content:
        return found
    lower = jmx_content
    for comp in DANGEROUS_COMPONENTS:
        if comp in lower:
            found.append(comp)
    return found


# XML 1.0 不支持的非法字符实体引用（JMeter 有时会写入 #x0-#x1F 等控制字符）
_INVALID_XML_HEX_ENTITY_RE = re.compile(r"&#x([0-9A-Fa-f]+);")
_INVALID_XML_DEC_ENTITY_RE = re.compile(r"&#(\d+);")


def _sanitize_jmx_content(content: str) -> str:
    """清理 JMX 中 XML 1.0 不支持的非法字符及其实体引用，避免标准库解析失败。"""

    def hex_repl(match: re.Match) -> str:
        code = int(match.group(1), 16)
        if code in (0x09, 0x0A, 0x0D):
            return match.group(0)
        return ""

    def dec_repl(match: re.Match) -> str:
        code = int(match.group(1))
        if code in (0x09, 0x0A, 0x0D):
            return match.group(0)
        return ""

    cleaned = _INVALID_XML_HEX_ENTITY_RE.sub(hex_repl, content)
    cleaned = _INVALID_XML_DEC_ENTITY_RE.sub(dec_repl, cleaned)
    # 同时清理字面控制字符（除 \t \n \r 外）
    cleaned = "".join(
        ch if ord(ch) >= 0x20 or ch in "\t\n\r" else "" for ch in cleaned
    )
    return cleaned


def _escape_xml(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _bool_str(val: bool) -> str:
    return "true" if val else "false"


class JMeterPlanBuilder:
    """从在线编排配置生成 JMX 文件。"""

    @staticmethod
    def build(
        config: Dict[str, Any],
        *,
        thread_count: int = 10,
        ramp_up: int = 5,
        duration: int = 60,
        backend_listener: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        """生成 JMX 文件，返回路径。"""
        output_dir = output_dir or tempfile.mkdtemp(prefix="perf_jmx_")
        os.makedirs(output_dir, exist_ok=True)
        jmx_path = os.path.join(output_dir, "plan.jmx")

        thread_groups = config.get("thread_groups") or []
        if not thread_groups:
            thread_groups = [{
                "name": "Thread Group",
                "thread_count": thread_count,
                "ramp_up": ramp_up,
                "duration": duration,
                "samplers": config.get("samplers") or [],
            }]

        parts: List[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
        parts.append('<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">')
        parts.append('  <hashTree>')

        # TestPlan 元素（JMeter 必须有）
        parts.append('    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan" enabled="true">')
        parts.append('      <stringProp name="TestPlan.comments"></stringProp>')
        parts.append('      <boolProp name="TestPlan.functional_mode">false</boolProp>')
        parts.append('      <boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>')
        parts.append('      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>')
        # 用户定义变量
        variables = config.get("variables") or []
        parts.append('      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">')
        parts.append('        <collectionProp name="Arguments.arguments">')
        for var in variables:
            vname = _escape_xml(str(var.get("name") or ""))
            vval = _escape_xml(str(var.get("value") or ""))
            parts.append(f'          <elementProp name="{vname}" elementType="Argument">')
            parts.append(f'            <stringProp name="Argument.name">{vname}</stringProp>')
            parts.append(f'            <stringProp name="Argument.value">{vval}</stringProp>')
            parts.append('            <stringProp name="Argument.metadata">=</stringProp>')
            parts.append('          </elementProp>')
        parts.append('        </collectionProp>')
        parts.append('      </elementProp>')
        parts.append('      <stringProp name="TestPlan.user_define_classpath"></stringProp>')
        parts.append('    </TestPlan>')
        parts.append('    <hashTree>')

        for tg in thread_groups:
            parts.append(JMeterPlanBuilder._render_thread_group(tg, thread_count, ramp_up, duration))

        if backend_listener:
            parts.append(JMeterPlanBuilder._render_backend_listener(backend_listener))

        parts.append('    </hashTree>')
        parts.append('  </hashTree>')
        parts.append('</jmeterTestPlan>')

        with open(jmx_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        return jmx_path

    @staticmethod
    def _render_thread_group(tg: Dict[str, Any], default_threads: int, default_ramp: int, default_duration: int) -> str:
        name = _escape_xml(tg.get("name") or "Thread Group")
        threads = int(tg.get("thread_count") or default_threads or 10)
        ramp = int(tg.get("ramp_up") or default_ramp or 5)
        duration = int(tg.get("duration") or default_duration or 60)
        loops = tg.get("loops")
        loops_str = str(loops) if loops is not None else "-1"

        lines: List[str] = []
        lines.append(f'    <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{name}" enabled="true">')
        lines.append('      <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>')
        lines.append(f'      <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">')
        lines.append(f'        <stringProp name="LoopController.loops">{loops_str}</stringProp>')
        lines.append('      </elementProp>')
        lines.append(f'      <stringProp name="ThreadGroup.num_threads">{threads}</stringProp>')
        lines.append(f'      <stringProp name="ThreadGroup.ramp_time">{ramp}</stringProp>')
        lines.append('      <boolProp name="ThreadGroup.scheduler">true</boolProp>')
        lines.append(f'      <stringProp name="ThreadGroup.duration">{duration}</stringProp>')
        lines.append('      <stringProp name="ThreadGroup.delay">0</stringProp>')
        lines.append('      <boolProp name="ThreadGroup.same_user_on_next_iteration">false</boolProp>')
        lines.append('    </ThreadGroup>')
        lines.append('    <hashTree>')

        # CSV 数据集
        for csv in tg.get("csv_datasets") or tg.get("csv_data") or (tg.get("csv_data_set") or []):
            lines.append(JMeterPlanBuilder._render_csv(csv))

        # Samplers
        for sampler in tg.get("samplers") or []:
            stype = (sampler.get("type") or "http").lower()
            if stype == "http":
                lines.append(JMeterPlanBuilder._render_http_sampler(sampler))

        return "\n".join(lines) + "\n    </hashTree>"

    @staticmethod
    def _render_http_sampler(s: Dict[str, Any]) -> str:
        name = _escape_xml(s.get("name") or "HTTP Request")
        method = (s.get("method") or "GET").upper()
        url = s.get("url") or ""
        path = s.get("path") or "/"
        host = s.get("host") or ""
        port = s.get("port") or ""
        protocol = s.get("protocol") or "http"
        if url and (not host or not path):
            from urllib.parse import urlparse
            p = urlparse(url)
            protocol = p.scheme or protocol
            host = p.hostname or host
            port = str(p.port) if p.port else port
            path = p.path or path
            if p.query:
                path = f"{path}?{p.query}"

        # 参数 / Headers 兼容 list[dict] 和 dict 两种写法
        raw_params = s.get("params") or []
        if isinstance(raw_params, dict):
            params_list = [(k, v) for k, v in raw_params.items()]
        else:
            params_list = [(p.get("name", ""), p.get("value", "")) for p in raw_params if isinstance(p, dict)]

        raw_headers = s.get("headers") or []
        if isinstance(raw_headers, dict):
            headers_list = [(k, v) for k, v in raw_headers.items()]
        else:
            headers_list = [(h.get("name", ""), h.get("value", "")) for h in raw_headers if isinstance(h, dict)]

        body = s.get("body") or ""

        lines: List[str] = []
        lines.append(f'      <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{name}" enabled="true">')
        lines.append(f'        <stringProp name="HTTPSampler.protocol">{_escape_xml(protocol)}</stringProp>')
        lines.append(f'        <stringProp name="HTTPSampler.domain">{_escape_xml(str(host))}</stringProp>')
        lines.append(f'        <stringProp name="HTTPSampler.port">{_escape_xml(str(port))}</stringProp>')
        lines.append(f'        <stringProp name="HTTPSampler.path">{_escape_xml(path)}</stringProp>')
        lines.append(f'        <stringProp name="HTTPSampler.method">{method}</stringProp>')
        lines.append('        <boolProp name="HTTPSampler.follow_redirects">true</boolProp>')
        lines.append('        <boolProp name="HTTPSampler.use_keepalive">true</boolProp>')

        if method in ("POST", "PUT", "PATCH", "DELETE") and body:
            # 任意方法都支持 body（前端可编辑；body 与 params 互斥，body 优先）
            lines.append(f'        <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>')
            lines.append('        <elementProp name="HTTPSampler.arguments" elementType="Arguments">')
            lines.append('          <collectionProp name="Arguments.arguments">')
            lines.append(f'            <elementProp name="" elementType="HTTPArgument">')
            lines.append(f'              <boolProp name="HTTPArgument.always_encode">false</boolProp>')
            lines.append(f'              <stringProp name="Argument.value">{_escape_xml(body)}</stringProp>')
            lines.append(f'              <stringProp name="Argument.metadata">=</stringProp>')
            lines.append(f'            </elementProp>')
            lines.append('          </collectionProp>')
            lines.append('        </elementProp>')
        elif params_list:
            lines.append('        <elementProp name="HTTPSampler.arguments" elementType="Arguments">')
            lines.append('          <collectionProp name="Arguments.arguments">')
            for k, v in params_list:
                k = k or ""
                v = v or ""
                lines.append(f'            <elementProp name="{_escape_xml(str(k))}" elementType="HTTPArgument">')
                lines.append(f'              <boolProp name="HTTPArgument.always_encode">true</boolProp>')
                lines.append(f'              <stringProp name="Argument.name">{_escape_xml(str(k))}</stringProp>')
                lines.append(f'              <stringProp name="Argument.value">{_escape_xml(str(v))}</stringProp>')
                lines.append(f'              <stringProp name="Argument.metadata">=</stringProp>')
                lines.append(f'              <stringProp name="HTTPArgument.use_equals">true</stringProp>')
                lines.append(f'            </elementProp>')
            lines.append('          </collectionProp>')
            lines.append('        </elementProp>')
        else:
            lines.append('        <elementProp name="HTTPSampler.arguments" elementType="Arguments">')
            lines.append('          <collectionProp name="Arguments.arguments"/>')
            lines.append('        </elementProp>')
        lines.append('      </HTTPSamplerProxy>')
        lines.append('      <hashTree>')

        # Headers
        if headers_list:
            lines.append('        <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="Headers" enabled="true">')
            lines.append('          <collectionProp name="HeaderManager.headers">')
            for k, v in headers_list:
                k = k or ""
                v = v or ""
                lines.append(f'            <elementProp name="" elementType="Header">')
                lines.append(f'              <stringProp name="Header.name">{_escape_xml(str(k))}</stringProp>')
                lines.append(f'              <stringProp name="Header.value">{_escape_xml(str(v))}</stringProp>')
                lines.append(f'            </elementProp>')
            lines.append('          </collectionProp>')
            lines.append('        </HeaderManager>')
            lines.append('        <hashTree/>')

        # 断言
        for assertion in s.get("assertions") or []:
            lines.append(JMeterPlanBuilder._render_assertion(assertion))

        # 定时器
        for timer in s.get("timers") or []:
            lines.append(JMeterPlanBuilder._render_timer(timer))

        lines.append('      </hashTree>')
        return "\n".join(lines)

    @staticmethod
    def _render_assertion(a: Dict[str, Any]) -> str:
        atype = (a.get("type") or "response_code").lower()
        if atype == "response_code":
            val = _escape_xml(str(a.get("value") or "200"))
            return (
                f'        <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="{_escape_xml(a.get("name") or "响应码断言")}" enabled="true">\n'
                '          <collectionProp name="Asserion.test_strings">\n'
                f'            <stringProp name="49586">{val}</stringProp>\n'
                '          </collectionProp>\n'
                '          <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>\n'
                '          <boolProp name="Assertion.assume_success">false</boolProp>\n'
                '          <intProp name="Assertion.test_type">8</intProp>\n'
                '        </ResponseAssertion>\n'
                '        <hashTree/>'
            )
        if atype in ("json", "json_path"):
            path = _escape_xml(str(a.get("path") or "$.code"))
            expected = _escape_xml(str(a.get("value") or ""))
            cond = a.get("condition") or "eq"
            return (
                '        <JSONPathAssertion guiclass="JSONPathAssertionGui" testclass="JSONPathAssertion" testname="JSON断言" enabled="true">\n'
                f'          <stringProp name="JSON_PATH">{path}</stringProp>\n'
                f'          <stringProp name="EXPECTED_VALUE">{expected}</stringProp>\n'
                f'          <boolProp name="JSONVALIDATION">{_bool_str(cond == "eq")}</boolProp>\n'
                '        </JSONPathAssertion>\n'
                '        <hashTree/>'
            )
        return ""

    @staticmethod
    def _render_timer(t: Dict[str, Any]) -> str:
        ttype = (t.get("type") or "constant").lower()
        if ttype == "constant":
            delay = int(t.get("delay") or 1000)
            return (
                '        <ConstantTimer guiclass="ConstantTimerGui" testclass="ConstantTimer" testname="定时器" enabled="true">\n'
                f'          <stringProp name="ConstantTimer.delay">{delay}</stringProp>\n'
                '        </ConstantTimer>\n'
                '        <hashTree/>'
            )
        return ""

    @staticmethod
    def _render_csv(csv: Dict[str, Any]) -> str:
        filename = _escape_xml(str(csv.get("filename") or csv.get("file") or "data.csv"))
        filename = os.path.basename(filename)
        var_names = _escape_xml(str(csv.get("variable_names") or csv.get("vars") or ""))
        delim = _escape_xml(str(csv.get("delimiter") or ","))
        return (
            '      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="CSV数据集" enabled="true">\n'
            f'        <stringProp name="filename">{filename}</stringProp>\n'
            f'        <stringProp name="variableNames">{var_names}</stringProp>\n'
            f'        <stringProp name="delimiter">{delim}</stringProp>\n'
            '        <boolProp name="quotedData">false</boolProp>\n'
            '        <boolProp name="recycle">true</boolProp>\n'
            '        <boolProp name="stopThread">false</boolProp>\n'
            '        <stringProp name="shareMode">shareMode.all</stringProp>\n'
            '      </CSVDataSet>\n'
            '      <hashTree/>'
        )

    @staticmethod
    def _render_backend_listener(cfg: Dict[str, Any]) -> str:
        url = _escape_xml(str(cfg.get("url") or "http://localhost:8086"))
        org = _escape_xml(str(cfg.get("org") or "testhub"))
        bucket = _escape_xml(str(cfg.get("bucket") or "jmeter"))
        token = _escape_xml(str(cfg.get("token") or ""))
        measurement = _escape_xml(str(cfg.get("measurement") or "jmeter"))
        application = _escape_xml(str(cfg.get("application") or "testhub"))
        return (
            '    <BackendListener guiclass="BackendListenerGui" testclass="BackendListener" testname="InfluxDB Backend" enabled="true">\n'
            '      <stringProp name="classname">org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient</stringProp>\n'
            '      <elementProp name="arguments" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" enabled="true">\n'
            '        <collectionProp name="Arguments.arguments">\n'
            f'          <elementProp name="influxdbMetricsSender" elementType="Argument">\n'
            '            <stringProp name="Argument.name">influxdbMetricsSender</stringProp>\n'
            '            <stringProp name="Argument.value">org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender</stringProp>\n'
            '          </elementProp>\n'
            f'          <elementProp name="influxdbUrl" elementType="Argument">\n'
            '            <stringProp name="Argument.name">influxdbUrl</stringProp>\n'
            f'            <stringProp name="Argument.value">{url}/api/v2/write?org={org}&amp;bucket={bucket}&amp;precision=ns</stringProp>\n'
            '          </elementProp>\n'
            f'          <elementProp name="influxdbToken" elementType="Argument">\n'
            '            <stringProp name="Argument.name">influxdbToken</stringProp>\n'
            f'            <stringProp name="Argument.value">{token}</stringProp>\n'
            '          </elementProp>\n'
            '          <elementProp name="measurement" elementType="Argument">\n'
            '            <stringProp name="Argument.name">measurement</stringProp>\n'
            f'            <stringProp name="Argument.value">{measurement}</stringProp>\n'
            '          </elementProp>\n'
            '          <elementProp name="application" elementType="Argument">\n'
            '            <stringProp name="Argument.name">application</stringProp>\n'
            f'            <stringProp name="Argument.value">{application}</stringProp>\n'
            '          </elementProp>\n'
            '          <elementProp name="summaryOnly" elementType="Argument">\n'
            '            <stringProp name="Argument.name">summaryOnly</stringProp>\n'
            '            <stringProp name="Argument.value">false</stringProp>\n'
            '          </elementProp>\n'
            '          <elementProp name="samplersRegex" elementType="Argument">\n'
            '            <stringProp name="Argument.name">samplersRegex</stringProp>\n'
            '            <stringProp name="Argument.value">.*</stringProp>\n'
            '          </elementProp>\n'
            '          <elementProp name="percentiles" elementType="Argument">\n'
            '            <stringProp name="Argument.name">percentiles</stringProp>\n'
            '            <stringProp name="Argument.value">90;95;99</stringProp>\n'
            '          </elementProp>\n'
            '        </collectionProp>\n'
            '      </elementProp>\n'
            '    </BackendListener>\n'
            '    <hashTree/>'
        )


# ==================== JMX 解析 → 在线编排配置 ====================

def _first_text(element: ET.Element, xpath: str, default: str = "") -> str:
    el = element.find(xpath)
    return el.text if el is not None else default


def _parse_headers(header_mgr: ET.Element) -> List[Dict[str, str]]:
    headers: List[Dict[str, str]] = []
    for h in header_mgr.findall(".//elementProp[@elementType='Header']"):
        name = _first_text(h, "stringProp[@name='Header.name']")
        value = _first_text(h, "stringProp[@name='Header.value']")
        if name or value:
            headers.append({"name": name, "value": value})
    return headers


def _parse_http_arguments(sampler: ET.Element):
    """返回 (body, params_list)。"""
    body = ""
    params: List[Dict[str, str]] = []
    args_container = sampler.find(".//elementProp[@name='HTTPSampler.arguments']")
    if args_container is None:
        return body, params

    post_raw = sampler.find("boolProp[@name='HTTPSampler.postBodyRaw']")
    is_body = post_raw is not None and post_raw.text == "true"

    for arg in args_container.findall(".//elementProp[@elementType='HTTPArgument']"):
        name = _first_text(arg, "stringProp[@name='Argument.name']")
        value = _first_text(arg, "stringProp[@name='Argument.value']")
        if is_body and not name:
            body = value
        else:
            params.append({"name": name, "value": value})
    return body, params


def _parse_hashtree(hashtree: Optional[ET.Element]) -> List[Dict[str, Any]]:
    """解析 JMeter 的 hashTree 子节点，返回组件列表。"""
    components: List[Dict[str, Any]] = []
    if hashtree is None:
        return components
    children = list(hashtree)
    i = 0
    while i < len(children):
        el = children[i]
        if el.tag == "hashTree":
            i += 1
            continue
        child_hash: Optional[ET.Element] = None
        if i + 1 < len(children) and children[i + 1].tag == "hashTree":
            child_hash = children[i + 1]
        comp = _parse_component(el, child_hash)
        if comp:
            components.append(comp)
        i += 2 if child_hash else 1
    return components


def _parse_component(el: ET.Element, child_hash: Optional[ET.Element]) -> Optional[Dict[str, Any]]:
    tag = el.tag
    if tag == "TestPlan":
        return _parse_testplan(el, child_hash)
    if tag == "ThreadGroup":
        return _parse_threadgroup(el, child_hash)
    if tag == "HTTPSamplerProxy":
        return _parse_http_sampler(el, child_hash)
    if tag == "CSVDataSet":
        return _parse_csv(el, child_hash)
    if tag == "HeaderManager":
        return {"type": "HeaderManager", "headers": _parse_headers(el)}
    if tag == "ResponseAssertion":
        return _parse_response_assertion(el, child_hash)
    if tag == "JSONPathAssertion":
        return _parse_jsonpath_assertion(el, child_hash)
    if tag == "ConstantTimer":
        return _parse_timer(el, child_hash)
    return None


def _parse_testplan(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    variables: List[Dict[str, str]] = []
    args = el.find(".//elementProp[@name='TestPlan.user_defined_variables']")
    if args is not None:
        for arg in args.findall(".//elementProp[@elementType='Argument']"):
            name = _first_text(arg, "stringProp[@name='Argument.name']")
            value = _first_text(arg, "stringProp[@name='Argument.value']")
            variables.append({"name": name, "value": value})

    thread_groups: List[Dict[str, Any]] = []
    csv_datasets: List[Dict[str, Any]] = []
    for child in _parse_hashtree(child_hash):
        ctype = child.get("type")
        if ctype == "ThreadGroup":
            thread_groups.append(child)
        elif ctype == "CSVDataSet":
            csv_datasets.append(child)
    return {
        "type": "TestPlan",
        "name": el.get("testname", "Test Plan"),
        "variables": variables,
        "thread_groups": thread_groups,
        "csv_datasets": csv_datasets,
    }


def _parse_threadgroup(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    tg: Dict[str, Any] = {
        "type": "ThreadGroup",
        "name": el.get("testname", "Thread Group"),
        "thread_count": 1,
        "ramp_up": 1,
        "duration": 60,
        "loops": -1,
        "variables": [],
        "csv_datasets": [],
        "samplers": [],
    }
    for prop in el.iter("stringProp"):
        name = prop.get("name", "")
        if name == "ThreadGroup.num_threads":
            tg["thread_count"] = int(prop.text or 1)
        elif name == "ThreadGroup.ramp_time":
            tg["ramp_up"] = int(prop.text or 1)
        elif name == "ThreadGroup.duration":
            tg["duration"] = int(prop.text or 60)
        elif name == "LoopController.loops":
            tg["loops"] = int(prop.text or -1)

    for child in _parse_hashtree(child_hash):
        ctype = child.get("type")
        if ctype == "CSVDataSet":
            tg["csv_datasets"].append(child)
        elif ctype == "HTTPSamplerProxy":
            tg["samplers"].append(child)
    return tg


def _parse_http_sampler(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    sampler: Dict[str, Any] = {
        "type": "HTTPSamplerProxy",
        "name": el.get("testname", "HTTP Request"),
        "method": "GET",
        "url": "",
        "headers": [],
        "params": [],
        "body": "",
        "assertions": [],
        "timers": [],
    }

    protocol = ""
    domain = ""
    port = ""
    path = ""
    for prop in el.iter("stringProp"):
        name = prop.get("name", "")
        if name == "HTTPSampler.protocol":
            protocol = prop.text or ""
        elif name == "HTTPSampler.domain":
            domain = prop.text or ""
        elif name == "HTTPSampler.port":
            port = prop.text or ""
        elif name == "HTTPSampler.path":
            path = prop.text or ""
        elif name == "HTTPSampler.method":
            sampler["method"] = (prop.text or "GET").upper()

    sampler["body"], sampler["params"] = _parse_http_arguments(el)

    if domain:
        url = f"{protocol}://{domain}" if protocol else domain
        if port:
            url += f":{port}"
        if path:
            url += path
        sampler["url"] = url
    elif path:
        sampler["url"] = path

    raw_assertions: List[Dict[str, Any]] = []
    for child in _parse_hashtree(child_hash):
        ctype = child.get("type")
        if ctype == "HeaderManager":
            sampler["headers"].extend(child.get("headers", []))
        elif ctype == "ResponseAssertion":
            raw_assertions.append(child)
        elif ctype == "JSONPathAssertion":
            raw_assertions.append(child)
        elif ctype == "ConstantTimer":
            sampler["timers"].append(child)

    for a in raw_assertions:
        if a["type"] == "ResponseAssertion":
            field = a.get("field", "")
            values = a.get("values", [])
            val = values[0] if values else ""
            if "response_code" in field:
                sampler["assertions"].append({"type": "response_code", "value": val})
            elif "response_data" in field:
                sampler["assertions"].append({"type": "contains", "value": val})
        elif a["type"] == "JSONPathAssertion":
            sampler["assertions"].append({"type": "json_path", "path": a.get("path", ""), "value": a.get("value", "")})
    return sampler


def _parse_csv(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    fname = _first_text(el, "stringProp[@name='filename']")
    return {
        "type": "CSVDataSet",
        "name": el.get("testname", "CSV数据集"),
        "file": os.path.basename(fname) if fname else "",
        "variable_names": _first_text(el, "stringProp[@name='variableNames']"),
        "delimiter": _first_text(el, "stringProp[@name='delimiter']", ","),
        "encoding": _first_text(el, "stringProp[@name='fileEncoding']", "UTF-8"),
    }


def _parse_response_assertion(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    values = [sp.text or "" for sp in el.findall("collectionProp[@name='Asserion.test_strings']/stringProp")]
    return {
        "type": "ResponseAssertion",
        "field": _first_text(el, "stringProp[@name='Assertion.test_field']"),
        "values": values,
    }


def _parse_jsonpath_assertion(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    return {
        "type": "JSONPathAssertion",
        "path": _first_text(el, "stringProp[@name='JSON_PATH']"),
        "value": _first_text(el, "stringProp[@name='EXPECTED_VALUE']"),
    }


def _parse_timer(el: ET.Element, child_hash: Optional[ET.Element]) -> Dict[str, Any]:
    return {"type": "ConstantTimer", "delay": int(_first_text(el, "stringProp[@name='ConstantTimer.delay']", "0"))}


def parse_jmx_to_config(jmx_file_path: str) -> Dict[str, Any]:
    """将 JMX 文件解析为在线编排配置（jmx_config）。"""
    with open(jmx_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = _sanitize_jmx_content(f.read())
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.warning("JMX 清理后仍解析失败: %s", exc)
        return {"variables": [], "csv_datasets": [], "thread_groups": []}

    config: Dict[str, Any] = {"variables": [], "csv_datasets": [], "thread_groups": []}
    root_ht = next((c for c in root if c.tag == "hashTree"), None)
    if root_ht is None:
        return config
    for comp in _parse_hashtree(root_ht):
        if comp.get("type") == "TestPlan":
            config["variables"] = comp.get("variables", [])
            config["csv_datasets"] = comp.get("csv_datasets", [])
            config["thread_groups"] = comp.get("thread_groups", [])
        elif comp.get("type") == "ThreadGroup":
            # 兜底：如果 ThreadGroup 出现在根层级也收进来
            config["thread_groups"].append(comp)
    return config


def _inject_backend_listener(root: ET.Element, cfg: Dict[str, Any]) -> None:
    """向 JMX 根 hashTree 注入 InfluxDB Backend Listener（若已存在则跳过）。"""
    # 检查是否已存在 BackendListener
    for bl in root.iter("BackendListener"):
        # 已存在，不再注入
        return

    backend_xml = JMeterPlanBuilder._render_backend_listener(cfg)
    # 解析为 Element 插入到根 hashTree 的末尾
    backend_el = ET.fromstring(backend_xml)
    root_ht = next((c for c in root if c.tag == "hashTree"), None)
    if root_ht is None:
        return
    # backend_xml 包含 BackendListener + <hashTree/>
    root_ht.append(backend_el)
    root_ht.append(ET.Element("hashTree"))


class UploadedJMXPlanBuilder:
    """JMX 导入：检测危险组件 + 覆盖线程数/CSV 路径等参数。"""

    @staticmethod
    def prepare(
        jmx_file_path: str,
        *,
        thread_count: int = 10,
        ramp_up: int = 5,
        duration: int = 60,
        backend_listener: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """返回 {ok, jmx_path, dangerous_components, warnings}。"""
        if not jmx_file_path or not os.path.exists(jmx_file_path):
            return {"ok": False, "error": "JMX 文件不存在"}

        with open(jmx_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        dangerous = detect_dangerous_components(content)
        warnings: List[str] = []
        if dangerous:
            warnings.append(f"检测到危险组件: {', '.join(dangerous)}，请确认脚本安全性")

        output_dir = output_dir or tempfile.mkdtemp(prefix="perf_jmx_")
        os.makedirs(output_dir, exist_ok=True)
        jmx_path = os.path.join(output_dir, "plan.jmx")
        modified = False

        try:
            cleaned = _sanitize_jmx_content(content)
            root = ET.fromstring(cleaned)
            # 覆盖线程数
            for tg in root.iter("ThreadGroup"):
                for prop in tg.iter("stringProp"):
                    name = prop.get("name", "")
                    if name == "ThreadGroup.num_threads":
                        prop.text = str(thread_count)
                        modified = True
                    elif name == "ThreadGroup.ramp_time":
                        prop.text = str(ramp_up)
                        modified = True
                    elif name == "ThreadGroup.duration":
                        prop.text = str(duration)
                        modified = True

            # 注入 Backend Listener（实时报告）
            if backend_listener:
                _inject_backend_listener(root, backend_listener)
                modified = True

            tree = ET.ElementTree(root)
            tree.write(jmx_path, encoding="utf-8", xml_declaration=True)
        except Exception as exc:
            logger.warning("JMX 解析覆盖失败，使用原始文件: %s", exc)
            import shutil
            shutil.copy2(jmx_file_path, jmx_path)

        return {
            "ok": True,
            "jmx_path": jmx_path,
            "dangerous_components": dangerous,
            "warnings": warnings,
            "modified": modified,
        }
