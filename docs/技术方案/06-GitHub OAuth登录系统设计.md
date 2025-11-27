# GitHub OAuth 2.0 登录系统设计

## 1. 系统概述

### 1.1 功能目标
- **已登录用户**：可以创建、保存工作流和上传工具，数据与用户账户关联
- **未登录用户**：只能体验创建工作流（不保存），无法上传工具

### 1.2 技术选型
- **认证协议**：GitHub OAuth 2.0
- **Token管理**：JWT (HS256算法)
- **会话存储**：LocalStorage (前端) + Database (后端)
- **权限控制**：依赖注入 + FastAPI Depends

---

## 2. OAuth 2.0 授权流程

### 2.1 完整流程图

```
┌─────────────┐                ┌──────────────┐                ┌─────────────┐
│   用户      │                │   前端       │                │   后端      │
│  (Browser)  │                │  (React)     │                │  (FastAPI)  │
└──────┬──────┘                └──────┬───────┘                └──────┬──────┘
       │                               │                               │
       │  1. 点击"GitHub登录"按钮       │                               │
       ├──────────────────────────────>│                               │
       │                               │                               │
       │  2. 重定向到GitHub授权页面     │                               │
       │<──────────────────────────────┤                               │
       │                               │                               │
┌──────┴───────┐                       │                               │
│   GitHub     │                       │                               │
│ OAuth Server │                       │                               │
└──────┬───────┘                       │                               │
       │  3. 用户授权                  │                               │
       │                               │                               │
       │  4. 回调 /auth/callback?code=xxx                              │
       ├──────────────────────────────>│                               │
       │                               │  5. POST /api/auth/github     │
       │                               ├──────────────────────────────>│
       │                               │     { code: "xxx" }           │
       │                               │                               │
       │                               │  6. 后端用code换取access_token │
       │                               │<──────────────────────────────┤
       │                               │     (调用GitHub API)          │
       │                               │                               │
       │                               │  7. 获取GitHub用户信息         │
       │                               │                               │
       │                               │  8. 创建/更新User实体          │
       │                               │                               │
       │                               │  9. 生成JWT token              │
       │                               │                               │
       │                               │  10. 返回JWT + 用户信息        │
       │                               │<──────────────────────────────┤
       │                               │     { token, user }           │
       │  11. 保存token到localStorage  │                               │
       │<──────────────────────────────┤                               │
       │                               │                               │
       │  12. 重定向到工作流页面        │                               │
       │<──────────────────────────────┤                               │
       │                               │                               │
```

### 2.2 关键步骤说明

**前端步骤：**
1. 用户点击"GitHub登录"按钮
2. 前端重定向到 `https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={CALLBACK_URL}&scope=user:email`
3. 用户在GitHub授权页面同意授权
4. GitHub回调到 `/auth/callback?code={CODE}`
5. 前端提取code，调用后端API `/api/auth/github`
6. 后端返回JWT token和用户信息
7. 前端存储token到localStorage，更新全局状态

**后端步骤：**
1. 接收前端发送的code
2. 用code向GitHub请求access_token
3. 用access_token获取GitHub用户信息
4. 在数据库中创建或更新User实体
5. 生成JWT token（包含user_id, email等）
6. 返回token和用户信息

---

## 3. 数据库设计

### 3.1 User表（ORM模型）

```python
class UserModel(Base):
    """User ORM 模型"""
    __tablename__ = "users"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="User ID（UUID）")

    # GitHub OAuth信息
    github_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, comment="GitHub用户ID")
    github_username: Mapped[str] = mapped_column(String(255), nullable=False, comment="GitHub用户名")
    github_avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="GitHub头像URL")
    github_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="GitHub个人主页")

    # 用户基本信息
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, comment="用户邮箱")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="用户姓名")

    # 账户状态
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, comment="是否激活")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user", comment="用户角色（user/admin）")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=datetime.now, comment="更新时间")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后登录时间")

    # 关系
    workflows: Mapped[list["WorkflowModel"]] = relationship("WorkflowModel", back_populates="user", cascade="all, delete-orphan")
    tools: Mapped[list["ToolModel"]] = relationship("ToolModel", back_populates="user", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index("idx_users_github_id", "github_id"),
        Index("idx_users_email", "email"),
        Index("idx_users_created_at", "created_at"),
    )
```

