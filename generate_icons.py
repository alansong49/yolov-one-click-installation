"""
将 SVG 图标转换为 ICO (Windows) 和 PNG (Linux) 格式
使用 PyQt6 的 SVG 渲染功能
"""
import os
import sys
from PyQt6.QtGui import QImage, QPainter, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

SVG_PATH = os.path.join(os.path.dirname(__file__), 'exported_image.svg')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'assets')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 图标尺寸（标准 ICO 包含的尺寸）
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def svg_to_image(svg_path, size):
    """将 SVG 渲染为指定尺寸的 QImage"""
    renderer = QSvgRenderer(svg_path)
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    return image


def generate_pngs():
    """生成各种尺寸的 PNG 图标"""
    png_files = []
    for size in SIZES:
        img = svg_to_image(SVG_PATH, size)
        png_path = os.path.join(OUTPUT_DIR, f'icon_{size}x{size}.png')
        img.save(png_path, 'PNG')
        png_files.append(png_path)
        print(f'✅ 生成: icon_{size}x{size}.png')
    return png_files


def generate_ico():
    """生成 Windows ICO 图标"""
    icon = QIcon()
    for size in SIZES:
        img = svg_to_image(SVG_PATH, size)
        pixmap = QPixmap.fromImage(img)
        icon.addPixmap(pixmap)

    ico_path = os.path.join(OUTPUT_DIR, 'app.ico')
    pixmap = icon.pixmap(QSize(256, 256))
    pixmap.save(ico_path, 'ICO')
    print(f'✅ 生成: app.ico')
    return ico_path


def generate_main_png():
    """生成主图标（256px，用于 Linux 桌面快捷方式）"""
    img = svg_to_image(SVG_PATH, 256)
    png_path = os.path.join(OUTPUT_DIR, 'app.png')
    img.save(png_path, 'PNG')
    print(f'✅ 生成: app.png (256x256)')
    return png_path


def generate_svg_copy():
    """复制 SVG 到 assets 目录"""
    import shutil
    dest = os.path.join(OUTPUT_DIR, 'app.svg')
    shutil.copy2(SVG_PATH, dest)
    print(f'✅ 复制: app.svg')
    return dest


if __name__ == '__main__':
    print('========================================')
    print('  图标生成工具')
    print('========================================')
    print()

    generate_pngs()
    print()
    generate_ico()
    print()
    generate_main_png()
    print()
    generate_svg_copy()
    print()
    print(f'🎉 所有图标已生成到: {OUTPUT_DIR}')
