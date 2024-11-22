from PIL import Image
import os

def extract_tif_frames(input_file_path, output_dir):
    # 打开输入的tif文件
    img = Image.open(input_file_path)

    # 获取tif文件中的帧数
    num_frames = img.n_frames

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 循环遍历每一帧并将其保存为新的tif文件
    for i in range(num_frames):
        img.seek(i)
        output_file_path = os.path.join(output_dir, f'frame_{i + 1}.tif')
        img.save(output_file_path)
        print(f'已保存第 {i + 1} 帧到 {output_file_path}')

if __name__ == '__main__':
    input_file_path = r'D:\621-Ti\1-1 (9).tif'
    output_dir = './'
    extract_tif_frames(input_file_path, output_dir)
