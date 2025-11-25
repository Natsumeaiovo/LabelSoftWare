import os
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import copy
from PIL import Image, ImageEnhance, ImageFilter


def add_noise(image, noise_type="gaussian", amount=0.02):
    """为图像添加不同类型的噪声（进一步降低了噪声强度）"""
    image_np = np.array(image).astype(np.float32) / 255.0

    if noise_type == "gaussian":
        noise = np.random.normal(0, amount, image_np.shape)
        noisy_image = image_np + noise
    elif noise_type == "salt_pepper":
        noise = np.random.random(image_np.shape)
        noisy_image = image_np.copy()
        noisy_image[noise < amount / 2] = 0
        noisy_image[noise > 1 - amount / 2] = 1

    # 将值限制在有效范围 [0, 1]
    noisy_image = np.clip(noisy_image, 0, 1)
    return Image.fromarray((noisy_image * 255).astype(np.uint8))


def gamma_correction(image, gamma=1.0):
    """伽马校正函数"""
    img_array = np.array(image).astype(np.float32) / 255.0

    # 应用伽马校正公式
    corrected = np.power(img_array, gamma)

    # 将值限制在有效范围 [0, 1]
    corrected = np.clip(corrected, 0, 1)
    return Image.fromarray((corrected * 255).astype(np.uint8))


def apply_distortion(image, k1, k2=0, p1=0, p2=0):
    """
    对图像应用镜头畸变（桶形或枕形），并自动裁剪黑边。
    :param image: PIL.Image 对象。
    :param k1: 径向畸变系数。正值产生桶形畸变，负值产生枕形畸变。
    :param k2, p1, p2: 其他畸变系数，这里可以保持为0。
    :return: 畸变后的 PIL.Image 对象。
    """
    # 将 PIL 图像转换为 OpenCV 格式
    img_np = np.array(image)
    h, w = img_np.shape[:2]

    # 定义虚拟相机矩阵
    K = np.array([[w, 0, w / 2],
                  [0, h, h / 2],
                  [0, 0, 1]], dtype=np.float32)

    # 定义畸变系数
    D = np.array([k1, k2, p1, p2], dtype=np.float32)

    # 计算最佳的新相机矩阵，alpha=0表示缩放图像以完全去除黑边
    new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), alpha=0)

    # 计算畸变映射
    map1, map2 = cv2.initUndistortRectifyMap(K, D, None, new_K, (w, h), cv2.CV_32FC1)

    # 应用畸变
    distorted_img_np = cv2.remap(img_np, map1, map2, interpolation=cv2.INTER_LINEAR)

    # 将 OpenCV 图像转换回 PIL 格式
    return Image.fromarray(distorted_img_np)

def transform_distortion_bbox(bbox, img_width, img_height, aug_name):
    """
    根据给定的畸变增强名称，变换标注框的坐标。
    :param bbox: 原始标注框 (x1, y1, x2, y2)。
    :param img_width: 图像宽度。
    :param img_height: 图像高度。
    :param aug_name: 畸变增强的名称。
    :return: 变换后的新标注框 (new_x1, new_y1, new_x2, new_y2)。
    """
    # 增强名称到 k1 畸变系数的映射
    distortion_map = {
        "distorted_barrel_medium": 0.6,
        "distorted_barrel_strong": 0.8,
        "distorted_pincushion_medium": -0.5,
        "distorted_pincushion_strong": -0.8,
        "distorted_barrel_very_strong": 1.2,
    }

    k1 = distortion_map.get(aug_name)
    if k1 is None:
        # 如果不是已知的畸变名称，则不进行变换
        return bbox

    x1, y1, x2, y2 = bbox
    w, h = img_width, img_height

    # --- 重建与 apply_distortion 中完全相同的变换管线 ---
    # 定义虚拟相机矩阵
    K = np.array([[w, 0, w / 2], [0, h, h / 2], [0, 0, 1]], dtype=np.float32)
    # 定义畸变系数
    D = np.array([k1, 0, 0, 0], dtype=np.float32)
    # 计算最佳的新相机矩阵以去除黑边
    new_K, _ = cv2.getOptimalNewCameraMatrix(K, D, (w, h), alpha=0)

    # 定义标注框的四个角点
    points = np.array([
        [x1, y1],
        [x1, y2],
        [x2, y1],
        [x2, y2]
    ], dtype=np.float32)

    # 将点重塑为 cv2.undistortPoints 需要的格式 (N, 1, 2)
    points = points.reshape(-1, 1, 2)

    # 应用畸变变换到这些点上
    undistorted_points = cv2.undistortPoints(points, K, D, P=new_K)

    # 从变换后的点中找到新的边界
    undistorted_points = undistorted_points.reshape(-1, 2)
    new_x1 = np.min(undistorted_points[:, 0])
    new_y1 = np.min(undistorted_points[:, 1])
    new_x2 = np.max(undistorted_points[:, 0])
    new_y2 = np.max(undistorted_points[:, 1])

    return new_x1, new_y1, new_x2, new_y2