### 3.2 修改现有表（添加user_id字段）

**WorkflowModel（workflows表）：**
```python
# 添加字段
user_id: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,  # 兼容现有数据
    comment="创建者ID",
)

# 添加关系
user: Mapped["UserModel"] = relationship("UserModel", back_populates="workflows")
```

**ToolModel（tools表）：**
```python
# 添加字段
user_id: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,  # 兼容现有数据
    comment="创建者ID",
)

# 添加关系
user: Mapped["UserModel"] = relationship("UserModel", back_populates="tools")
```

---

## 4. Domain层设计（DDD）

### 4.1 User实体（src/domain/entities/user.py）

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.domain.exceptions import DomainError
from src.domain.value_objects.user_role import UserRole

@dataclass
class User:
    """用户聚合根"""
    id: str
    github_id: int
    github_username: str
    email: str
    name: Optional[str] = None
    github_avatar_url: Optional[str] = None
    github_profile_url: Optional[str] = None
    is_active: bool = True
    role: UserRole = UserRole.USER
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    @staticmethod
    def create_from_github(
        github_id: int,
        github_username: str,
        email: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        profile_url: Optional[str] = None,
    ) -> "User":
        """从GitHub OAuth信息创建用户"""
        if not github_id:
            raise DomainError("github_id不能为空")
        if not github_username:
            raise DomainError("github_username不能为空")
        if not email:
            raise DomainError("email不能为空")

        return User(
            id=generate_id(),
            github_id=github_id,
            github_username=github_username,
            email=email,
            name=name,
            github_avatar_url=avatar_url,
            github_profile_url=profile_url,
            created_at=datetime.now(),
        )

    def update_login_time(self) -> None:
        """更新最后登录时间"""
        self.last_login_at = datetime.now()

    def deactivate(self) -> None:
        """停用用户"""
        self.is_active = False

    def activate(self) -> None:
        """激活用户"""
        self.is_active = True
```

### 4.2 UserRole值对象（src/domain/value_objects/user_role.py）

```python
from enum import Enum

class UserRole(str, Enum):
    """用户角色"""
    USER = "user"        # 普通用户
    ADMIN = "admin"      # 管理员
```

### 4.3 UserRepository接口（src/domain/ports/user_repository.py）

```python
from typing import Protocol, Optional
from src.domain.entities.user import User

class UserRepository(Protocol):
    """用户仓储接口"""

    def save(self, user: User) -> None:
        """保存用户"""
        ...

    def find_by_id(self, user_id: str) -> Optional[User]:
        """根据ID查找用户"""
        ...

    def find_by_github_id(self, github_id: int) -> Optional[User]:
        """根据GitHub ID查找用户"""
        ...

    def find_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查找用户"""
        ...

    def exists_by_github_id(self, github_id: int) -> bool:
        """检查GitHub ID是否已存在"""
        ...

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """列出所有用户"""
        ...
```

---

## 5. Infrastructure层设计

### 5.1 GitHubOAuthService（src/infrastructure/auth/github_oauth_service.py）

```python
import httpx
from typing import Dict, Optional

class GitHubOAuthService:
    """GitHub OAuth 2.0 服务"""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def exchange_code_for_token(self, code: str) -> str:
        """用授权码换取access_token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["access_token"]

    async def get_user_info(self, access_token: str) -> Dict:
        """获取GitHub用户信息"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_emails(self, access_token: str) -> list[Dict]:
        """获取GitHub用户邮箱列表"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
```

### 5.2 JWTService（src/infrastructure/auth/jwt_service.py）

```python
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt
from src.config import settings

class JWTService:
    """JWT Token服务"""

    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict:
        """解码JWT令牌"""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token已过期")
        except jwt.JWTError:
            raise ValueError("Token无效")
