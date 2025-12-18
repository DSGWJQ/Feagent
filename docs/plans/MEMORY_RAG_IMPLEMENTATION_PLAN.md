# Memory + RAG 集成实施计划

## 📋 总体目标

实现一个生产级的 **Memory + RAG** 系统，具备：
- ✅ 统一的 Memory 接口抽象
- ✅ 数据库 + 缓存双写机制（原子性）
- ✅ TTL 缓存自动回溯
- ✅ 工作记忆压缩 + 长期记忆向量化
- ✅ RAG 个人知识库隔离
- ✅ 性能监控（命中率、回溯耗时）

---

## 🎯 架构设计

### 架构分层（严格遵循 DDD）

```
┌─────────────────────────────────────────────────────────┐
│                 Interface Layer                          │
│  - 监控 API (metrics, cache_stats)                       │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Application Layer                           │
│  - CompositeMemoryService (组合模式编排)                  │
│  - MemoryMetricsCollector (监控指标)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 Domain Layer                             │
│  Ports (Pure Python Protocols):                         │
│  - MemoryProvider (抽象接口)                             │
│  - MemoryCache (缓存接口)                                │
│  - MemoryCompressor (压缩策略)                           │
│                                                          │
│  Entities:                                               │
│  - WorkingMemory (工作记忆值对象)                         │
│  - MemoryMetrics (监控指标值对象)                         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│           Infrastructure Layer                           │
│  Adapters (Implementations):                            │
│  - DatabaseMemoryStore (实现 MemoryProvider)             │
│  - InMemoryCache (实现 MemoryCache + TTL)                │
│  - TFIDFCompressor (实现 MemoryCompressor)               │
│  - EmbeddingIndexBuilder (向量索引构建)                   │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 数据流设计

### 1️⃣ 写入流程（原子双写）

```
User Message
    │
    ▼
CompositeMemoryService.append(message)
    │
    ├─1️⃣─► DatabaseMemoryStore.save(message)  [DB 事务]
    │        ├─ Success → commit
    │        └─ Failure → rollback + raise exception
    │
    └─2️⃣─► InMemoryCache.put(workflow_id, message)
             ├─ Success → update last_access_time
             └─ Failure → log warning + mark cache as invalid
```

**原子性保证：**
- DB 写入失败 → 抛出异常，整个操作回滚
- Cache 写入失败 → 记录日志，标记缓存失效（下次读取触发回溯）

---

### 2️⃣ 读取流程（缓存优先 + 自动回溯）

```
CompositeMemoryService.load_recent(workflow_id, last_n)
    │
    ▼
InMemoryCache.get(workflow_id)
    │
    ├─ Cache Hit + TTL Valid
    │   └─► Return cached messages (快速路径)
    │
    └─ Cache Miss / TTL Expired / Invalid
        │
        ▼
      DatabaseMemoryStore.find_by_workflow_id(workflow_id, limit=100)
        │
        ▼
      MemoryCompressor.compress(messages, max_tokens=4000)
        ├─ 1️⃣ TF-IDF 计算重要性得分
        ├─ 2️⃣ 保留最近 min_messages 条
        ├─ 3️⃣ 移除低分消息直到满足 token 限制
        └─ 4️⃣ 返回压缩后的消息列表
        │
        ▼
      InMemoryCache.put(workflow_id, compressed_messages)
        │
        ▼
      Return compressed_messages
```

**缓存策略：**
- TTL: 15 分钟（可配置）
- 最大容量：1000 个 workflow（LRU 淘汰）
- 每个 workflow 最多缓存 50 条消息

---

### 3️⃣ 搜索流程（向量 + 关键词混合）

```
CompositeMemoryService.search(query, workflow_id)
    │
    ├─1️⃣─► InMemoryCache.search_index(query)
    │        └─ 倒排索引 + TF-IDF 快速匹配
    │             └─► Top 20 candidates
    │
    └─2️⃣─► EmbeddingIndexBuilder.vector_search(query_embedding)
             ├─ ChromaDB 向量相似度搜索
             └─► Top 10 results
    │
    ▼
Merge + Rerank (RRF 算法)
    └─► Final Top 5 results
