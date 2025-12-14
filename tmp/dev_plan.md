# TDD开发计划：后端测试补充

**基于文档**: `docs/testing/BACKEND_TESTING_PLAN.md`
**创建时间**: 2025-12-14
**目标**: 根据测试计划文档补充P0优先级测试

---

## 1. 需求分析摘要

根据测试计划文档分析：

### 当前状态
- **总体覆盖率**: 14.9% (目标: 50%)
- **失败测试数**: 29-239个（环境依赖）
- **核心问题**: 测试隔离、TDD Red阶段测试未门禁

### P0任务（本次重点）
1. 排除`tests/manual/`从pytest收集
2. 标记TDD Red测试为xfail
3. 添加网络mock装饰器（可选）
4. 修复FastAPI测试依赖覆盖（可选）

---

## 2. P0任务详情

### Task 1: 排除manual目录 ✅
**预计时间**: 15min
**文件**: `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
ignore = ["tests/manual"]  # 新增
```

**验收**: pytest收集不包含manual目录测试

### Task 2: 标记TDD Red测试
**预计时间**: 30min
**影响**: 消除58个预期失败

**方法**: 为开发中测试添加 `@pytest.mark.xfail` 或 `@pytest.mark.skip`

###Task 3: Mock外部服务（可选）
**预计时间**: 1-2h
**文件**: `tests/conftest.py`

```python
@pytest.fixture(autouse=True)
def mock_external_services(request):
    """自动mock外部服务调用"""
    if "integration" not in str(request.fspath):
        with patch("requests.get"), patch("requests.post"):
            yield
    else:
        yield
```

### Task 4: FastAPI依赖覆盖（可选）
**预计时间**: 2-4h
**文件**: `tests/integration/api/scheduler/*`

**问题**: 集成测试创建了内存DB但未注入到app

**修复**: 使用`app.dependency_overrides`

---

## 3. 实施步骤

### Step 1: 排除manual目录 ✅
- [ ] 修改: `pyproject.toml` 添加ignore配置
- [ ] 验证: `pytest --collect-only | grep manual` 无结果
- [ ] 验证: `pytest` 运行不收集manual测试

### Step 2: 标记TDD Red测试
- [ ] 识别: 查看lastfailed找出TDD Red测试
- [ ] 标记: 添加xfail/skip标记
- [ ] 验证: pytest无预期失败

### Step 3: Mock外部服务（可选）
- [ ] 修改: `tests/conftest.py` 添加autouse fixture
- [ ] 验证: 运行单元测试确认无外部调用
- [ ] 验证: 集成测试不受影响

### Step 4: FastAPI依赖覆盖（可选）
- [ ] 修改: scheduler测试添加dependency override
- [ ] 验证: 34个API测试通过

---

## 4. 验收标准

### P0完成标准（最小可行）
- [ ] pytest收集不包含manual目录
- [ ] TDD Red测试被正确标记（无预期失败）
- [ ] 运行pytest失败数显著减少

### P0+完成标准（理想状态）
- [ ] 单元测试无外部网络依赖
- [ ] API集成测试使用内存数据库
- [ ] 所有测试通过（0失败）

---

## 5. 进度跟踪

**当前阶段**: Phase 1 - 探索与规划 ✅
**下一步**: Phase 3 - TDD实施P0-Task1

### 里程碑
- [ ] M1: P0完成 (本次)
- [ ] M2: CI绿灯 (Week 1 Day 2)

---

**文档版本**: 1.0
**最后更新**: 2025-12-14