def augment_image(image_path, output_dir, aug_num):
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 加载原始图像
    img = Image.open(image_path).convert('RGB')
    file_name = Path(image_path).stem
    ext = Path(image_path).suffix

    augmented_images = []

    # 原始图像（保留作参考，不会再次保存）
    augmented_images.append(("original", img))

    # 1-5. 图像畸变增强（5张），参数已调大且无黑边
    distorted_barrel_medium = apply_distortion(img, k1=0.6)
    distorted_barrel_strong = apply_distortion(img, k1=0.8)
    distorted_pincushion_medium = apply_distortion(img, k1=-0.5)
    distorted_pincushion_strong = apply_distortion(img, k1=-0.8)
    distorted_barrel_very_strong = apply_distortion(img, k1=1.2)
    augmented_images.append(("distorted_barrel_medium", distorted_barrel_medium))
    augmented_images.append(("distorted_barrel_strong", distorted_barrel_strong))
    augmented_images.append(("distorted_pincushion_medium", distorted_pincushion_medium))
    augmented_images.append(("distorted_pincushion_strong", distorted_pincushion_strong))
    augmented_images.append(("distorted_barrel_very_strong", distorted_barrel_very_strong))

    # 6-7. 翻转（2张图像）
    flip_horizontal = img.transpose(Image.FLIP_LEFT_RIGHT)
    flip_vertical = img.transpose(Image.FLIP_TOP_BOTTOM)
    augmented_images.append(("horizontal_flip", flip_horizontal))
    augmented_images.append(("vertical_flip", flip_vertical))

    # 8-10. 旋转（3张图像）
    rotate_90 = img.rotate(90, expand=True)
    rotate_180 = img.rotate(180)
    rotate_270 = img.rotate(270, expand=True)
    augmented_images.append(("rotate_90", rotate_90))
    augmented_images.append(("rotate_180", rotate_180))
    augmented_images.append(("rotate_270", rotate_270))

    # 11-16. 亮度和对比度调整（6张图像）
    brightness_enhancer = ImageEnhance.Brightness(img)
    brightness_low = brightness_enhancer.enhance(0.7)
    brightness_high = brightness_enhancer.enhance(1.3)

    contrast_enhancer = ImageEnhance.Contrast(img)
    contrast_low = contrast_enhancer.enhance(0.7)
    contrast_high = contrast_enhancer.enhance(1.3)

    # 组合亮度和对比度调整
    contrast_brightness_low = ImageEnhance.Contrast(brightness_low).enhance(0.7)
    contrast_brightness_high = ImageEnhance.Contrast(brightness_high).enhance(1.3)

    augmented_images.append(("brightness_low", brightness_low))
    augmented_images.append(("brightness_high", brightness_high))
    augmented_images.append(("contrast_low", contrast_low))
    augmented_images.append(("contrast_high", contrast_high))
    augmented_images.append(("contrast_brightness_low", contrast_brightness_low))
    augmented_images.append(("contrast_brightness_high", contrast_brightness_high))

    # 17-18. 添加噪声（减少到2张图像，进一步降低噪声强度）
    gaussian_noise = add_noise(img, "gaussian", 0.02)  # 降低噪声强度
    # 去掉了salt_pepper_noise（颗粒感较大）
    noisy_contrast = add_noise(contrast_high, "gaussian", 0.015)  # 进一步降低噪声强度

    augmented_images.append(("gaussian_noise", gaussian_noise))
    augmented_images.append(("noisy_contrast", noisy_contrast))

    # 19. 图像锐化增强
    sharpened = img.filter(ImageFilter.SHARPEN)
    sharpened_more = sharpened.filter(ImageFilter.SHARPEN)  # 应用两次以获得更强效果
    augmented_images.append(("sharpened", sharpened_more))

    # 20-21. 伽马校正（增强暗区域细节）
    gamma_low = gamma_correction(img, gamma=0.7)  # 增强亮区域
    gamma_high = gamma_correction(img, gamma=1.5)  # 增强暗区域
    augmented_images.append(("gamma_low", gamma_low))
    augmented_images.append(("gamma_high", gamma_high))

    # 22. 模糊增强（模拟不同焦距）
    # 只保留一种程度的模糊
    blurred_light = img.filter(ImageFilter.GaussianBlur(radius=1))
    augmented_images.append(("blurred_light", blurred_light))

    # --- 图像选择逻辑 ---
    candidate_augmentations = augmented_images[1:]  # 排除原始图像
    images_to_save = []

    if aug_num > 0:
        if aug_num < 10:
            # 小于10，取前后各半
            front_count = aug_num // 2
            back_count = aug_num - front_count
            front_images = candidate_augmentations[:front_count]
            back_images = candidate_augmentations[-back_count:]
            images_to_save = front_images + back_images
        else:  # aug_num >= 10
            # 大于等于10，随机选取
            if aug_num >= len(candidate_augmentations):
                images_to_save = candidate_augmentations
            else:
                images_to_save = random.sample(candidate_augmentations, aug_num)

    # 从将要保存的图像列表中提取增强方法的名称
    aug_func_list = [name for name, img in images_to_save]

    # 保存所选的增强图像
    for i, (name, img_to_save) in enumerate(images_to_save, 2):
        output_path = os.path.join(output_dir, f"{file_name}({i}){ext}")
        img_to_save.save(output_path)
        print(f"已保存: {output_path}")

    print(f"共创建增强图像: {len(images_to_save)}张")

    # 返回增强方法名称列表
    return aug_func_list


