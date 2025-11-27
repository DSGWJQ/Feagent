"""用户角色值对象

用户角色是一个值对象，表示用户在系统中的权限级别。

为什么是值对象而不是实体？
- 用户角色没有独立的生命周期，它是User实体的一部分
- 用户角色是不可变的（一旦设置，不会改变内部状态）
- 用户角色基于值相等性（两个相同的角色值是相等的）
- 用户角色可以被替换（通过更新User实体的role字段）

设计原则：
- 使用Enum确保角色值的有效性
- 提供清晰的角色描述
- 便于扩展新角色
"""

from enum import Enum


class UserRole(str, Enum):
    """用户角色枚举

    角色层级（从低到高）：
    - USER: 普通用户，可以创建和管理自己的工作流和工具
    - ADMIN: 管理员，可以管理所有用户和系统设置

    为什么继承str？
    - 便于序列化到JSON和数据库
    - 可以直接比较字符串值
    - 符合Pydantic和FastAPI的要求
    """

    USER = "user"  # 普通用户
    ADMIN = "admin"  # 管理员

    @property
    def description(self) -> str:
        """获取角色描述"""
        descriptions = {
            UserRole.USER: "普通用户",
            UserRole.ADMIN: "管理员",
        }
        return descriptions.get(self, "未知角色")

    @classmethod
    def default(cls) -> "UserRole":
        """获取默认角色"""
        return cls.USER

    def is_admin(self) -> bool:
        """检查是否是管理员角色"""
        return self == UserRole.ADMIN

    def is_user(self) -> bool:
        """检查是否是普通用户角色"""
        return self == UserRole.USER
