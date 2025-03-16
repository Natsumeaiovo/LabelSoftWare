
#
# if file_extension.lower() == '.dcm':
#     ds = pydicom.dcmread(self.filePath)
#     raw_img = ds.pixel_array.astype(np.float32)
#
#     # 步骤1：对数处理（Retinex分解）
#     # 添加epsilon防止log(0)
#     epsilon = 1e-6
#     s_log = np.log(raw_img + epsilon)  # 公式(2)-(4)
#
#     # 步骤2：归一化到[-1,1]范围
#     # 计算当前对数图像的范围
#     s_log_min = np.min(s_log)
#     s_log_max = np.max(s_log)
#     # 线性映射到[-1,1]
#     s_log_1 = 2 * (s_log - s_log_min) / (s_log_max - s_log_min) - 1  # 专利中的归一化步骤
#
#     # 步骤3：导向滤波获取基础层
#     base_log = guided_filter(s_log_1, s_log_1, radius=16, eps=0.01)
#     # 映射回原始对数域
#     base_ys_log = (base_log + 1) * (s_log_max - s_log_min) / 2 + s_log_min
#
#     # 步骤4：动态范围映射与细节处理，计算细节层（专利公式(6)）
#     detail_log = s_log - base_ys_log
#
#     # 步骤5：系数分配与合成（专利公式7-8）
#     alpha = 0.5
#     beta = 2.0
#     enhanced_base = alpha * base_ys_log  # 基础层动态范围压缩
#     enhanced_detail = beta * detail_log  # 细节层增强
#     enhanced_log = enhanced_base + enhanced_detail
#
#     # 步骤6：结果输出（专利公式9）
#     # 指数变换恢复线性域
#     enhanced_linear = np.exp(enhanced_log)
#
#     # 恢复原始数值范围
#     original_min = np.min(raw_img)
#     original_max = np.max(raw_img)
#     enhanced_norm = (enhanced_linear - np.min(enhanced_linear)) / \
#                     (np.max(enhanced_linear) - np.min(enhanced_linear)) * \
#                     (original_max - original_min) + original_min
#
#     # DICOM格式兼容处理
#     if ds.PixelRepresentation == 0:  # 无符号整型
#         enhanced_img = np.clip(enhanced_norm, 0, 2 ** ds.BitsStored - 1)
#         output_img = enhanced_img.astype(ds.pixel_array.dtype)
#     else:  # 有符号整型（如CT值）
#         enhanced_img = np.clip(enhanced_norm, -2 ** (ds.BitsStored - 1), 2 ** (ds.BitsStored - 1) - 1)
#         output_img = enhanced_img.astype(ds.pixel_array.dtype)
#     read_img = output_img



# img_16bit = ds.pixel_array.astype(np.int32)
                #
                # # 1. 中值滤波去噪（转为uint16）
                # denoised = cv2.medianBlur(np.clip(img_16bit, 0, 65535).astype(np.uint16), 5)
                #
                # # 2. 动态范围拉伸（保持16位）
                # min_val = np.percentile(denoised, 0.5)
                # max_val = np.percentile(denoised, 99.5)
                # stretched = ((denoised.astype(np.float32) - min_val) /
                #              (max_val - min_val) * 65535).astype(np.uint16)
                #
                # # 3. 小波边缘增强（需float32输入）
                # coeffs = pywt.dwt2(stretched.astype(np.float32), 'haar')
                # cA, (cH, cV, cD) = coeffs
                # cH *= 1.5
                # cV *= 1.5  # 增强系数
                # enhanced = pywt.idwt2((cA, (cH, cV, cD)), 'haar')
                #
                # # 4. 非线性对比度调整（Gamma校正）
                # gamma = 0.7  # <1 增强暗部细节
                # gamma_corrected = np.power(enhanced / 65535.0, gamma) * 65535
                # final_16bit = gamma_corrected.astype(np.uint16)

                # read_img = final_16bit