def process_single_image(image_path, output_dir, xml_path, xml_output_dir, aug_num):
    """处理单张图像，为每个增强图像生成新的XML标注文件"""
    file_name = Path(image_path).stem
    ext = Path(image_path).suffix

    # 执行图像增强
    aug_func_list = augment_image(image_path, output_dir, aug_num)
    # 使用 shutil.copy 复制文件，原始文件会保留在原位
    # 增强完成后，将原图复制并重命名为 原文件名(1).ext 到输出目录
    copied_path = os.path.join(output_dir, f"{file_name}(1){ext}")
    shutil.copy(image_path, copied_path)
    print(f"已将原图复制到: {copied_path}")

    # 根据增强函数列表，为每个增强图像生成新的XML标注文件。
    save_new_xml(xml_path, xml_output_dir, aug_func_list)
    # 同样地，复制原始XML文件并重命名为 原文件名(1).xml
    copied_xml_path = os.path.join(xml_output_dir, f"{file_name}(1).xml")
    shutil.copy(xml_path, copied_xml_path)
    print(f"已将原XML复制到: {copied_xml_path}")


def save_new_xml(xml_path, xml_output_dir, aug_func_list):
    """
    根据增强函数列表，为每个增强图像生成新的XML标注文件。

    :param xml_path: 原始XML文件的路径。
    :param xml_output_dir: 新XML文件的输出目录。
    :param aug_func_list: 应用于图像的增强方法名称列表。
    """
    # 确保输出目录存在
    os.makedirs(xml_output_dir, exist_ok=True)

    # 1. 解析原始XML文件
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 提取原始信息
    p = Path(root.find('filename').text)
    original_stem = p.stem
    original_ext = p.suffix

    original_path_text = root.find('path').text
    original_path_dir = str(Path(original_path_text).parent)

    size_node = root.find('size')
    W = int(size_node.find('width').text)
    H = int(size_node.find('height').text)

    # 2. 遍历增强列表，为每个增强方法生成一个XML文件
    for i, aug_name in enumerate(aug_func_list, 2):
        new_root = copy.deepcopy(root)

        # 3. 更新文件名和路径
        new_filename = f"{original_stem}({i}){original_ext}"
        new_root.find('filename').text = new_filename
        # 将原始目录与新文件名结合，生成新的path
        new_path = os.path.join(original_path_dir, new_filename)
        new_root.find('path').text = new_path

        # 4. 根据增强方法更新bndbox和size
        # 只有在旋转90/270度时，尺寸会改变
        current_W, current_H = W, H
        if aug_name in ["rotate_90", "rotate_270"]:
            current_W, current_H = H, W
            new_root.find('size/width').text = str(current_W)
            new_root.find('size/height').text = str(current_H)

        # 遍历所有object标签
        for obj in new_root.findall('object'):
            bndbox = obj.find('bndbox')
            x1 = float(bndbox.find('xmin').text)
            y1 = float(bndbox.find('ymin').text)
            x2 = float(bndbox.find('xmax').text)
            y2 = float(bndbox.find('ymax').text)

            new_x1, new_y1, new_x2, new_y2 = x1, y1, x2, y2

            # --- 优先处理畸变 ---
            if aug_name.startswith("distorted_"):
                new_x1, new_y1, new_x2, new_y2 = transform_distortion_bbox((x1, y1, x2, y2), W, H, aug_name)
            elif aug_name == "horizontal_flip":
                new_x1 = W - x2
                new_x2 = W - x1
            elif aug_name == "vertical_flip":
                new_y1 = H - y2
                new_y2 = H - y1
            elif aug_name == "rotate_180":
                new_x1 = W - x2
                new_y1 = H - y2
                new_x2 = W - x1
                new_y2 = H - y1
            elif aug_name == "rotate_90": # 逆时针90度
                new_x1 = y1
                new_y1 = W - x2
                new_x2 = y2
                new_y2 = W - x1
            elif aug_name == "rotate_270": # 逆时针270度
                new_x1 = H - y2
                new_y1 = x1
                new_x2 = H - y1
                new_y2 = x2

            # 更新bndbox坐标
            bndbox.find('xmin').text = str(new_x1)
            bndbox.find('ymin').text = str(new_y1)
            bndbox.find('xmax').text = str(new_x2)
            bndbox.find('ymax').text = str(new_y2)

        # 5. 保存新的XML文件
        new_xml_filename = f"{original_stem}({i}).xml"
        new_xml_path = os.path.join(xml_output_dir, new_xml_filename)
        new_tree = ET.ElementTree(new_root)
        new_tree.write(new_xml_path, encoding='utf-8', xml_declaration=True)
        print(f"已保存: {new_xml_path}")


