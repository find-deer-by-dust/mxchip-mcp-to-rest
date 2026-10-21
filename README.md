# 多乐信除湿机 HTTP 接口

基于 mxchip MCP 服务，将多乐信除湿机的“连续干衣”和“舒适睡眠”两个固定操作暴露为 HTTP 接口。配置自己的 mxchip `Authorization` 后，可通过 Docker Compose 一键启动，也可执行 `python main.py` 启动服务。

## 使用前提

- **Docker 方式**：docker compose up -d --build
- **直接运行 Python**：需要 **Python 3.11 或更新版本**，并有项目目录的写入权限。先执行 `python --version` 确认；低于 3.11 时程序会直接退出。
- 首次构建镜像或直接运行 Python 时需要联网下载依赖。日常控制需要运行服务的容器或主机能访问 `app.api.cloud.mxchip.com` 的 HTTPS `2443` 端口。
- Token 所属账号下，必须恰好有一台名称为 **`多乐信除湿机`**、类别为 `DEHUMIDIFIER` 的设备，且设备在线。设备改名、没有匹配设备或有多台同名同类设备，都会导致调用失败。
- 设备的 `mode` 属性必须可写，且包含 `1=连续`、`4=舒适`。程序会校验这些定义；当前没有通过配置指定设备名称或设备 ID 的功能。

## 获取 Authorization