```

### 5.3 SQLAlchemyUserRepository（src/infrastructure/database/repositories/user_repository.py）

```python
from typing import Optional
from sqlalchemy.orm import Session
from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.database.models import UserModel
from src.infrastructure.database.assemblers.user_assembler import UserAssembler

class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy用户仓储实现"""

    def __init__(self, session: Session):
        self.session = session

    def save(self, user: User) -> None:
        model = self.session.query(UserModel).filter_by(id=user.id).first()
        if model:
            UserAssembler.update_model(model, user)
        else:
            model = UserAssembler.to_model(user)
            self.session.add(model)
        self.session.commit()
        self.session.refresh(model)

    def find_by_id(self, user_id: str) -> Optional[User]:
        model = self.session.query(UserModel).filter_by(id=user_id).first()
        return UserAssembler.to_entity(model) if model else None

    def find_by_github_id(self, github_id: int) -> Optional[User]:
        model = self.session.query(UserModel).filter_by(github_id=github_id).first()
        return UserAssembler.to_entity(model) if model else None

    def find_by_email(self, email: str) -> Optional[User]:
        model = self.session.query(UserModel).filter_by(email=email).first()
        return UserAssembler.to_entity(model) if model else None

    def exists_by_github_id(self, github_id: int) -> bool:
        return self.session.query(UserModel).filter_by(github_id=github_id).first() is not None

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        models = self.session.query(UserModel).offset(skip).limit(limit).all()
        return [UserAssembler.to_entity(model) for model in models]
```

---

## 6. Application层设计

### 6.1 GitHubAuthUseCase（src/application/use_cases/github_auth.py）

```python
from dataclasses import dataclass
from datetime import timedelta
from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.github_oauth_service import GitHubOAuthService
from src.infrastructure.auth.jwt_service import JWTService
from src.config import settings

@dataclass
class GitHubAuthInput:
    """GitHub认证输入"""
    code: str

@dataclass
class GitHubAuthOutput:
    """GitHub认证输出"""
    access_token: str
    user: User

class GitHubAuthUseCase:
    """GitHub OAuth认证用例"""

    def __init__(
        self,
        user_repository: UserRepository,
        github_oauth_service: GitHubOAuthService,
    ):
        self.user_repository = user_repository
        self.github_oauth_service = github_oauth_service

    async def execute(self, input_data: GitHubAuthInput) -> GitHubAuthOutput:
        """执行GitHub OAuth认证"""
        # 1. 用code换取GitHub access_token
        github_token = await self.github_oauth_service.exchange_code_for_token(input_data.code)

        # 2. 获取GitHub用户信息
        github_user = await self.github_oauth_service.get_user_info(github_token)
        github_emails = await self.github_oauth_service.get_user_emails(github_token)

        # 3. 提取主邮箱
        primary_email = next((e["email"] for e in github_emails if e["primary"]), github_user.get("email"))

        # 4. 查找或创建用户
        user = self.user_repository.find_by_github_id(github_user["id"])
        if user:
            # 更新登录时间
            user.update_login_time()
            self.user_repository.save(user)
        else:
            # 创建新用户
            user = User.create_from_github(
                github_id=github_user["id"],
                github_username=github_user["login"],
                email=primary_email,
                name=github_user.get("name"),
                avatar_url=github_user.get("avatar_url"),
                profile_url=github_user.get("html_url"),
            )
            self.user_repository.save(user)

        # 5. 生成JWT token
        token_data = {
            "sub": user.id,
            "email": user.email,
            "role": user.role.value,
        }
        access_token = JWTService.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )

        return GitHubAuthOutput(access_token=access_token, user=user)
```

---

## 7. Interface层设计

### 7.1 认证路由（src/interfaces/api/routes/auth.py）

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.application.use_cases.github_auth import GitHubAuthUseCase, GitHubAuthInput
from src.interfaces.api.dependencies.auth import get_github_auth_use_case
from src.interfaces.api.dto.user_dto import UserResponse

router = APIRouter()

class GitHubAuthRequest(BaseModel):
    """GitHub认证请求"""
    code: str

class GitHubAuthResponse(BaseModel):
    """GitHub认证响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/auth/github", response_model=GitHubAuthResponse)
