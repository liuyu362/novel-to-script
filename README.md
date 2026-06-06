# novel-to-script

AI 辅助小说转剧本工具，将小说文本自动转换为结构化剧本（YAML 格式），降低改编门槛，提升创作效率。

## 目录结构

```
novel-to-script/
├── backend/                 # FastAPI 后端
│   ├── app.py              # 主应用入口，路由定义
│   ├── llm_client.py       # LLM API 调用封装（OpenAI 兼容接口）
│   ├── novel_analyzer.py   # 小说文本分析
│   ├── chapter_splitter.py # 章节智能拆分
│   ├── character_extractor.py  # 角色信息提取
│   ├── scene_extractor.py  # 场景提取
│   ├── dialogue_separator.py   # 对话分离
│   ├── fusion_script.py    # 剧本融合生成
│   ├── schema.py           # 剧本 YAML Schema 定义（v2.1）
│   ├── yaml_parser.py      # YAML 解析
│   ├── yaml_validator.py   # YAML 校验与自动修复
│   ├── logic_checker.py    # 逻辑一致性检测
│   ├── version_prompts.py # 多版本（电影/电视剧/舞台剧）Prompt 模板
│   ├── user_manager.py     # 用户注册/登录/JWT 鉴权
│   ├── works_manager.py    # 作品管理（CRUD）
│   ├── config.py           # 配置管理
│   ├── json_utils.py       # JSON 解析容错工具
│   ├── errors.py           # 统一错误处理
│   └── prompts.py         # 基础 Prompt 模板
├── frontend/               # 纯前端（无构建工具）
│   ├── index.html          # 主界面（单页应用，含所有 CSS/JS）
│   └── login.html          # 登录/注册独立页面
├── docs/
│   └── YAML-Schema-设计文档.md  # Schema 设计说明
├── .env                    # 环境变量（不提交，见 .env.example）
├── requirements.txt         # Python 依赖
└── README.md
```

## 功能特性

- **用户系统**：注册/登录，JWT 鉴权，多用户隔离
- **小说管理**：上传小说、章节拆分、元数据提取
- **角色提取**：自动识别角色姓名、性别、性格、简介
- **场景提取**：自动识别场景地点、时间、参与角色
- **剧本生成**：AI 生成结构化 YAML 剧本，支持电影版/电视剧版/舞台剧版
- **多版本 Prompt**：不同版本独立优化 Prompt，提升生成质量
- **剧本编辑**：前端直接编辑 YAML 剧本，实时保存
- **逻辑检测**：检测查找文本是否在替换后剧本中缺失，自动修复
- **YAML 校验**：自动校验并修复 Schema 合法性
- **Schema v2.1 专业字段**：景别、角度、运动、转场、标准场景标题行（Slugline）、角色入场/退场标记

## 技术栈

### 后端
- **框架**：FastAPI + Uvicorn
- **LLM**：OpenAI API 兼容接口（支持 DeepSeek 等）
- **认证**：PyJWT（HS256 签名）
- **数据格式**：PyYAML
- **配置**：python-dotenv

### 前端
- **技术**：原生 HTML + CSS + JavaScript（无框架依赖）
- **样式**：CSS 变量体系、毛玻璃效果、动画过渡
- **存储**：localStorage（用户会话 + 作品草稿）

## 依赖清单

### Python（后端）
```
fastapi>=0.115.0
uvicorn>=0.30.0
openai>=1.60.0
python-dotenv>=1.0.1
pyyaml>=6.0.2
PyJWT>=2.8.0
```

### 前端
无第三方依赖，全部使用原生 Web API。

## 安装与运行

### 1. 克隆仓库

```bash
git clone https://github.com/liuyu362/novel-to-script.git
cd novel-to-script
```

### 2. 配置后端

```bash
cd backend
pip install -r requirements.txt
```

创建 `.env` 文件（参考 `.env.example`）：

```env
# LLM API 配置（OpenAI 兼容接口）
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或你的 LLM 端点
MODEL_NAME=deepseek-chat                      # 模型名称

# JWT 签名密钥（生产环境请更换）
JWT_SECRET=your-secret-key-here

# 服务端口
PORT=8000
```

### 3. 启动后端

```bash
cd backend
```

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问 `http://localhost:8000/docs` 可查看 API 文档。

## 使用流程

1. **注册/登录** → 打开 `login.html`，注册账号并登录
2. **上传小说** → 进入"上传分析"页，粘贴或上传小说文本
3. **确认角色/场景** → AI 自动提取，可手动调整
4. **生成剧本** → 选择版本（电影/电视剧/舞台剧），点击生成
5. **编辑剧本** → 在 YAML 编辑器中直接修改，支持撤销/复制/下载
6. **逻辑检测** → 使用"查找替换"功能时自动检测逻辑一致性

## YAML Schema

剧本使用结构化 YAML 格式，Schema 定义见 `docs/YAML-Schema-设计文档.md`。

**设计原因**：YAML 可读性强、支持注释、LLM 生成质量高，适合作为剧本初稿的人工编辑格式。Schema 面向剪辑思维设计，包含场景、角色、对话、动作指示，以及 v2.1 新增的专业拍摄字段（景别/角度/运动/转场/Slugline/入场退场）。

## API 端点概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录（返回 JWT） |
| POST | `/api/analyze` | 分析小说（提取角色/场景） |
| POST | `/api/generate-script` | 生成剧本 |
| GET | `/api/works` | 获取作品列表 |
| POST | `/api/works` | 保存作品 |
| PUT | `/api/works/{id}` | 更新作品 |
| DELETE | `/api/works/{id}` | 删除作品 |

除注册/登录外，所有接口需在 Header 中携带 `Authorization: Bearer <token>`。

## Demo 视频

> 待上传

## 开发记录

- 全程通过 Pull Request 持续交付，每个 PR 只做一件事
- PR 描述遵循规范：标题一句话 + 功能描述 + 实现思路 + 测试方式
- 主要 PR 序列：PR33（前后端鉴权）→ PR34（逻辑检测修复）→ PR35（JWT 替换）→ PR36（Schema v2.1 专业字段）→ PR37（前端美化）

## 许可

MIT License
