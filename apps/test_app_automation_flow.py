import time
import urllib.parse
import requests

BASE_URL = "http://localhost:8000/api"
USERNAME = "admin"          # TODO: 改成你的账号
PASSWORD = "lcy7683167"       # TODO: 改成你的密码


def api(method, path, token=None, **kwargs):
    """简单的 API 封装，出错时打印详细信息便于调试"""
    url = f"{BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)

    if not resp.ok:
        # 打印出错时的响应内容，方便看到具体报错
        print(f"\n[API ERROR] {method.upper()} {url}")
        print(f"Status: {resp.status_code}")
        try:
            print("Body:", resp.json())
        except ValueError:
            print("Body (raw):", resp.text)
        resp.raise_for_status()

    try:
        return resp.json()
    except ValueError:
        return {}


def login():
    data = {"username": USERNAME, "password": PASSWORD}
    # 后端认证接口为 /api/auth/login/
    res = api("post", "/auth/login/", json=data)
    return res["access"]


def create_project(token):
    data = {
        "name": "E2E APP 项目",
        "description": "自动化脚本创建的项目"
    }
    res = api("post", "/app-automation/projects/", token, json=data)

    # 创建接口返回的可能不包含 id，这里做一次兜底查询
    project_id = res.get("id")
    if project_id:
        return project_id

    # 按名称查最新的一个项目
    name_q = urllib.parse.quote(data["name"])
    list_res = api(
        "get",
        f"/app-automation/projects/?search={name_q}&ordering=-created_at&page=1",
        token,
    )
    results = list_res.get("results") or []
    if not results:
        raise RuntimeError(f"创建项目失败，返回数据为: {res}")
    return results[0]["id"]


def create_device(token, project_id):
    data = {
        # AppDevice 模型字段
        "device_id": "AUTO-DEVICE-001",
        "name": "虚拟设备-脚本",
        "status": "available",
        "android_version": "13",
        "connection_type": "emulator",
        "ip_address": "127.0.0.1",
        "port": 5555,
        "device_specs": {},
        "description": "E2E 自动化虚拟设备",
        "location": "E2E"
    }
    device_id = data["device_id"]

    # 1) 先查一下是否已存在该设备，避免重复创建
    list_res = api(
        "get",
        f"/app-automation/devices/?search={urllib.parse.quote(device_id)}&ordering=-created_at&page=1",
        token,
    )
    results = list_res.get("results") or []
    if results:
        # 已存在就直接复用
        return device_id

    # 2) 不存在时再尝试创建
    _ = api("post", "/app-automation/devices/", token, json=data)
    return device_id


def create_test_case(token, project_id, device_id):
    data = {
        "name": "E2E APP 用例",
        "project": project_id,
        "package_name": "com.example.demo",
        "steps": [
            {"order": 1, "action": "open_app", "params": {"package_name": "com.example.demo"}},
            {"order": 2, "action": "sleep", "params": {"seconds": 1}}
        ]
    }
    res = api("post", "/app-automation/test-cases/", token, json=data)
    case_id = res.get("id")
    if case_id:
        return case_id

    # 按名称查最新的一个用例
    name_q = urllib.parse.quote(data["name"])
    list_res = api(
        "get",
        f"/app-automation/test-cases/?search={name_q}&ordering=-created_at&page=1",
        token,
    )
    results = list_res.get("results") or []
    if not results:
        raise RuntimeError(f"创建用例失败，返回数据为: {res}")
    return results[0]["id"]


def create_suite(token, project_id, case_id):
    data = {
        "name": "E2E 套件",
        "project": project_id,
        "description": "脚本创建的回归套件"
    }
    suite = api("post", "/app-automation/test-suites/", token, json=data)
    suite_id = suite.get("id")
    if not suite_id:
        # 按名称查最新的一个套件
        name_q = urllib.parse.quote(data["name"])
        list_res = api(
            "get",
            f"/app-automation/test-suites/?search={name_q}&ordering=-created_at&page=1",
            token,
        )
        results = list_res.get("results") or []
        if not results:
            raise RuntimeError(f"创建套件失败，返回数据为: {suite}")
        suite_id = results[0]["id"]

    # 把用例加入套件
    api("post", f"/app-automation/test-suites/{suite_id}/add_test_case/", token,
        json={"test_case_id": case_id})
    return suite_id


def run_suite(token, suite_id, device_device_id):
    """触发套件执行；device_device_id 为 AppDevice.device_id 字符串"""
    res = api(
        "post",
        f"/app-automation/test-suites/{suite_id}/run/",
        token,
        json={"device_id": device_device_id},
    )
    # 后端一般会返回执行记录或任务信息
    return res.get("execution_id") or res.get("id")


def wait_execution(token, execution_id, timeout=600):
    start = time.time()
    while True:
        res = api("get", f"/app-automation/executions/{execution_id}/", token)
        status = res.get("status")
        result = res.get("result")
        print(f"execution {execution_id}: status={status}, result={result}")

        if status in ("completed", "error", "stopped"):
            return res

        if time.time() - start > timeout:
            raise TimeoutError("等待执行超时")

        time.sleep(5)


def main():
    token = login()
    print("登录成功")

    project_id = create_project(token)
    print("项目创建成功:", project_id)

    device_device_id = create_device(token, project_id)
    print("设备创建成功，device_id:", device_device_id)

    case_id = create_test_case(token, project_id, device_device_id)
    print("用例创建成功:", case_id)

    suite_id = create_suite(token, project_id, case_id)
    print("套件创建成功:", suite_id)

    execution_id = run_suite(token, suite_id, device_device_id)
    print("触发执行，执行ID:", execution_id)

    exec_detail = wait_execution(token, execution_id)
    print("执行结束:", exec_detail.get("status"), exec_detail.get("result"))

    # 如果有报告接口，也可以简单访问一下
    report_url = f"{BASE_URL}/app-automation/executions/{execution_id}/report/"
    r = requests.get(report_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    print("报告状态码:", r.status_code)


if __name__ == "__main__":
    main()