async def github_auth(
    request: GitHubAuthRequest,
    use_case: GitHubAuthUseCase = Depends(get_github_auth_use_case),
):
    """GitHub OAuth认证"""
    try:
        result = await use_case.execute(GitHubAuthInput(code=request.code))
        return GitHubAuthResponse(
            access_token=result.access_token,
            user=UserResponse.from_entity(result.user),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/auth/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_active_user),
):
    """获取当前登录用户"""
    return UserResponse.from_entity(current_user)
```

### 7.2 依赖注入（src/interfaces/api/dependencies/auth.py）

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredential
from sqlalchemy.orm import Session
from src.domain.entities.user import User
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.database.engine import get_db
from src.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.auth.github_oauth_service import GitHubOAuthService
from src.application.use_cases.github_auth import GitHubAuthUseCase
from src.config import settings

security = HTTPBearer()

def get_github_oauth_service() -> GitHubOAuthService:
    """获取GitHub OAuth服务"""
    return GitHubOAuthService(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=settings.github_redirect_uri,
    )

def get_github_auth_use_case(
    session: Session = Depends(get_db),
    github_oauth_service: GitHubOAuthService = Depends(get_github_oauth_service),
) -> GitHubAuthUseCase:
    """获取GitHub认证用例"""
    user_repository = SQLAlchemyUserRepository(session)
    return GitHubAuthUseCase(user_repository, github_oauth_service)

async def get_current_user(
    credentials: HTTPAuthCredential = Depends(security),
    session: Session = Depends(get_db),
) -> User:
    """获取当前用户（从JWT token）"""
    try:
        payload = JWTService.decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    user_repository = SQLAlchemyUserRepository(session)
    user = user_repository.find_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前激活用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被停用",
        )
    return current_user

async def get_current_user_optional(
    credentials: HTTPAuthCredential = Depends(security),
    session: Session = Depends(get_db),
) -> User | None:
    """获取当前用户（可选，未登录返回None）"""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, session)
    except HTTPException:
        return None
```

---

## 8. 前端设计

### 8.1 GitHub登录组件（web/src/features/auth/components/GitHubLoginButton.tsx）

```typescript
import React from 'react';
import { Button } from '@/components/ui/button';
import { GithubIcon } from 'lucide-react';

const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID;
const REDIRECT_URI = import.meta.env.VITE_GITHUB_REDIRECT_URI || `${window.location.origin}/auth/callback`;

export const GitHubLoginButton: React.FC = () => {
  const handleLogin = () => {
    const authUrl = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=user:email`;
    window.location.href = authUrl;
  };

  return (
    <Button onClick={handleLogin} variant="outline" className="gap-2">
      <GithubIcon size={20} />
      使用 GitHub 登录
    </Button>
  );
};
```

### 8.2 回调页面（web/src/features/auth/pages/AuthCallbackPage.tsx）

```typescript
import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

export const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      navigate('/login?error=no_code');
      return;
    }

    const handleCallback = async () => {
      try {
        const response = await api.auth.githubAuth({ code });
        login(response.data.access_token, response.data.user);
        navigate('/workflows');
      } catch (error) {
        console.error('GitHub认证失败:', error);
        navigate('/login?error=auth_failed');
      }
    };

    handleCallback();
  }, [searchParams, navigate, login]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <p className="text-lg">正在登录...</p>
      </div>
    </div>
  );
};
```

### 8.3 Auth API（web/src/services/api.ts）

```typescript
// 添加到API客户端
const auth = {
  githubAuth: (data: { code: string }) =>
    axiosInstance.post<{ access_token: string; user: User }>('/auth/github', data),
  getCurrentUser: () =>
    axiosInstance.get<User>('/auth/me'),
  logout: () => {
    localStorage.removeItem('authToken');
    window.location.href = '/login';
  },
};

