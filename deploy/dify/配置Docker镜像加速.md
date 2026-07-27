# 配置 Docker Desktop 镜像加速（解决无法拉取镜像）

当出现 `registry-1.docker.io` 超时、`Image Interrupted` 时，多为无法直连 Docker Hub。给 Docker 配置**镜像加速**后，拉取会走国内镜像，再重新运行 `install-and-start.bat` 即可。

---

## 步骤（Windows Docker Desktop）

1. **打开 Docker Desktop**，确保已启动（托盘图标无转圈）。

2. **打开设置**  
   右上角 **齿轮图标（Settings）** → 左侧选 **Docker Engine**。

3. **修改 JSON 配置**  
   在编辑框里找到或新增 **`registry-mirrors`**。若已有其他配置，只增加或合并该段，不要删掉已有内容。

   **示例（保留原有大括号和逗号）：**

   ```json
   {
     "registry-mirrors": [
       "https://dockerproxy.com",
       "https://docker.m.daocloud.io",
       "https://docker.1panel.live",
       "https://hub-mirror.c.163.com",
       "https://mirror.baidubce.com"
     ],
     "builder": { "gc": { "defaultKeepStorage": "20GB", "enabled": true } },
     "experimental": false
   }
   ```
   **注意**：JSON 中数组或对象**最后一项后面不能有逗号**，否则会报错无法应用。

   - 若当前只有 `{}`，把上面整段粘贴进去即可。  
   - 若已有 `"builder"`、`"experimental"` 等，只加 `"registry-mirrors"` 这一段，并注意上一行末尾加逗号。

4. **保存并重启**  
   点击 **Apply & restart**，等 Docker 重启完成（托盘图标就绪）。

5. **重新运行安装脚本**  
   在项目根目录执行：
   ```cmd
   deploy\dify\install-and-start.bat
   ```

---

## 若仍拉取失败

- **换一个镜像**：删掉或注释掉当前 `registry-mirrors` 里不生效的地址，换成别的（如阿里云个人加速地址，需在阿里云容器镜像服务里开通）。  
- **用离线包**：在能访问 Docker Hub 的电脑上运行 `deploy\dify\export-images.bat`，把生成的 **deploy\dify\offline** 拷到本机，再运行 `deploy\dify\import-and-start.bat`（见 README「方式二：离线安装」）。
