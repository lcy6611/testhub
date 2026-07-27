<template>
  <div class="perf-config-page">
    <el-page-header title="性能测试配置" @back="$router.push('/configuration')" />

    <el-card class="config-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>全局配置</span>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
        </div>
      </template>

      <el-form :model="form" label-position="top" label-width="auto">
        <h4>JMeter 配置</h4>
        <el-row :gutter="20">
          <el-col :span="18">
            <el-form-item label="JMeter 可执行路径">
              <el-input v-model="form.jmeter_path" placeholder="例如 /opt/apache-jmeter-5.6.3/bin/jmeter 或 E:\\apache-jmeter-5.6.3\\bin\\jmeter.bat" clearable />
              <div class="form-tip">留空则使用环境变量 JMETER_PATH 或 PATH 中的 jmeter</div>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="最大线程数">
              <el-input-number v-model="form.max_threads" :min="1" :max="10000" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="最大持续时间（秒）">
              <el-input-number v-model="form.max_duration" :min="1" :max="86400" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider />

        <h4>实时报告（InfluxDB 2.x）</h4>
        <el-form-item>
          <el-checkbox v-model="form.realtime_report_enabled">启用实时报告</el-checkbox>
          <el-button v-show="form.realtime_report_enabled" type="info" size="small" style="margin-left: 12px;" @click="fillDefaultInfluxdb">一键填入 Docker 默认配置</el-button>
        </el-form-item>

        <el-alert v-show="form.realtime_report_enabled" type="info" :closable="false" style="margin-bottom: 16px;">
          <div>使用 Docker Compose 部署时，后端和 JMeter 均在容器内运行，InfluxDB 地址应填 <code>http://influxdb:8086</code>（Docker 内部网络），Org=testhub，Bucket=jmeter，Token=testhub-influxdb-token。</div>
          <div style="margin-top: 8px;"><strong>注意：</strong>实时报告仅在执行时勾选「启用实时报告」才会写入 InfluxDB。配置页仅保存连接信息，不会强制所有执行都开启实时报告。</div>
        </el-alert>

        <el-row :gutter="20" v-show="form.realtime_report_enabled">
          <el-col :span="12">
            <el-form-item label="InfluxDB URL">
              <el-input v-model="form.influxdb_url" placeholder="http://influxdb:8086" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Token">
              <el-input v-model="form.influxdb_token" placeholder="influxdb-token" clearable show-password />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20" v-show="form.realtime_report_enabled">
          <el-col :span="6">
            <el-form-item label="Org">
              <el-input v-model="form.influxdb_org" placeholder="testhub" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Bucket">
              <el-input v-model="form.influxdb_bucket" placeholder="jmeter" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Measurement">
              <el-input v-model="form.influxdb_measurement" placeholder="jmeter" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Application">
              <el-input v-model="form.influxdb_application" placeholder="testhub" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item v-show="form.realtime_report_enabled">
          <el-button type="success" :loading="testing" @click="handleTestInfluxdb">测试连接</el-button>
        </el-form-item>

        <el-divider />

        <h4>服务器监控（Prometheus）</h4>
        <el-form-item>
          <el-checkbox v-model="form.prometheus_enabled">启用 Prometheus 监控</el-checkbox>
          <el-button v-show="form.prometheus_enabled" type="info" size="small" style="margin-left: 12px;" @click="fillDefaultPrometheus">一键填入 Docker 默认</el-button>
        </el-form-item>

        <el-alert v-show="form.prometheus_enabled" type="info" :closable="false" style="margin-bottom: 16px;">
          <div>使用 Docker Compose 部署时，若 Prometheus 与后端同网络，地址填 <code>http://prometheus:9090</code>；跨机部署填可访问的 http://IP:9090。</div>
          <div style="margin-top: 8px;">执行性能测试后，平台会按执行时间窗自动采集下方监控目标的资源指标，并展示在报告与执行详情中。</div>
        </el-alert>

        <el-row :gutter="20" v-show="form.prometheus_enabled">
          <el-col :span="16">
            <el-form-item label="Prometheus URL">
              <el-input v-model="form.prometheus_url" placeholder="http://prometheus:9090" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="采集步长(秒)">
              <el-input-number v-model="form.prometheus_step" :min="1" :max="300" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item v-show="form.prometheus_enabled">
          <el-button type="success" :loading="testingP" @click="handleTestPrometheus">测试连接</el-button>
        </el-form-item>

        <div v-show="form.prometheus_enabled">
          <h4>监控目标</h4>
          <el-table :data="form.monitor_targets" border size="small" style="margin-bottom: 12px;">
            <el-table-column label="名称" width="160">
              <template #default="{ row }">
                <el-input v-model="row.name" placeholder="如 应用服务器1" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="140">
              <template #default="{ row }">
                <el-select v-model="row.type" size="small" placeholder="类型">
                  <el-option label="应用服务器" value="app_server" />
                  <el-option label="网关" value="gateway" />
                  <el-option label="Redis/缓存" value="redis" />
                  <el-option label="数据库" value="db" />
                  <el-option label="自定义微服务" value="custom" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="instance（Prometheus 标签值）">
              <template #default="{ row }">
                <el-input v-model="row.instance" placeholder="如 10.0.59.110:9100" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="job（可选）" width="150">
              <template #default="{ row }">
                <el-input v-model="row.job" placeholder="node / mysql" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row, $index }">
                <el-button type="danger" link size="small" @click="removeTarget($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" plain size="small" @click="addTarget">+ 添加监控目标</el-button>
          <div class="form-tip" style="margin-top: 8px;">
            instance 为 Prometheus 中 node_exporter / mysqld_exporter 的 instance 标签值（通常 host:port）；数据库类型会自动采集连接数 / QPS / 行锁等待 / 缓冲池命中率等指标。
          </div>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPerformanceConfig, updatePerformanceConfig, testInfluxdbConnection, testPrometheusConnection } from '@/api/performance'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testingP = ref(false)

