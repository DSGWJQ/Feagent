#!/usr/bin/env python3
"""同步文档版本号 - 更新docs/中的版本信息"""

from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"D:\My_Project\agent_data")


def update_readme():
    """更新docs/README.md"""
    readme = PROJECT_ROOT / "docs" / "README.md"

    if not readme.exists():
        print(f"  [WARN] File not found: {readme}")
        return False

    try:
        content = readme.read_text(encoding="utf-8")
        original_content = content

        # 替换版本号
        content = content.replace(
            "阶段：V2 (对话编辑+Coze集成)", "阶段：Phase 8+ (Unified Definition System)"
        )
        content = content.replace("V2 (对话编辑+Coze集成)", "Phase 8+ (Unified Definition System)")
        content = content.replace("最后更新：2025-11-25", "最后更新：2025-12-13")

        if content != original_content:
            readme.write_text(content, encoding="utf-8")
            print("  [OK] Updated docs/README.md")
            print("      - V2 -> Phase 8+")
            print("      - 2025-11-25 -> 2025-12-13")
            return True
        else:
            print("  [INFO] docs/README.md - no update needed")
            return True
    except Exception as e:
        print(f"  [ERROR] Update failed: {e}")
        return False


def update_current_agents():
    """更新current_agents.md"""
    doc = PROJECT_ROOT / "docs" / "architecture" / "current_agents.md"

    if not doc.exists():
        print(f"  [WARN] File not found: {doc}")
        return False

    try:
        content = doc.read_text(encoding="utf-8")
        original_content = content

        # 替换阶段描述
        content = content.replace("状态：Phase 5完成", "状态：Phase 8+ 活跃开发中")
        content = content.replace(
            "Phase 5完成，知识库集成已实现", "Phase 8+ 活跃开发中，多Agent协作系统完善"
        )

        if content != original_content:
            doc.write_text(content, encoding="utf-8")
            print("  [OK] Updated current_agents.md")
            print("      - Phase 5 -> Phase 8+")
            return True
        else:
            print("  [INFO] current_agents.md - no update needed")
            return True
    except Exception as e:
        print(f"  [ERROR] Update failed: {e}")
        return False


def update_api_doc():
    """更新API文档日期"""
    doc = PROJECT_ROOT / "docs" / "api" / "workflow_platform_api.md"

    if not doc.exists():
        print(f"  [WARN] File not found: {doc}")
        return False

    try:
        content = doc.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 检查是否已有更新日期
        has_date = any("最后更新" in line or "Last Updated" in line for line in lines[:5])

        if not has_date:
            # 在标题后添加日期（假设第一行是标题）
            if lines and lines[0].startswith("#"):
                lines.insert(1, "")
                lines.insert(2, "**Last Updated**: 2025-12-13")
                lines.insert(3, "")

                doc.write_text("\n".join(lines), encoding="utf-8")
                print("  [OK] Updated workflow_platform_api.md")
                print("      - Added update date: 2025-12-13")
                return True
        else:
            print("  [INFO] workflow_platform_api.md - already has date marker")
            return True
    except Exception as e:
        print(f"  [ERROR] Update failed: {e}")
        return False


def main():
    """主函数"""
    print("[UPDATE] Documentation Version Sync Script")
    print("=" * 60)
    print(f"Project Path: {PROJECT_ROOT}")
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    results = []

    print("[STEP 1] Updating docs/README.md")
    print("-" * 60)
    results.append(update_readme())
    print()

    print("[STEP 2] Updating current_agents.md")
    print("-" * 60)
    results.append(update_current_agents())
    print()

    print("[STEP 3] Updating workflow_platform_api.md")
    print("-" * 60)
    results.append(update_api_doc())
    print()

    print("=" * 60)
    success_count = sum(results)
    total_count = len(results)

    if success_count == total_count:
        print(f"[SUCCESS] Documentation sync completed! ({success_count}/{total_count})")
    else:
        print(f"[WARN] Some documents failed to update ({success_count}/{total_count})")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCEL] Sync operation cancelled")
    except Exception as e:
        print(f"\n\n[ERROR] An error occurred: {e}")
        import traceback

        traceback.print_exc()