def handle_xml(xml_path: str) -> Tuple[List[str], List[str]]:
    """
    解析指定目录下的所有XML文件，提取图像路径和缺陷名称。

    :param xml_path: 包含XML文件的目录路径。
    :return: 一个元组，包含两个列表：image_path_list 和 defect_list。
    """
    image_path_list = []
    defect_list = []

    # 遍历目录中的所有文件
    for filename in os.listdir(xml_path):
        if not filename.endswith('.xml'):
            continue

        xml_file_path = os.path.join(xml_path, filename)

        try:
            # 解析XML文件
            tree = ET.parse(xml_file_path)
            root = tree.getroot()

            # 查找path标签并提取文本
            path_element = root.find('path')
            if path_element is not None:
                image_path_list.append(path_element.text)
            else:
                # 如果找不到path，可以添加一个占位符或记录错误
                image_path_list.append(None)

            # 查找object/name标签并提取文本
            name_element = root.find('object/name')
            if name_element is not None:
                defect_list.append(name_element.text)
            else:
                # 如果找不到name，可以添加一个占位符或记录错误
                defect_list.append(None)

        except ET.ParseError as e:
            print(f"解析XML文件失败: {xml_file_path}, 错误: {e}")

    return image_path_list, defect_list


# 在这里直接设置您的图像路径和输出目录
def main(image_path, output_dir):
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 判断是文件还是目录
    if os.path.isdir(image_path):
        # 如果是目录，处理目录中所有支持的图像文件
        processed_count = 0
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']

        for file in os.listdir(image_path):
            file_path = os.path.join(image_path, file)
            if os.path.isfile(file_path) and Path(file_path).suffix.lower() in image_extensions:
                process_single_image(file_path, output_dir)
                processed_count += 1

        print(f"共处理了 {processed_count} 张图像")
    else:
        # 如果是单个文件，直接处理
        process_single_image(image_path, output_dir)


if __name__ == "__main__":
    # image_path = "./表7海绵状疏松(3.2mm)/8.png"  # 可以是图像文件或目录
    # xml标注标签与增强数量的map
    label_to_aug_num_map = {
        'GM': 0,
        'DM': 6,
        'QK': 10,
        'SS': 15,
        'SK': 20,
        'LW': 20
    }
    xml_dir = "./testImage-XML"
    # 根据xml目录，读取到所有的图像路径，缺陷路径（每个图像对应一个缺陷）
    image_path_list, defect_list = handle_xml(xml_dir)
    img_output_dir = "./output"  # 请替换为您的输出目录
    xml_output_dir = "./output-XML"
    for i in range(len(image_path_list)):
        image_path = image_path_list[i]
        defect_label = defect_list[i]

        # 使用 .get() 方法获取增强数量，如果标签不存在于map中，则默认为0
        aug_num = label_to_aug_num_map.get(defect_label, 0)
        if image_path:
            # 从图像路径构建对应的XML文件路径
            # 从 '.../testImage/SS1.png' 得到 'SS1'
            image_stem = Path(image_path).stem
            # 拼接成 '.../testImage-XML/SS1.xml'
            specific_xml_path = os.path.join(xml_dir, f"{image_stem}.xml")
            if os.path.exists(specific_xml_path):
                # 将具体的XML文件路径传递给处理函数
                process_single_image(image_path, img_output_dir, specific_xml_path, xml_output_dir, aug_num)
            else:
                print(f"找不到对应的XML文件 {specific_xml_path}")
        else:
            print(f"图像路径不存在或无效: {image_path}")
