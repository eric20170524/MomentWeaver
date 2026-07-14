import numpy as np
import cv2
from PIL import Image, ImageOps, ImageEnhance

def make_seamless_blend(img: Image.Image) -> Image.Image:
    """
    通过象限翻转与中心掩码交叉混合算法，实现无 AI 的图片无缝化平铺处理。
    """
    w, h = img.size
    img_arr = np.array(img.convert("RGB"))
    # 将图像沿着宽高滚动一半（原本的边缘会来到中心，中心会变成四周边缘，确保四周无缝拼合）
    base = np.roll(img_arr, shift=(h//2, w//2), axis=(0, 1))

    # 构建掩码：中心为1，四周边缘为0
    y, x = np.ogrid[0:h, 0:w]
    center_y, center_x = h / 2.0, w / 2.0
    dist_x = np.abs(x - center_x) / center_x
    dist_y = np.abs(y - center_y) / center_y
    
    # Cosine 平滑过渡
    mask_x = np.cos(dist_x * np.pi / 2)
    mask_y = np.cos(dist_y * np.pi / 2)
    mask = mask_x * mask_y
    mask = mask[..., np.newaxis]

    # 将原图（中心无接缝）通过掩码覆盖到滚动的底图（边缘无接缝）上，用梯度隐藏十字缝隙
    blended = img_arr * mask + base * (1 - mask)
    return Image.fromarray(blended.astype(np.uint8))

def generate_normal_map(img: Image.Image, strength: float = 2.0) -> Image.Image:
    """
    使用 Sobel 算子将漫反射贴图的灰度梯度近似转化为法线贴图 (Normal Map)。
    """
    arr = np.array(img.convert("L"))
    sobelx = cv2.Sobel(arr, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(arr, cv2.CV_64F, 0, 1, ksize=3)

    nx = -sobelx * strength / 255.0
    ny = -sobely * strength / 255.0  # OpenGL 标准：+Y Up
    nz = np.ones_like(nx)

    length = np.sqrt(nx**2 + ny**2 + nz**2)
    # 避免除以零
    length[length == 0] = 1.0
    nx /= length
    ny /= length
    nz /= length

    r = ((nx + 1.0) / 2.0 * 255.0).astype(np.uint8)
    g = ((ny + 1.0) / 2.0 * 255.0).astype(np.uint8)
    b = (nz * 255.0).astype(np.uint8)

    normal_arr = np.stack([r, g, b], axis=2)
    return Image.fromarray(normal_arr)

def generate_roughness_map(img: Image.Image, invert: bool = False) -> Image.Image:
    """
    提取灰度并调整对比度以近似粗糙度贴图 (Roughness Map)。
    """
    gray = img.convert("L")
    if invert:
        gray = ImageOps.invert(gray)
    roughness = ImageEnhance.Contrast(gray).enhance(1.2)
    return roughness

def remove_black_background(img: Image.Image) -> Image.Image:
    """
    专门针对黑底特效图 (VFX Sprite Sheet) 的去背与 Alpha 通道提取算法。
    使用 RGB 的最大值作为 Alpha 通道，并解除颜色预乘 (Un-premultiply)，
    以完美保留火焰、魔法等发光特效的半透明光晕边缘，避免生成黑边。
    """
    arr = np.array(img.convert("RGBA")).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    
    # 提取发光强度作为 Alpha (适合纯黑底色的能量/发光特效)
    alpha = np.maximum(np.maximum(r, g), b)
    
    # 解除预乘 (Un-premultiply) 恢复原本纯正的特效颜色
    # 如果不解除，半透明区域的 RGB 值会因为原本的黑色背景而显得很暗
    mask = alpha > 0
    r[mask] = np.clip(r[mask] / (alpha[mask] / 255.0), 0, 255)
    g[mask] = np.clip(g[mask] / (alpha[mask] / 255.0), 0, 255)
    b[mask] = np.clip(b[mask] / (alpha[mask] / 255.0), 0, 255)
    
    arr[:, :, 0] = r
    arr[:, :, 1] = g
    arr[:, :, 2] = b
    arr[:, :, 3] = alpha
    
    return Image.fromarray(arr.astype(np.uint8))
