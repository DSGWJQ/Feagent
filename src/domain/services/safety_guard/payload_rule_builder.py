"""SafetyGuard - Payload 规则构建器

Phase 35.2: 从 CoordinatorAgent 提取 Payload 验证规则构建方法。

提供4个规则构建方法：
1. build_required_fields_rule: 必填字段验证
2. build_type_validation_rule: 字段类型验证
3. build_range_validation_rule: 字段范围验证
4. build_enum_validation_rule: 枚举值验证
"""

from typing import Any

from src.domain.services.safety_guard.rules import Rule


class PayloadRuleBuilder:
    """Payload 验证规则构建器

    负责构建4种 Payload 验证规则：
    - 必填字段验证
    - 字段类型验证
    - 字段范围验证
    - 枚举值验证

    使用示例：
        builder = PayloadRuleBuilder()
        rule = builder.build_required_fields_rule(
            decision_type="create_workflow",
            required_fields=["nodes", "edges"]
        )
        coordinator.add_rule(rule)
    """

    def build_required_fields_rule(
        self,
        decision_type: str,
        required_fields: list[str],
    ) -> Rule:
        """构建必填字段验证规则

        参数：
            decision_type: 决策类型
            required_fields: 必填字段列表

        返回：
            Rule: 验证规则
        """

        def condition(decision: dict[str, Any]) -> bool:
            # 只验证匹配的决策类型
            if decision.get("action_type") != decision_type:
                return True

            # 检查所有必填字段
            missing_fields = []
            for field_name in required_fields:
                if field_name not in decision or decision[field_name] is None:
                    missing_fields.append(field_name)
                # 检查空列表/空字典（Phase 8.4 增强）
                elif isinstance(decision[field_name], list | dict) and not decision[field_name]:
                    missing_fields.append(field_name)

            # 如果有缺失字段，记录到决策中以便错误消息使用
            if missing_fields:
                decision["_missing_fields"] = missing_fields
                return False

            return True

        rule = Rule(
            id=f"payload_required_{decision_type}",
            name=f"Payload 必填字段验证 ({decision_type})",
            condition=condition,
            priority=1,
            error_message=lambda d: "; ".join(
                [f"缺少必填字段: {field}" for field in d.get("_missing_fields", [])]
            )
            if len(d.get("_missing_fields", [])) > 1
            else f"缺少必填字段: {', '.join(d.get('_missing_fields', []))}",
        )

        return rule

    def build_type_validation_rule(
        self,
        decision_type: str,
        field_types: dict[str, type | tuple[type, ...]],
        nested_field_types: dict[str, type | tuple[type, ...]] | None = None,
    ) -> Rule:
        """构建字段类型验证规则

        参数：
            decision_type: 决策类型
            field_types: 字段类型映射 {字段名: 类型}
            nested_field_types: 嵌套字段类型映射 {字段路径: 类型}，如 {"config.timeout": int}

        返回：
            Rule: 验证规则
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            type_errors = []

            # 检查顶层字段类型
            for field_name, expected_type in field_types.items():
                if field_name in decision:
                    value = decision[field_name]
                    if not isinstance(value, expected_type):
                        type_name = (
                            expected_type.__name__
                            if isinstance(expected_type, type)
                            else " or ".join(t.__name__ for t in expected_type)
                        )
                        type_errors.append(
                            f"字段 {field_name} 类型错误，期望 {type_name}，实际 {type(value).__name__}"
                        )

            # 检查嵌套字段类型
            if nested_field_types:
                for field_path, expected_type in nested_field_types.items():
                    parts = field_path.split(".")
                    current = decision
                    try:
                        for part in parts:
                            current = current[part]

                        if not isinstance(current, expected_type):
                            type_name = (
                                expected_type.__name__
                                if isinstance(expected_type, type)
                                else " or ".join(t.__name__ for t in expected_type)
                            )
                            type_errors.append(f"字段 {field_path} 类型错误，期望 {type_name}")
                    except (KeyError, TypeError):
                        # 字段不存在，跳过（由必填字段验证处理）
                        pass

            if type_errors:
                decision["_type_errors"] = type_errors
                return False

            return True

        rule = Rule(
            id=f"payload_type_{decision_type}",
            name=f"Payload 字段类型验证 ({decision_type})",
            condition=condition,
            priority=2,
            error_message=lambda d: "; ".join(d.get("_type_errors", [])),
        )

        return rule

    def build_range_validation_rule(
        self,
        decision_type: str,
        field_ranges: dict[str, dict[str, int | float]],
    ) -> Rule:
        """构建字段值范围验证规则

        参数：
            decision_type: 决策类型
            field_ranges: 字段范围映射 {字段路径: {"min": 最小值, "max": 最大值}}

        返回：
            Rule: 验证规则
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            range_errors = []

            for field_path, range_spec in field_ranges.items():
                parts = field_path.split(".")
                current = decision
                try:
                    for part in parts:
                        current = current[part]

                    # 检查范围（仅对数值类型进行比较）
                    if not isinstance(current, int | float):
                        continue

                    min_val = range_spec.get("min")
                    max_val = range_spec.get("max")

                    if min_val is not None and current < min_val:
                        range_errors.append(f"字段 {field_path} 值 {current} 小于最小值 {min_val}")

                    if max_val is not None and current > max_val:
                        range_errors.append(f"字段 {field_path} 值 {current} 大于最大值 {max_val}")

                except (KeyError, TypeError):
                    # 字段不存在或类型错误，跳过
                    pass

            if range_errors:
                decision["_range_errors"] = range_errors
                return False

            return True

        rule = Rule(
            id=f"payload_range_{decision_type}",
            name=f"Payload 字段范围验证 ({decision_type})",
            condition=condition,
            priority=3,
            error_message=lambda d: "; ".join(d.get("_range_errors", [])),
        )

        return rule

    def build_enum_validation_rule(
        self,
        decision_type: str,
        field_enums: dict[str, list[str]],
    ) -> Rule:
        """构建字段枚举值验证规则

        参数：
            decision_type: 决策类型
            field_enums: 字段枚举映射 {字段名: 允许的值列表}

        返回：
            Rule: 验证规则
        """

        def condition(decision: dict[str, Any]) -> bool:
            if decision.get("action_type") != decision_type:
                return True

            enum_errors = []

            for field_name, allowed_values in field_enums.items():
                if field_name in decision:
                    value = decision[field_name]
                    if value not in allowed_values:
                        enum_errors.append(
                            f"字段 {field_name} 值 {value} 不在允许的列表中: {', '.join(allowed_values)}"
                        )

            if enum_errors:
                decision["_enum_errors"] = enum_errors
                return False

            return True

        rule = Rule(
            id=f"payload_enum_{decision_type}",
            name=f"Payload 枚举值验证 ({decision_type})",
            condition=condition,
            priority=4,
            error_message=lambda d: "; ".join(d.get("_enum_errors", [])),
        )

        return rule


__all__ = ["PayloadRuleBuilder"]