```

---

## 📝 分阶段实施计划（TDD 驱动）

### Phase 1: Domain 层 - 纯接口定义（2 文件）

**目标：** 定义核心抽象，无任何框架依赖

#### 1.1 定义 MemoryProvider Protocol

**文件：** `src/domain/ports/memory_provider.py`

```python
from typing import Protocol
from src.domain.entities.chat_message import ChatMessage

class MemoryProvider(Protocol):
    """Memory 统一接口抽象"""

    def append(self, message: ChatMessage) -> None:
        """追加消息到记忆中"""
        ...

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        """加载最近 N 条消息"""
        ...

    def search(self, query: str, workflow_id: str, threshold: float = 0.5) -> list[tuple[ChatMessage, float]]:
        """搜索相关消息"""
        ...

    def clear(self, workflow_id: str) -> None:
        """清空指定 workflow 的记忆"""
        ...
```

#### 1.2 定义 MemoryCache Protocol

**文件：** `src/domain/ports/memory_cache.py`

```python
from typing import Protocol
from src.domain.entities.chat_message import ChatMessage

class MemoryCache(Protocol):
    """缓存接口抽象"""

    def get(self, workflow_id: str) -> list[ChatMessage] | None:
        """获取缓存（None 表示未命中或过期）"""
        ...

    def put(self, workflow_id: str, messages: list[ChatMessage]) -> None:
        """更新缓存"""
        ...

    def invalidate(self, workflow_id: str) -> None:
        """主动失效"""
        ...

    def is_valid(self, workflow_id: str) -> bool:
        """检查缓存是否有效"""
        ...
```

**TDD 步骤：**
1. 写测试（RED）：`tests/unit/domain/ports/test_memory_provider.py`
   - 测试 Protocol 是否可被正确继承
   - 测试方法签名是否符合预期
2. 实现接口（GREEN）
3. 重构（REFACTOR）

---

### Phase 2: Infrastructure 层 - 适配器实现（3 文件）

#### 2.1 DatabaseMemoryStore（现有 Repository 的包装）

**文件：** `src/infrastructure/memory/database_memory_store.py`

```python
from src.domain.ports.memory_provider import MemoryProvider
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.domain.entities.chat_message import ChatMessage

class DatabaseMemoryStore:
    """数据库持久化存储（实现 MemoryProvider）"""

    def __init__(self, repository: ChatMessageRepository):
        self._repository = repository

    def append(self, message: ChatMessage) -> None:
        """写入数据库（带异常处理）"""
        try:
            self._repository.save(message)
        except Exception as e:
            # 记录日志 + 重新抛出
            raise DatabaseWriteError(f"Failed to save message: {e}") from e

    def load_recent(self, workflow_id: str, last_n: int = 10) -> list[ChatMessage]:
        messages = self._repository.find_by_workflow_id(workflow_id, limit=last_n * 2)
        return messages[-last_n:]  # 只取最近 N 条

    def search(self, query: str, workflow_id: str, threshold: float = 0.5) -> list[tuple[ChatMessage, float]]:
        return self._repository.search(workflow_id, query, threshold)

    def clear(self, workflow_id: str) -> None:
        self._repository.delete_by_workflow_id(workflow_id)
```

**TDD 步骤：**
1. 写测试（RED）：`tests/unit/infrastructure/memory/test_database_memory_store.py`
   - 测试正常写入
   - 测试异常处理
   - 测试读取逻辑
2. 实现（GREEN）
3. 重构（REFACTOR）

---

#### 2.2 InMemoryCache（TTL + LRU）

**文件：** `src/infrastructure/memory/in_memory_cache.py`

```python
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict
from src.domain.entities.chat_message import ChatMessage

@dataclass
class CacheEntry:
    """缓存条目"""
    messages: list[ChatMessage]
    last_access: datetime
    is_valid: bool = True

