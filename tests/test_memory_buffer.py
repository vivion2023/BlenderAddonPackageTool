"""
测试内存缓冲区图像发送功能

这个脚本可以在 Blender 的 Python 控制台中运行,用于测试新的内存缓冲区实现。
"""

import bpy
import time

def test_memory_buffer_image_send():
    """测试内存缓冲区图像发送"""
    
    print("\n" + "="*60)
    print("测试: 内存缓冲区图像发送")
    print("="*60)
    
    # 1. 检查场景中是否有相机
    if not bpy.context.scene.camera:
        print("❌ 错误: 场景中没有相机")
        print("   请添加相机后再测试")
        return False
    
    print(f"✅ 相机: {bpy.context.scene.camera.name}")
    
    # 2. 检查是否连接到服务器
    from addons.robotic_twin.core.app import get_app
    app = get_app()
    
    if not app.is_connected():
        print("❌ 错误: 未连接到服务器")
        print("   请先连接到 WebSocket 服务器")
        return False
    
    print(f"✅ 已连接到服务器")
    
    # 3. 检查依赖
    try:
        import numpy as np
        print(f"✅ NumPy 版本: {np.__version__}")
    except ImportError:
        print("❌ 错误: NumPy 未安装")
        return False
    
    try:
        from PIL import Image
        print(f"✅ Pillow 版本: {Image.__version__}")
    except ImportError:
        print("❌ 错误: Pillow 未安装")
        return False
    
    # 4. 执行发送图像操作
    print("\n开始测试图像发送...")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        result = bpy.ops.robotic_twin.send_image()
        
        elapsed_time = time.time() - start_time
        
        if result == {'FINISHED'}:
            print(f"✅ 图像发送成功!")
            print(f"⏱️  耗时: {elapsed_time*1000:.1f}ms")
            return True
        else:
            print(f"❌ 图像发送失败: {result}")
            return False
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ 异常: {str(e)}")
        print(f"⏱️  耗时: {elapsed_time*1000:.1f}ms")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("="*60 + "\n")


def test_render_performance():
    """测试渲染性能"""
    
    print("\n" + "="*60)
    print("测试: 渲染性能对比")
    print("="*60)
    
    import time
    import numpy as np
    from PIL import Image
    from io import BytesIO
    
    scene = bpy.context.scene
    
    # 测试不同分辨率
    resolutions = [
        (640, 480, "VGA"),
        (1280, 720, "HD"),
        (1920, 1080, "Full HD"),
    ]
    
    original_x = scene.render.resolution_x
    original_y = scene.render.resolution_y
    
    try:
        for width, height, name in resolutions:
            print(f"\n测试分辨率: {name} ({width}x{height})")
            print("-" * 60)
            
            scene.render.resolution_x = width
            scene.render.resolution_y = height
            
            # 渲染
            start = time.time()
            bpy.ops.render.render(write_still=False)
            render_time = time.time() - start
            
            # 读取像素
            start = time.time()
            render_result = bpy.data.images.get('Render Result')
            w, h = render_result.size
            
            pixel_count = w * h * 4
            pixels = np.empty(pixel_count, dtype=np.float32)
            render_result.pixels.foreach_get(pixels)
            read_time = time.time() - start
            
            # 转换
            start = time.time()
            pixels = pixels.reshape((h, w, 4))
            pixels = np.flipud(pixels)
            pixels_uint8 = (pixels * 255).astype(np.uint8)
            pixels_rgb = pixels_uint8[:, :, :3]
            convert_time = time.time() - start
            
            # 编码
            start = time.time()
            pil_image = Image.fromarray(pixels_rgb, 'RGB')
            buffer = BytesIO()
            pil_image.save(buffer, format='JPEG', quality=85, optimize=True)
            image_data = buffer.getvalue()
            encode_time = time.time() - start
            
            total_time = render_time + read_time + convert_time + encode_time
            size_kb = len(image_data) / 1024
            
            print(f"  渲染时间: {render_time*1000:.1f}ms")
            print(f"  读取时间: {read_time*1000:.1f}ms")
            print(f"  转换时间: {convert_time*1000:.1f}ms")
            print(f"  编码时间: {encode_time*1000:.1f}ms")
            print(f"  总时间:   {total_time*1000:.1f}ms")
            print(f"  文件大小: {size_kb:.1f}KB")
            
    finally:
        # 恢复原始分辨率
        scene.render.resolution_x = original_x
        scene.render.resolution_y = original_y
        print("\n" + "="*60 + "\n")


# 运行测试
if __name__ == "__main__":
    print("\n开始测试...")
    
    # 测试基本功能
    success = test_memory_buffer_image_send()
    
    if success:
        # 如果基本功能测试通过,可以选择运行性能测试
        print("\n是否运行性能测试? (可能需要几秒钟)")
        print("在 Blender 控制台中运行: test_render_performance()")