export const api = {
  workflows,
  // ... 其他API
  auth,
};
```

### 8.4 Auth Context（web/src/contexts/AuthContext.tsx）

```typescript
import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '@/types/user';
import { api } from '@/services/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (token) {
      api.auth.getCurrentUser()
        .then(response => setUser(response.data))
        .catch(() => localStorage.removeItem('authToken'))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = (token: string, user: User) => {
    localStorage.setItem('authToken', token);
    setUser(user);
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth必须在AuthProvider内使用');
  return context;
};
```

---

## 9. 配置文件更新

### 9.1 后端配置（.env）

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:5173/auth/callback
```

### 9.2 前端配置（.env）

```bash
# GitHub OAuth
VITE_GITHUB_CLIENT_ID=your_github_client_id
VITE_GITHUB_REDIRECT_URI=http://localhost:5173/auth/callback
```

---

## 10. 权限控制实现

### 10.1 修改Workflow路由（添加权限控制）

```python
@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    request: CreateWorkflowRequest,
    current_user: User | None = Depends(get_current_user_optional),
    session: Session = Depends(get_db),
):
    """创建工作流（未登录用户创建的工作流不保存到数据库）"""
    if current_user:
        # 已登录：保存到数据库，关联用户
        use_case = CreateWorkflowUseCase(repository=SQLAlchemyWorkflowRepository(session))
        workflow = use_case.execute(CreateWorkflowInput(**request.dict(), user_id=current_user.id))
        return WorkflowResponse.from_entity(workflow)
    else:
        # 未登录：创建临时工作流，不保存
        workflow = Workflow.create(
            name=request.name,
            description=request.description,
            user_id=None,  # 无用户关联
        )
        return WorkflowResponse.from_entity(workflow)
```

### 10.2 修改Tool路由（强制要求登录）

```python
@router.post("/tools", response_model=ToolResponse)
async def create_tool(
    request: CreateToolRequest,
    current_user: User = Depends(get_current_active_user),  # 必须登录
    session: Session = Depends(get_db),
):
    """创建工具（需要登录）"""
    use_case = CreateToolUseCase(repository=SQLAlchemyToolRepository(session))
    tool = use_case.execute(CreateToolInput(**request.dict(), user_id=current_user.id))
    return ToolResponse.from_entity(tool)
```

---

## 11. 数据库迁移

### 11.1 创建迁移脚本

```bash
alembic revision --autogenerate -m "add_users_table_and_user_associations"
alembic upgrade head
```

---

## 12. 测试策略

### 12.1 单元测试
- User实体创建和业务逻辑测试
- UserRepository接口测试
- GitHubAuthUseCase测试
- JWTService测试

### 12.2 集成测试
- GitHub OAuth完整流程测试
- 认证API端点测试
- 权限控制中间件测试

### 12.3 E2E测试
- 用户登录流程测试
- 已登录用户创建工作流测试
- 未登录用户体验模式测试

---

## 13. 安全考虑

1. **Token安全**：
   - JWT使用HS256算法，密钥存储在环境变量
   - Token过期时间默认30分钟
   - 前端存储在localStorage（考虑XSS攻击）

2. **GitHub OAuth安全**：
   - Client Secret仅在后端使用，不暴露给前端
   - Redirect URI白名单验证

3. **CSRF防护**：
   - GitHub OAuth的state参数（可选实现）

4. **数据隔离**：
   - 所有用户数据通过user_id隔离
   - 数据库查询自动过滤当前用户

---

## 14. 实施优先级

**P0（核心功能）：**
1. User Entity + Repository
2. GitHub OAuth Service
3. JWT Service
4. 认证API端点
5. 前端登录组件

**P1（权限控制）：**
1. 依赖注入中间件
2. Workflow/Tool关联用户
3. 权限控制逻辑

**P2（用户体验）：**
1. 用户仪表板
2. 用户设置页面
3. 登出功能

**P3（可选功能）：**
1. 用户头像显示
2. 邮箱验证
3. 用户角色管理

---

**设计文档版本**: v1.0
**最后更新**: 2025-01-27
