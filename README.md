# 基于官方 mcp 接口实现

https://app.api.cloud.mxchip.com:2443/oauth2/mcp/oauth

# 多乐信除湿机 HTTP 接口

用户提供 mxchip `Authorization`，执行 `python main.py`，服务就会启动并暴露两个 HTTP 接口。

## 启动

```bash
AUTHORIZATION='Bearer <你的Token>' python main.py
```

首次运行会自动将锁定依赖安装到当前目录的 `.packages/`，缺少 pip 时自动准备，无需先安装 mcpo。不复制项目、不创建另一套启动目录、不注册服务。后续启动直接复用已安装的依赖。

如果希望每次只执行 `python main.py`，复制 `.env.example` 为 `.env`，填入 Authorization 即可：

```dotenv
AUTHORIZATION=Bearer <你的Token>
```

也可以直接运行 `python main.py`，按提示隐藏输入 Authorization。

默认监听 `0.0.0.0:8000`，以前台进程运行。服务管理和自启动由用户自己的工具负责。

## 其他设备调用

将下面的 `服务器IP` 换成运行本项目机器 IP。

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

## 可选配置

环境变量或 `.env` 均可配置：

| 名称 | 用途 | 默认值 |
| --- | --- | --- |
| `AUTHORIZATION` | 用户自己的 mxchip 上游凭据 | 必填，未提供时隐藏询问 |
| `HOST` | HTTP 监听地址 | `0.0.0.0` |
| `PORT` | HTTP 端口 | `8000` |
| `API_KEY` | 其他设备调用接口时使用的可选密钥 | 不启用调用端鉴权 |

仅设置 `AUTHORIZATION` 时，其他设备直接调用以上两个接口即可。设置 `API_KEY` 后，调用方增加 `Authorization: Bearer <API_KEY>` 请求头；上游的 mxchip Token 不需要提供给调用设备。

## 代码

- `main.py`：唯一启动入口，准备依赖、读取 Authorization 并启动 mcpo。
- `dehumidifier_mcp.py`：定义两个 MCP 工具，调用 mxchip 并校验设备回读。
- `requirements.in` / `requirements.txt`：依赖声明和锁定版本。
- `test_main.py`：启动配置和依赖准备测试。

调用关系：`python main.py` → mcpo HTTP 服务 → 两个 MCP 工具 → mxchip → 除湿机。

mcpo 会自动启动工具子进程，无需用户另起进程。实际 HTTP 转换由 `main.py` 中的 `from mcpo import app` 完成。

## 来源

- [mcpo 官方仓库](https://github.com/open-webui/mcpo)：stdio MCP 工具转换为普通 HTTP 接口。
- [pip 官方安装说明](https://pip.pypa.io/en/stable/installation/)：缺少 pip 时使用官方 `get-pip.py`。
- [pip 安装参数](https://pip.pypa.io/en/stable/cli/pip_install/)：依赖安装至项目目录的 `--target` 方式。
