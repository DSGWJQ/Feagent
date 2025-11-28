# 文件创建和组织规则

## 核心原则

**未经用户明确要求，禁止创建任何新文件（包括文档、测试文件、脚本等）**

## 规则说明

### 1. 文档创建规则

- ❌ **禁止**主动创建任何文档文件（.md, .txt, .doc 等）
- ❌ **禁止**创建 README、指南、总结、笔记等文档
- ❌ **禁止**创建测试指南、使用说明等辅助文档
- ✅ **仅当**用户明确要求"创建文档"、"写一个指南"等时才可创建
- ✅ 如果需要说明信息，直接在对话中告诉用户，不要写成文件

### 2. 测试文件创建规则

- ❌ **禁止**主动创建新的测试文件
- ❌ **禁止**为现有功能"补充"测试文件
- ✅ **仅当**用户明确要求"写测试"、"创建测试文件"时才可创建
- ✅ 优先更新现有测试文件，而不是创建新文件

### 3. 脚本和工具文件创建规则

- ❌ **禁止**主动创建辅助脚本（如 git_push.py, test_*.py 等）
- ❌ **禁止**创建"方便使用"的工具脚本
- ✅ **仅当**用户明确要求创建特定脚本时才可创建

### 4. 配置文件创建规则

- ✅ 可以创建项目必需的配置文件（如 package.json, tsconfig.json 等）
- ✅ 可以创建框架要求的文件（如 vite.config.ts, pytest.ini 等）
- ❌ **禁止**创建"可选"的配置文件

## 文件组织规范

### 项目根目录（`/`）

**应该包含**：
- `README.md` - 项目主文档（必需）
- `LICENSE` - 许可证文件
- `pyproject.toml` - Python 项目配置
- `alembic.ini` - 数据库迁移配置
- `.gitignore` - Git 忽略规则
- 数据库文件（`*.db`）- 开发环境数据库

**不应该包含**：
- ❌ 测试脚本（`test_*.py`）
- ❌ 临时文档（`*_NOTES.md`, `*_GUIDE.md`）
- ❌ 工具脚本（`git_push.py`, `git_push.bat`）

### 文档目录（`docs/`）

**应该包含**：
- 架构和开发指南（`ARCHITECTURE_GUIDE.md`, `DEVELOPMENT_GUIDE.md`）
- 需求和设计文档（`workflow_requirements.md`, `workflow_api_design.md`）
- 项目总结文档（`WORKFLOW_INTEGRATION_SUMMARY.md`）
- `archive/` - 归档的旧文档

**不应该包含**：
- ❌ 临时测试指南（应该在 `tests/manual/` 中）
- ❌ 开发过程笔记（应该删除或归档）

### 测试目录（`tests/`）

**结构**：
```
tests/
├── unit/           # 单元测试
├── integration/    # 集成测试
└── manual/         # 手动测试脚本
```

**手动测试脚本**（`tests/manual/`）：
- ✅ 用于手动验证功能的 Python 脚本
- ✅ 测试指南文档（如果需要）
- 命名：`test_*.py` 或 `check_*.py`

### 脚本目录（`scripts/`）

**应该包含**：
- 项目初始化脚本（`init-frontend.sh`, `init-frontend.ps1`）
- 启动脚本（`start_backend.bat`）
- 数据库初始化脚本
- 开发工具脚本

**不应该包含**：
- ❌ 临时测试脚本（应该在 `tests/manual/`）
- ❌ 一次性使用的脚本（用完即删）

## 文件移动规则

当发现文件位置不正确时：

1. **测试脚本**（`test_*.py`）
   - 从根目录移动到 `tests/manual/`
   - 或移动到 `tests/integration/`（如果是集成测试）

2. **文档文件**（`*_GUIDE.md`, `*_NOTES.md`）
   - 如果是重要文档，移动到 `docs/`
   - 如果是临时笔记，移动到 `docs/archive/misc/`
   - 如果是测试指南，移动到 `tests/manual/` 或删除

3. **工具脚本**（`git_push.py`, `*.bat`）
   - 移动到 `scripts/`
   - 或者删除（如果是临时脚本）

4. **日志和临时文件**
   - 移动到 `logs/` 或删除
   - 确保在 `.gitignore` 中忽略

## 执行步骤

当需要整理文件时：

1. **识别文件类型**：测试脚本、文档、工具脚本、临时文件
2. **确定目标位置**：根据上述规范确定应该放在哪里
3. **询问用户**：列出移动计划，询问用户是否同意
4. **执行移动**：使用 Git 命令移动文件（保留历史）
5. **更新引用**：检查并更新其他文件中的路径引用

## 示例

### 错误示例 ❌

```
项目根目录/
├── test_api.py                    # ❌ 应该在 tests/manual/
├── test_chat_api.py               # ❌ 应该在 tests/manual/
├── MANUAL_TEST_GUIDE.md           # ❌ 应该在 docs/ 或 tests/manual/
├── E2E_INTEGRATION_NOTES.md       # ❌ 应该在 docs/archive/
├── git_push.py                    # ❌ 应该在 scripts/
└── git_push.bat                   # ❌ 应该在 scripts/
```

### 正确示例 ✅

```
项目根目录/
├── README.md                      # ✅ 项目主文档
├── pyproject.toml                 # ✅ 项目配置
├── docs/
│   ├── ARCHITECTURE_GUIDE.md      # ✅ 架构指南
│   └── archive/                   # ✅ 归档文档
├── tests/
│   └── manual/
│       ├── test_api.py            # ✅ 手动测试脚本
│       └── test_chat_api.py       # ✅ 手动测试脚本
└── scripts/
    ├── git_push.py                # ✅ 工具脚本
    └── start_backend.bat          # ✅ 启动脚本
```

## 总结

- **默认不创建文件**：除非用户明确要求
- **保持根目录整洁**：只放必需的配置文件
- **分类组织文件**：测试、文档、脚本各归其位
- **定期清理**：删除临时文件和过时文档
