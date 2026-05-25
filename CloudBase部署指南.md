# CloudBase 云托管部署指南

将 春夏体适能 系统部署到腾讯云 CloudBase 云托管（Serverless 容器）。

## 架构说明

```
你电脑 git push → GitHub/工蜂
                       ↓
CloudBase 云托管检测 Dockerfile → 自动构建镜像 → 部署容器
                       ↓
            CFS 文件存储（/data）持久化：
              - fitness.db    SQLite 数据库
              - uploads/      二维码 + 训练照片
```

需持久化的文件通过 **CFS（Cloud File Storage）** 挂载到容器的 `/data` 目录。

---

## 第一步：开通 CloudBase

1. 访问 [https://console.cloud.tencent.com/tcb](https://console.cloud.tencent.com/tcb)
2. 新建环境 → 选择「按量计费」→ 环境名称自定义
3. 等待 2-3 分钟环境初始化

## 第二步：开通 CFS 文件存储

1. CloudBase 控制台 → 左侧「文件管理」→「文件存储(CFS)」
2. 点击开通 → 选择「通用性能型」
3. 记录下 CFS ID（类似 `cfs-xxxxxx`）

## 第三步：部署代码

### 方式 A：使用 CloudBase CLI（推荐）

```bash
# 1. 安装 CLI
npm install -g @cloudbase/cli

# 2. 登录
tcb login

# 3. 在项目目录初始化
cd /Volumes/增元/项目/fitness-h5
tcb init

# 4. 部署到云托管
tcb cloudrun deploy
```

CLI 会自动读取 Dockerfile 构建并部署。

### 方式 B：控制台手动部署

1. CloudBase 控制台 →「云托管」→「新建服务」
2. 服务名：`fitness`
3. 部署方式：从源代码仓库
4. 关联你的 Git 仓库（GitHub/Gitee/工蜂）
5. 指定 Dockerfile 路径：`./Dockerfile`
6. 点击「部署」

## 第四步：挂载 CFS

部署完成后：

1. 进入云托管 → 服务 `fitness` →「版本管理」
2. 点击当前版本 →「编辑配置」
3. 找到「文件存储」→ 添加挂载：
   - CFS 实例：选之前创建的
   - 挂载路径：`/data`
4. 保存，容器会自动重启

## 第五步：配置环境变量

云托管 → 服务 `fitness` →「环境变量」：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `FITNESS_COACH_PASSWORD` | `你的密码` | 教练登录密码 |
| `PUBLIC_BASE_URL` | `https://xxx.run.tcloudbase.com` | 公网域名（部署后自动生成） |
| `SECRET_KEY` | `随机字符串` | Flask session 密钥 |
| `LLM_API_KEY` | `sk-xxx` | DeepSeek API Key |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | LLM API 地址 |
| `LLM_MODEL` | `deepseek-chat` | LLM 模型名 |
| `DATA_DIR` | `/data` | 持久化数据目录 |

## 第六步：验证

1. 访问 CloudBase 分配的域名（`https://xxx.run.tcloudbase.com`）
2. 教练登录 `/login` → 用设置的密码
3. 确认数据库/上传功能正常
4. 确认 LLM 内容生成正常（群内容中心 → AI 生成）

## 成本预估

| 项目 | 费用 |
|------|------|
| 云托管计算 | 新用户有免费额度（1-2月），之后约 ¥0.0001/秒 |
| CFS 文件存储 | 约 ¥35/月（100GB 通用型） |
| 外网流量 | 很低，一般 ¥5-20/月 |

> 头两个月几乎免费（新用户赠金）。正式运行后约 **¥40-60/月**。

## 本地测试 Docker 构建

```bash
cd /Volumes/增元/项目/fitness-h5
docker build -t fitness .
docker run -p 8080:8080 -e DATA_DIR=/data -v $(pwd)/local_data:/data fitness
# 访问 http://localhost:8080
```