class InMemoryCache:
    """基于内存的 TTL 缓存（LRU 淘汰策略）"""

    def __init__(
        self,
        ttl_seconds: int = 900,  # 15 分钟
        max_workflows: int = 1000,
        max_messages_per_workflow: int = 50
    ):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_workflows = max_workflows
        self._max_messages = max_messages_per_workflow
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # 监控指标
        self._hits = 0
        self._misses = 0

    def get(self, workflow_id: str) -> list[ChatMessage] | None:
        """获取缓存（检查 TTL）"""
        if workflow_id not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[workflow_id]

        # 检查 TTL
        if datetime.utcnow() - entry.last_access > self._ttl:
            self._misses += 1
            del self._cache[workflow_id]
            return None

        # 检查有效性标记
        if not entry.is_valid:
            self._misses += 1
            return None

        # 命中：更新访问时间 + LRU 移动
        entry.last_access = datetime.utcnow()
        self._cache.move_to_end(workflow_id)
        self._hits += 1

        return entry.messages.copy()

    def put(self, workflow_id: str, messages: list[ChatMessage]) -> None:
        """更新缓存（LRU 淘汰）"""
        # 限制消息数量
        trimmed_messages = messages[-self._max_messages:]

        # 更新或插入
        self._cache[workflow_id] = CacheEntry(
            messages=trimmed_messages,
            last_access=datetime.utcnow()
        )
        self._cache.move_to_end(workflow_id)

        # LRU 淘汰
        while len(self._cache) > self._max_workflows:
            self._cache.popitem(last=False)  # 移除最旧的

    def invalidate(self, workflow_id: str) -> None:
        """标记失效（不删除，触发下次回溯）"""
        if workflow_id in self._cache:
            self._cache[workflow_id].is_valid = False

    def is_valid(self, workflow_id: str) -> bool:
        """检查缓存有效性"""
        if workflow_id not in self._cache:
            return False
        entry = self._cache[workflow_id]
        return entry.is_valid and (datetime.utcnow() - entry.last_access <= self._ttl)

    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "cached_workflows": len(self._cache),
            "ttl_seconds": self._ttl.total_seconds()
        }
```

**TDD 步骤：**
1. 写测试（RED）：`tests/unit/infrastructure/memory/test_in_memory_cache.py`
   - 测试基本 get/put
   - 测试 TTL 过期
   - 测试 LRU 淘汰
   - 测试 invalidate
   - 测试统计指标
2. 实现（GREEN）
3. 重构（REFACTOR）

---

#### 2.3 TFIDFCompressor（智能压缩）

**文件：** `src/infrastructure/memory/tfidf_compressor.py`

```python
from collections import Counter
import math
from src.domain.entities.chat_message import ChatMessage

class TFIDFCompressor:
    """基于 TF-IDF 的消息重要性评估器"""

    def compress(
        self,
        messages: list[ChatMessage],
        max_tokens: int = 4000,
        min_messages: int = 2
    ) -> list[ChatMessage]:
        """压缩消息列表到指定 token 限制"""

        if len(messages) <= min_messages:
            return messages

        # 1. 计算每条消息的 token 数
        message_tokens = [self._estimate_tokens(msg.content) for msg in messages]
        total_tokens = sum(message_tokens)

        if total_tokens <= max_tokens:
            return messages

        # 2. 计算 TF-IDF 分数
        scores = self._calculate_tfidf_scores(messages)

        # 3. 按时间倒序排序（保留最近的）
        sorted_indices = list(range(len(messages)))
        sorted_indices.sort(key=lambda i: messages[i].timestamp, reverse=True)

        # 4. 贪心选择：优先保留最近 + 高分消息
        selected = []
        current_tokens = 0

        # 强制保留最近 min_messages 条
        for i in range(min(min_messages, len(messages))):
            idx = sorted_indices[i]
            selected.append(idx)
            current_tokens += message_tokens[idx]

        # 按分数选择剩余消息
        remaining = [(idx, scores[idx]) for idx in sorted_indices[min_messages:]]
        remaining.sort(key=lambda x: x[1], reverse=True)

        for idx, score in remaining:
            if current_tokens + message_tokens[idx] <= max_tokens:
                selected.append(idx)
                current_tokens += message_tokens[idx]
            else:
                break

        # 5. 按时间顺序返回
        selected.sort()
        return [messages[i] for i in selected]

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量（启发式）"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.3 + other_chars / 4)

    def _calculate_tfidf_scores(self, messages: list[ChatMessage]) -> list[float]:
        """计算每条消息的 TF-IDF 分数"""
        # 构建词频表
        all_words = []
        message_words = []

        for msg in messages:
            words = self._tokenize(msg.content)
            message_words.append(words)
            all_words.extend(words)

        # 计算 IDF
        word_doc_count = Counter()
        for words in message_words:
            word_doc_count.update(set(words))

        num_docs = len(messages)
        idf = {word: math.log(num_docs / count) for word, count in word_doc_count.items()}

        # 计算每条消息的 TF-IDF 得分
        scores = []
        for words in message_words:
            word_count = Counter(words)
            total_words = len(words)

            if total_words == 0:
                scores.append(0.0)
                continue

            tfidf_sum = sum(
                (count / total_words) * idf.get(word, 0.0)
                for word, count in word_count.items()
            )
            scores.append(tfidf_sum)

        return scores

    def _tokenize(self, text: str) -> list[str]:
        """简单分词（空格分隔 + 中文字符）"""
        words = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                words.append(char)
        words.extend(text.split())
        return [w for w in words if w.strip()]