1. 打开 [mxchip 智家精灵 MCP 接入页面](https://app.api.cloud.mxchip.com:2443/oauth2/mcp/oauth)。
2. 使用已绑定目标设备的智家精灵账号登录，点击“登录并生成接入凭证”。
3. 登录成功后，在页面预览的 MCP 配置中找到 `headers.Authorization`，复制其中的 `Bearer <实际Token>`，按下面的启动步骤填写。

上述链接用于登录获取凭据；程序实际调用的 MCP 地址是 `https://app.api.cloud.mxchip.com:2443/mcp`，使用 Streamable HTTP 协议。

当前程序不会自动获取或刷新 Token。Token 失效后，需要重新获取凭据、更新 `AUTHORIZATION`，然后按下方对应启动方式重新应用配置。

## 启动

### 1. 配置 Authorization

在项目目录中操作，推荐使用 `.env` 保存配置。

Linux / macOS（Bash）：

```bash
cp .env.example .env
```

Windows（PowerShell）：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，将占位符替换为上一步获取的真实凭据：

```dotenv
AUTHORIZATION=Bearer <你的Token>
```

### 2. 使用 Docker Compose 启动（推荐）

完成上述配置后，在项目目录执行：

```bash
docker compose up -d --build
```

首次执行会拉取 Python 3.12 基础镜像并安装锁定依赖，后续启动复用镜像。依赖在构建时准备好，容器启动时无需再次下载；服务以非 root 用户运行。`.env` 和本地依赖缓存不会进入镜像，配置由 Compose 注入容器。

默认接口文档为 `http://服务器IP:8000/dehumidifier/docs`。

健康检查仅访问本地 HTTP 文档页面，不会控制设备，也不代表上游 Token 有效或设备在线。

修改 `.env`（包括更新 Token）后，执行 `docker compose up -d` 重新创建受配置变化影响的容器；`docker compose restart` 不会加载新的环境变量。更新项目代码或依赖后，执行 `docker compose up -d --build` 重新构建并启动。

Compose 使用 `.env` 中的 `HOST`、`PORT` 设置**宿主机端口绑定**；容器内部固定监听 `0.0.0.0:8000`。例如配置 `PORT=18000` 后，访问 `http://服务器IP:18000/dehumidifier/docs`；设置 `HOST=127.0.0.1` 可将宿主机端口限制为仅本机访问。未填写或留空 `AUTHORIZATION` 时，Compose 会直接提示错误，需要先提供凭据。

### 3. 直接运行 Python（可选）

完成上述 `.env` 配置后，在项目目录执行：

```bash
python main.py
```

首次运行会自动将锁定依赖安装到**项目目录**的 `.packages/`，缺少 pip 时自动准备，无需先安装 mcpo。后续启动在依赖文件和 Python 版本未变化时复用已安装的依赖。服务以前台进程运行，可按 `Ctrl+C` 停止；服务管理和自启动由用户自己的工具负责。

也可以通过环境变量提供凭据。

Linux / macOS（Bash）：

```bash
AUTHORIZATION='Bearer <你的Token>' python main.py
```

Windows（PowerShell）：

```powershell
$env:AUTHORIZATION = 'Bearer <你的Token>'
python main.py
```

同名环境变量优先于 `.env`，Docker Compose 也遵循这一规则。如果已在终端设置 `AUTHORIZATION`，修改 `.env` 后还需要同步更新或清除该环境变量，再重新应用配置。直接运行 Python 时，两处均未提供凭据，程序会提示隐藏输入 Authorization。

默认监听 `0.0.0.0:8000`，即所有网络接口。未设置 `API_KEY` 时，能连接到该端口的设备都可调用这两个控制接口；监听地址和调用密钥可在下方配置。

## 其他设备调用

将下面的 `服务器IP` 换成运行本项目机器的实际 IP，并确保调用设备能访问对应端口。本机调用可用 `127.0.0.1`。Windows PowerShell 请使用 `curl.exe` 执行下面的 curl 命令。

```bash
# 连续干衣
curl -X POST http://服务器IP:8000/dehumidifier/continuous_drying

# 舒适睡眠
curl -X POST http://服务器IP:8000/dehumidifier/comfort_sleep
```

| 方法 | 路径 | 设备模式 |
| --- | --- | --- |
| POST | `/dehumidifier/continuous_drying` | 连续干衣：设备连续档 `mode=1` |
| POST | `/dehumidifier/comfort_sleep` | 舒适睡眠：设备舒适档 `mode=4` |

接口不需要请求参数。必要时开机，设置模式并回读确认后返回 `success=true, confirmed=true`，同时返回实际工作状态、湿度和温度。设备没有额外睡眠档，舒适睡眠使用“舒适”模式。

接口文档：`http://服务器IP:8000/dehumidifier/docs`。

### 成功响应

HTTP `200`，返回 JSON 对象。以下为连续干衣的结构示例，非真实设备读数；工作状态、湿度和温度取自设备回读，缺失的属性值为 `null`：

```json
{
  "success": true,
  "confirmed": true,
  "preset": "continuous_drying",
  "device": "多乐信除湿机",
  "online": true,
  "power": 1,
  "mode": 1,
  "work_status": null,
  "current_humidity": null,
  "current_temperature": null
}
```

舒适睡眠成功时，`preset` 为 `comfort_sleep`，`mode` 为 `4`。上游提供属性标签时，还会返回对应的 `*_label` 字段，例如 `mode_label`。

`confirmed=true` 表示回读确认设备已开机且模式符合请求；实际工作状态由 `work_status` 及其可选标签表示。

### 失败响应与排查

调用方应先检查 HTTP 状态码，只有收到成功响应且 `success`、`confirmed` 均为 `true` 时，才视为操作已确认完成。失败由 mcpo 返回 HTTP 错误和 `detail` 信息，不保证返回 `success=false`。

| 常见 HTTP 状态 | 含义与处理 |
| --- | --- |
| `401` | 已启用 `API_KEY`，但调用方缺少有效的 Bearer 请求头；补充下方示例中的请求头。 |
| `403` | 调用方提供的 `API_KEY` 不匹配；核对服务端和调用端的密钥。 |
| `500` | 工具执行或连接失败；检查错误详情、上游 Token、设备匹配条件、设备在线状态及网络连接。上游 Token 失效也可能表现为此错误。 |

例如，调用密钥错误时返回 HTTP `403`：

```json
{
  "detail": "Invalid API key"
}
```

工具执行失败时，锁定版本 mcpo 可能返回如下 HTTP `500` 结构，`error` 的具体内容以实际响应为准：

```json
{
  "detail": {
    "message": "Unexpected error",
    "error": "<工具执行错误详情>"
  }
}
```

错误详情中的 `Expected exactly one matching Dorosin dehumidifier` 表示设备匹配数量不符合要求；`Device mode definitions differ from the verified presets` 表示设备模式定义不兼容；`Dehumidifier is unavailable or offline` 表示设备不可用或离线。

**失败不代表设备没有变化。** 开机或设置模式可能已部分成功，随后才因控制动作失败、网络中断或回读未确认而报错。程序不会自动回滚；遇到此类错误，先在原设备 App 中确认实际状态，再决定是否重试。回读最多尝试 10 次，期间还有上游网络请求，因此不要将调用超时简单设为 10 秒。

## 可选配置

环境变量或项目目录下的 `.env` 均可配置；环境变量优先。修改后，Docker Compose 执行 `docker compose up -d`，直接运行 Python 时重启进程：

| 名称 | 用途 | 默认值 |
| --- | --- | --- |
| `AUTHORIZATION` | 用户自己的 mxchip 上游凭据，支持裸 Token 或 `Bearer <Token>` | 必填；Compose 缺失时报错，直接运行 Python 时隐藏询问 |
| `HOST` | Compose 的宿主机绑定地址；直接运行 Python 时为 HTTP 监听地址 | `0.0.0.0` |
| `PORT` | Compose 的宿主机端口；直接运行 Python 时为 HTTP 端口，范围 `1`–`65535` | `8000` |
| `API_KEY` | 其他设备调用接口时使用的可选密钥 | 不启用调用端鉴权 |

仅设置 `AUTHORIZATION` 时，其他设备直接调用以上两个接口即可。设置 `API_KEY` 后，调用方增加 `Authorization: Bearer <API_KEY>` 请求头；上游的 mxchip Token 不需要提供给调用设备。

```bash
curl -X POST http://服务器IP:8000/dehumidifier/continuous_drying -H "Authorization: Bearer <API_KEY>"
```

## 代码

- `main.py`：唯一启动入口，准备依赖、读取 Authorization 并启动 mcpo。
- `dehumidifier_mcp.py`：定义两个 MCP 工具，调用 mxchip 并校验设备回读。
- `requirements.in` / `requirements.txt`：依赖声明和锁定版本。
- `Dockerfile` / `.dockerignore`：构建包含锁定依赖的运行镜像，并限制构建上下文。
- `compose.yaml`：一键构建启动、环境变量注入、端口映射、健康检查及自动重启。
- `test_main.py`：启动配置和依赖准备测试。

调用关系：`python main.py` → mcpo HTTP 服务 → 两个 MCP 工具 → mxchip → 除湿机。

mcpo 会自动启动工具子进程，无需用户另起进程。实际 HTTP 转换由 `main.py` 中的 `from mcpo import app` 完成。

## 来源

- [mxchip 智家精灵 MCP 接入页面](https://app.api.cloud.mxchip.com:2443/oauth2/mcp/oauth)：登录获取上游 Token 及 MCP 接入参数。
- [mcpo 官方仓库](https://github.com/open-webui/mcpo)：stdio MCP 工具转换为普通 HTTP 接口。
- [mcpo 0.0.20 工具响应处理](https://github.com/open-webui/mcpo/blob/v0.0.20/src/mcpo/utils/main.py) / [调用密钥校验](https://github.com/open-webui/mcpo/blob/v0.0.20/src/mcpo/utils/auth.py)：本文 HTTP 响应与鉴权说明对应项目锁定版本。
- [pip 官方安装说明](https://pip.pypa.io/en/stable/installation/)：缺少 pip 时使用官方 `get-pip.py`。
- [pip 安装参数](https://pip.pypa.io/en/stable/cli/pip_install/)：依赖安装至项目目录的 `--target` 方式。
- [Docker Compose 安装说明](https://docs.docker.com/compose/install/) / [环境变量插值](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) / [服务配置](https://docs.docker.com/reference/compose-file/services/)：Compose 安装、`.env` 配置、端口映射和重启策略。

## 许可证

本项目自有代码采用 [MIT License](LICENSE)。
第三方依赖遵循各自的许可证。