const defaultForm = {
  jmeter_path: '',
  max_threads: 1000,
  max_duration: 7200,
  realtime_report_enabled: false,
  influxdb_url: '',
  influxdb_org: 'testhub',
  influxdb_bucket: 'jmeter',
  influxdb_token: '',
  influxdb_measurement: 'jmeter',
  influxdb_application: 'testhub',
  prometheus_enabled: false,
  prometheus_url: '',
  prometheus_step: 15,
  monitor_targets: [],
}

const form = ref({ ...defaultForm })

async function loadConfig() {
  loading.value = true
  try {
    const res = await getPerformanceConfig()
    const data = res.data || {}
    form.value = { ...defaultForm, ...data }
  } catch (e) {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await updatePerformanceConfig(form.value)
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

function fillDefaultInfluxdb() {
  form.value.influxdb_url = 'http://influxdb:8086'
  form.value.influxdb_org = 'testhub'
  form.value.influxdb_bucket = 'jmeter'
  form.value.influxdb_token = 'testhub-influxdb-token'
  form.value.influxdb_measurement = 'jmeter'
  form.value.influxdb_application = 'testhub'
  ElMessage.info('已填入 Docker 默认配置，请根据实际部署修改')
}

async function handleTestInfluxdb() {
  if (!form.value.influxdb_url) {
    ElMessage.warning('请先填写 InfluxDB URL')
    return
  }
  if (!form.value.influxdb_token) {
    ElMessage.warning('请先填写 InfluxDB Token')
    return
  }
  testing.value = true
  try {
    const res = await testInfluxdbConnection({
      influxdb_url: form.value.influxdb_url,
      influxdb_token: form.value.influxdb_token,
      influxdb_org: form.value.influxdb_org,
      influxdb_bucket: form.value.influxdb_bucket,
    })
    if (res.data?.ok) {
      ElMessage.success(res.data.message || '连接成功')
    } else {
      ElMessage.error(res.data?.message || '连接失败')
    }
  } catch (e) {
    ElMessage.error('测试连接请求失败')
  } finally {
    testing.value = false
  }
}

function fillDefaultPrometheus() {
  form.value.prometheus_url = 'http://prometheus:9090'
  form.value.prometheus_step = 15
  ElMessage.info('已填入 Docker 默认配置，请根据实际部署修改')
}

function addTarget() {
  if (!Array.isArray(form.value.monitor_targets)) {
    form.value.monitor_targets = []
  }
  form.value.monitor_targets.push({ name: '', type: 'app_server', instance: '', job: '' })
}

function removeTarget(index) {
  form.value.monitor_targets.splice(index, 1)
}

async function handleTestPrometheus() {
  if (!form.value.prometheus_url) {
    ElMessage.warning('请先填写 Prometheus URL')
    return
  }
  testingP.value = true
  try {
    const res = await testPrometheusConnection({ prometheus_url: form.value.prometheus_url })
    if (res.data?.ok) {
      ElMessage.success(res.data.message || '连接成功')
    } else {
      ElMessage.error(res.data?.message || '连接失败')
    }
  } catch (e) {
    ElMessage.error('测试连接请求失败')
  } finally {
    testingP.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.perf-config-page {
  padding: 20px;
}

.config-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

h4 {
  margin: 16px 0 12px;
  color: var(--el-text-color-primary);
}
</style>
