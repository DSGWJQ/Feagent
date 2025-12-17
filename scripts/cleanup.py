#!/usr/bin/env python3
"""项目文件清理脚本 - 删除临时文件和缓存"""
import os
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"D:\My_Project\agent_data")

def cleanup():
    """执行清理操作"""
    # 创建备份
    backup_dir = PROJECT_ROOT / "backup" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    print("[CLEANUP] Project File Cleanup Script")
    print("=" * 60)
    print(f"Project Path: {PROJECT_ROOT}")
    print(f"Backup Path: {backup_dir}")
    print("=" * 60)
    print()

    # 临时文件列表
    temp_files = [
        "nul",
        "_tmp_36828_d7b9fc136caba0b38a5a21fc1cae477c",
        "snippet.py",
    ]

    print("[STEP 1] Cleaning temporary files")
    print("-" * 60)
    cleaned_files = 0
    for file in temp_files:
        path = PROJECT_ROOT / file
        if path.exists():
            size = path.stat().st_size
            print(f"  Found: {file} ({size} bytes)")
            # 备份后删除
            try:
                shutil.copy2(path, backup_dir / file)
                path.unlink()
                print(f"    [OK] Deleted (backed up)")
                cleaned_files += 1
            except Exception as e:
                print(f"    [ERROR] Failed to delete: {e}")
        else:
            print(f"  Skip: {file} (not found)")

    print(f"\n  Completed: {cleaned_files}/{len(temp_files)} files cleaned")
    print()

    # 清理缓存目录
    print("[STEP 2] Cleaning cache directories")
    print("-" * 60)
    cache_dirs = [
        ".pytest_cache",
        ".ruff_cache",
        "scripts/tmp",
    ]

    cleaned_dirs = 0
    for dir_name in cache_dirs:
        path = PROJECT_ROOT / dir_name
        if path.exists():
            try:
                # 计算目录大小
                total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                print(f"  Found: {dir_name}/ ({size_mb:.2f} MB)")
                shutil.rmtree(path)
                print(f"    [OK] Cleaned")
                cleaned_dirs += 1
            except Exception as e:
                print(f"    [ERROR] Failed to clean: {e}")
        else:
            print(f"  Skip: {dir_name}/ (not found)")

    print(f"\n  Completed: {cleaned_dirs}/{len(cache_dirs)} directories cleaned")
    print()

    # 移动错位文件
    print("[STEP 3] Moving misplaced files")
    print("-" * 60)
    watchfiles = PROJECT_ROOT / "watchfiles.py"
    if watchfiles.exists():
        target = PROJECT_ROOT / "scripts" / "watchfiles.py"
        try:
            # 如果目标已存在，先备份
            if target.exists():
                shutil.copy2(target, backup_dir / "watchfiles_old.py")
                print(f"  Backed up old file: scripts/watchfiles.py")

            shutil.move(str(watchfiles), str(target))
            print(f"  [OK] Moved: watchfiles.py -> scripts/watchfiles.py")
        except Exception as e:
            print(f"  [ERROR] Failed to move: {e}")
    else:
        print(f"  Skip: watchfiles.py (not found)")

    print()
    print("=" * 60)
    print(f"[SUCCESS] Cleanup completed!")
    print(f"[BACKUP] Backup location: {backup_dir}")
    print("=" * 60)

if __name__ == "__main__":
    try:
        cleanup()
    except KeyboardInterrupt:
        print("\n\n[CANCEL] Cleanup operation cancelled")
    except Exception as e:
        print(f"\n\n[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