```

**TDD 步骤：**
1. 写测试（RED）：`tests/unit/infrastructure/memory/test_tfidf_compressor.py`
   - 测试无需压缩场景
   - 测试 token 限制生效
   - 测试 min_messages 保证
   - 测试 TF-IDF 分数计算
2. 实现（GREEN）
3. 重构（REFACTOR）

---

### Phase 3: Application 层 - 组合编排（1 文件）

#### 3.1 CompositeMemoryService（核心编排）

**文件：** `src/application/services/composite_memory_service.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore
from src.infrastructure.memory.in_memory_cache import InMemoryCache
from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor

logger = logging.getLogger(__name__)

@dataclass
class MemoryMetrics:
    """内存操作指标"""
    cache_hit_rate: float
    fallback_count: int
    compression_ratio: float
    avg_fallback_time_ms: float
    last_updated: datetime = field(default_factory=datetime.utcnow)

class CompositeMemoryService:
    """组合式内存服务（双写 + 回溯 + 压缩）"""

    def __init__(
        self,
        db_store: DatabaseMemoryStore,
        cache: InMemoryCache,
        compressor: TFIDFCompressor,
        max_context_tokens: int = 4000
    ):
        self._db = db_store
        self._cache = cache
        self._compressor = compressor
        self._max_tokens = max_context_tokens

        # 监控指标
        self._fallback_times = []
        self._compression_ratios = []

    def append(self, message: ChatMessage) -> None:
        """原子双写：DB → Cache"""

        # 1. 写入数据库（失败则抛异常）
        try:
            self._db.append(message)
        except Exception as e:
            logger.error(f"Database write failed for message {message.id}: {e}")
            raise

        # 2. 更新缓存（失败不影响主流程）
        try:
            # 读取当前缓存
            cached = self._cache.get(message.workflow_id)
            if cached is None:
                cached = []

            # 追加新消息
            cached.append(message)

            # 更新缓存
            self._cache.put(message.workflow_id, cached)
        except Exception as e:
            logger.warning(f"Cache write failed for workflow {message.workflow_id}: {e}")
            # 标记缓存失效，触发下次回溯
            self._cache.invalidate(message.workflow_id)

    def load_recent(
        self,
        workflow_id: str,
        last_n: int = 10
    ) -> list[ChatMessage]:
        """加载最近消息（缓存优先 + 自动回溯）"""

        # 1. 尝试从缓存读取
        cached = self._cache.get(workflow_id)
        if cached is not None:
            logger.debug(f"Cache hit for workflow {workflow_id}")
            return cached[-last_n:]

        # 2. 缓存未命中 → 回溯到数据库
        logger.info(f"Cache miss for workflow {workflow_id}, falling back to database")

        start_time = datetime.utcnow()

        # 3. 从数据库加载
        messages = self._db.load_recent(workflow_id, last_n=100)  # 多取一些用于压缩

        if not messages:
            return []

        # 4. 压缩（如果超过 token 限制）
        original_count = len(messages)
        compressed = self._compressor.compress(
            messages,
            max_tokens=self._max_tokens,
            min_messages=min(2, last_n)
        )

        # 5. 更新缓存
        self._cache.put(workflow_id, compressed)

        # 6. 记录指标
        fallback_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        self._fallback_times.append(fallback_time)

        compression_ratio = len(compressed) / original_count if original_count > 0 else 1.0
        self._compression_ratios.append(compression_ratio)

        logger.info(
            f"Fallback completed in {fallback_time:.2f}ms, "
            f"compressed {original_count} → {len(compressed)} messages"
        )

        return compressed[-last_n:]

    def search(
        self,
        query: str,
        workflow_id: str,
        threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """搜索相关消息（直接查询数据库）"""
        # 搜索操作直接查询 DB，因为需要全量数据
        return self._db.search(query, workflow_id, threshold)

    def clear(self, workflow_id: str) -> None:
        """清空记忆（DB + Cache）"""
        self._db.clear(workflow_id)
        self._cache.invalidate(workflow_id)

    def get_metrics(self) -> MemoryMetrics:
        """获取性能指标"""
        cache_stats = self._cache.get_stats()

        avg_fallback_time = (
            sum(self._fallback_times) / len(self._fallback_times)
            if self._fallback_times else 0.0
        )

        avg_compression_ratio = (
            sum(self._compression_ratios) / len(self._compression_ratios)
            if self._compression_ratios else 1.0
        )

        return MemoryMetrics(
            cache_hit_rate=cache_stats["hit_rate"],
            fallback_count=len(self._fallback_times),
            compression_ratio=avg_compression_ratio,
            avg_fallback_time_ms=avg_fallback_time
        )
```

**TDD 步骤：**
1. 写测试（RED）：`tests/unit/application/services/test_composite_memory_service.py`
   - 测试双写成功
   - 测试 DB 写入失败抛异常
   - 测试 Cache 写入失败不影响主流程
   - 测试缓存命中
   - 测试缓存未命中回溯
   - 测试压缩逻辑
   - 测试指标收集
2. 实现（GREEN）
3. 重构（REFACTOR）

---

### Phase 4: 集成到对话流（1 文件修改）

#### 4.1 增强 WorkflowChatServiceEnhanced

**文件：** `src/domain/services/workflow_chat_service_enhanced.py`（修改）

**修改点：**
1. 将 `ChatHistory` 替换为 `CompositeMemoryService`
2. 集成 RAG 上下文检索
3. 构建统一 prompt（工作记忆 + RAG + 当前消息）

```python
# 修改前
class EnhancedWorkflowChatService:
    def __init__(
        self,
        workflow_id: str,
        llm: ChatOpenAI,
        chat_message_repository: ChatMessageRepository,
        rag_service=None
    ):
        self.chat_history = ChatHistory(workflow_id, chat_message_repository)
        ...

# 修改后
class EnhancedWorkflowChatService:
    def __init__(
        self,
        workflow_id: str,
        llm: ChatOpenAI,
        composite_memory: CompositeMemoryService,
        rag_service: Optional[RAGService] = None
    ):
        self.workflow_id = workflow_id
        self.memory = composite_memory
        self.rag_service = rag_service
        ...

    async def process_message(
        self,
        workflow: Workflow,
        user_message: str,
        use_rag: bool = True
    ) -> ModificationResult:
        """处理消息（Memory + RAG 集成）"""

        # 1. 加载工作记忆（自动压缩）
        working_memory = self.memory.load_recent(self.workflow_id, last_n=10)
        memory_context = self._format_memory_context(working_memory)

        # 2. 检索 RAG 上下文（如果启用）
        rag_context = ""
        rag_sources = []
        if use_rag and self.rag_service:
            retrieved = await self.rag_service.retrieve_context(
                QueryContext(
                    query=user_message,
                    workflow_id=self.workflow_id,
                    max_context_length=2000,
                    filters={"user_id": self.workflow_id}  # 用户隔离
                )
            )
            rag_context = retrieved.formatted_context
            rag_sources = retrieved.sources

        # 3. 构建最终 prompt
        system_prompt = self._build_system_prompt(workflow, memory_context, rag_context)

        # 4. 调用 LLM
        response = await self.llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        # 5. 应用修改
        # ... (现有逻辑)

        # 6. 保存到记忆（双写）
        user_msg = ChatMessage.create(self.workflow_id, user_message, is_user=True)
        ai_msg = ChatMessage.create(self.workflow_id, ai_reply, is_user=False)

        self.memory.append(user_msg)
        self.memory.append(ai_msg)

        return ModificationResult(
            success=True,
            ai_message=ai_reply,
            rag_sources=rag_sources,
            ...
        )
```

**TDD 步骤：**
1. 写测试（RED）：`tests/integration/test_workflow_chat_with_composite_memory.py`
   - 测试单轮对话
   - 测试多轮对话（记忆延续）
   - 测试 RAG 上下文注入
   - 测试缓存命中/未命中
2. 实现（GREEN）
3. 重构（REFACTOR）

---

### Phase 5: 监控与 API（2 文件）

#### 5.1 监控 API

**文件：** `src/interfaces/api/routes/memory_metrics.py`

```python
from fastapi import APIRouter, Depends
from src.interfaces.api.dependencies.memory import get_composite_memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.get("/metrics/{workflow_id}")
async def get_memory_metrics(
    workflow_id: str,
    memory_service = Depends(get_composite_memory_service)
):
    """获取内存系统性能指标"""
    metrics = memory_service.get_metrics()

    return {
        "workflow_id": workflow_id,
        "cache_hit_rate": metrics.cache_hit_rate,
        "fallback_count": metrics.fallback_count,
        "avg_compression_ratio": metrics.compression_ratio,
        "avg_fallback_time_ms": metrics.avg_fallback_time_ms,
        "last_updated": metrics.last_updated.isoformat()
    }

@router.post("/cache/invalidate/{workflow_id}")
async def invalidate_cache(
    workflow_id: str,
    memory_service = Depends(get_composite_memory_service)
):
    """手动失效缓存"""
    memory_service._cache.invalidate(workflow_id)
    return {"status": "invalidated", "workflow_id": workflow_id}
```

#### 5.2 依赖注入

**文件：** `src/interfaces/api/dependencies/memory.py`

```python
from functools import lru_cache
from src.application.services.composite_memory_service import CompositeMemoryService
from src.infrastructure.memory.database_memory_store import DatabaseMemoryStore
from src.infrastructure.memory.in_memory_cache import InMemoryCache
from src.infrastructure.memory.tfidf_compressor import TFIDFCompressor
from src.interfaces.api.dependencies.database import get_db_session

@lru_cache()
def get_in_memory_cache() -> InMemoryCache:
    """全局单例缓存"""
    return InMemoryCache(ttl_seconds=900, max_workflows=1000)

def get_composite_memory_service(session = Depends(get_db_session)):
    """创建组合式内存服务"""
    repository = SQLAlchemyChatMessageRepository(session)
    db_store = DatabaseMemoryStore(repository)
    cache = get_in_memory_cache()
    compressor = TFIDFCompressor()

    return CompositeMemoryService(db_store, cache, compressor)
```

---

### Phase 6: 真实场景集成测试（1 文件）

**文件：** `tests/integration/test_memory_rag_real_scenario.py`

```python
import pytest
from datetime import datetime, timedelta

class TestMemoryRAGRealScenario:
    """真实场景测试（不是为了通过而通过）"""

    @pytest.mark.asyncio
    async def test_user_builds_workflow_with_conversation_memory(self):
        """
        场景：用户通过多轮对话逐步构建工作流

        验证点：
        1. 第一轮：用户说"创建一个 HTTP 节点"
        2. 第二轮：用户说"再加一个 LLM 节点连接到它"（需要记住第一轮）
        3. 第三轮：缓存过期，系统自动回溯到数据库
        4. 第四轮：用户说"总结一下我们做了什么"（测试搜索功能）
        """
        # 实现完整的端到端测试
        ...

    @pytest.mark.asyncio
    async def test_rag_personal_knowledge_isolation(self):
        """
        场景：多用户使用个人知识库

        验证点：
        1. 用户 A 上传文档"如何使用 Redis"
        2. 用户 B 上传文档"如何使用 MongoDB"
        3. 用户 A 询问"缓存怎么用" → 应返回 Redis 文档（不返回 MongoDB）
        4. 用户 B 询问"数据库怎么选" → 应返回 MongoDB 文档（不返回 Redis）
        """
        ...

    @pytest.mark.asyncio
    async def test_cache_performance_under_high_load(self):
        """
        场景：高并发场景下的缓存性能

        验证点：
        1. 模拟 100 个并发 workflow
        2. 每个 workflow 10 轮对话
        3. 验证缓存命中率 > 80%
        4. 验证平均响应时间 < 200ms
        """
        ...

    @pytest.mark.asyncio
    async def test_memory_compression_effectiveness(self):
        """
        场景：长对话压缩效果

        验证点：
        1. 用户进行 50 轮对话（超过 token 限制）
        2. 系统自动压缩到 4000 tokens
        3. 验证重要信息（如节点创建命令）被保留
        4. 验证低价值消息（如"好的"、"谢谢"）被移除
        """
        ...
```

---

## 📊 实施顺序总结（TDD 严格执行）

| Phase | 任务 | 文件数 | TDD 步骤 | 预计时间 |
|-------|------|--------|---------|---------|
| 1 | Domain Ports | 2 | RED→GREEN→REFACTOR | 30min |
| 2 | Infrastructure Adapters | 3 | RED→GREEN→REFACTOR | 90min |
| 3 | Application Composite Service | 1 | RED→GREEN→REFACTOR | 60min |
| 4 | Integration to Chat Flow | 1 | RED→GREEN→REFACTOR | 45min |
| 5 | Monitoring & API | 2 | RED→GREEN→REFACTOR | 30min |
| 6 | Real Scenario Tests | 1 | RED→GREEN→REFACTOR | 60min |
| **总计** | **10 文件** | | | **~5 小时** |

---

## 🚦 实施纪律

### 严格遵守的原则：

1. **TDD 三部曲：**
   - 🔴 RED: 先写失败的测试
   - 🟢 GREEN: 实现最小代码让测试通过
   - 🔵 REFACTOR: 优化代码质量

2. **分步确认：**
   - 每完成 1 个 Phase，暂停等待用户确认
   - 确认通过后再进入下一 Phase

3. **架构约束：**
   - Domain 层：纯 Python，零框架依赖
   - Application 层：业务编排，不直接操作数据库
   - Infrastructure 层：适配器实现，隔离外部依赖
   - Interface 层：HTTP API，依赖注入

4. **测试覆盖率：**
   - Domain 层：≥ 80%
   - Application 层：≥ 70%
   - Infrastructure 层：≥ 60%

---

## ✅ 验收标准

### 功能验收：
- ✅ 缓存命中率 > 70%（10 轮对话后）
- ✅ 回溯耗时 < 500ms
- ✅ 压缩比 0.3-0.7（原始消息的 30%-70%）
- ✅ RAG 文档隔离（跨用户无泄漏）
- ✅ 双写原子性（DB 失败 → 回滚）

### 性能验收：
- ✅ 单次 append 耗时 < 50ms
- ✅ 单次 load_recent 耗时 < 100ms（缓存命中）
- ✅ 单次 load_recent 耗时 < 500ms（缓存未命中）
- ✅ 并发 100 请求无异常

### 代码质量：
- ✅ 所有测试通过（pytest）
- ✅ 类型检查通过（pyright）
- ✅ 代码格式化（ruff format）
- ✅ 无 linting 错误（ruff check）

---

## 📚 参考资料

- **现有代码：**
  - ChatMessage Entity: `src/domain/entities/chat_message.py`
  - ChatMessageRepository: `src/infrastructure/database/repositories/chat_message_repository.py`
  - RAGService: `src/application/services/rag_service.py`
  - EnhancedWorkflowChatService: `src/domain/services/workflow_chat_service_enhanced.py`

- **文档：**
  - 开发规范: `docs/开发规范/00-总体开发规范.md`
  - TDD 指南: `docs/开发规范/03-开发过程指导.md`
  - CLAUDE.md: 项目根目录

---

**最后更新：** 2025-11-30
**状态：** 待用户确认 ✋
**下一步：** Phase 1 - Domain 层接口定义
