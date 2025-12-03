"""
启动 Blender 并加载插件
支持热更新：修改代码后自动重载插件

用法:
    python run_blender.py                    # 启动默认插件（带热更新）
    python run_blender.py robotic_twin       # 指定插件名
    python run_blender.py --no-watch         # 禁用热更新
"""

from framework import test_addon
from main import ACTIVE_ADDON

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='启动 Blender 并加载插件')
    parser.add_argument('addon', default=ACTIVE_ADDON, nargs='?', 
                        help='插件名称 (默认: %(default)s)')
    parser.add_argument('--no-watch', dest='disable_watch', action='store_true',
                        help='禁用热更新（文件修改后不自动重载）')
    
    args = parser.parse_args()
    
    print(f"启动 Blender，加载插件: {args.addon}")
    print(f"热更新: {'禁用' if args.disable_watch else '启用'}")
    print("-" * 40)
    
    test_addon(args.addon, enable_watch=not args.disable_watch)
