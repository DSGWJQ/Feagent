"""JWT Token服务

职责：
1. 创建JWT访问令牌（access token）
2. 解码和验证JWT令牌
3. 处理token过期和安全验证

为什么使用JWT？
- 无状态认证：不需要在服务器端存储session
- 可扩展：支持分布式系统
- 标准化：符合RFC 7519标准
- 安全：使用签名防止篡改

设计原则：
- 使用HS256算法（HMAC with SHA-256）
- Token包含：用户ID（sub）、邮箱、角色、过期时间（exp）、签发时间（iat）
- 密钥从配置文件读取，生产环境必须更换
"""

from datetime import datetime, timedelta

import jwt

from src.config import settings


class JWTService:
    """JWT Token服务

    提供JWT token的创建和验证功能。

    为什么使用静态方法？
    - JWTService是无状态的工具类
    - 不需要实例化，直接调用即可
    - 符合函数式编程风格
    """

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        """创建JWT访问令牌

        生成包含用户信息的JWT token，用于API认证。

        Args:
            data: 要编码到token中的数据（通常包含sub, email, role）
            expires_delta: 可选的过期时间间隔，如果不指定则使用配置的默认值

        Returns:
            str: 编码后的JWT token字符串

        示例：
            >>> token_data = {"sub": "user-123", "email": "user@example.com", "role": "user"}
            >>> token = JWTService.create_access_token(data=token_data)
            >>> print(token)
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
        """
        # 复制数据，避免修改原始字典
        to_encode = data.copy()

        # 计算过期时间
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        # 添加标准JWT声明
        to_encode.update(
            {
                "exp": expire,  # 过期时间（Expiration Time）
                "iat": datetime.utcnow(),  # 签发时间（Issued At）
            }
        )

        # 使用HS256算法编码
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> dict:
        """解码JWT令牌

        验证token签名并解码payload数据。

        Args:
            token: JWT token字符串

        Returns:
            Dict: 解码后的payload数据

        Raises:
            ValueError: 当token过期、无效或被篡改时抛出

        示例：
            >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            >>> payload = JWTService.decode_token(token)
            >>> print(payload["sub"])
            'user-123'
        """
        try:
            # 解码并验证token
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload

        except jwt.ExpiredSignatureError:
            # Token已过期
            raise ValueError("Token已过期")

        except jwt.PyJWTError:
            # Token无效（签名验证失败、格式错误等）
            raise ValueError("Token无效")

        except Exception:
            # 其他异常（如空字符串、格式错误等）
            raise ValueError("Token无效")
