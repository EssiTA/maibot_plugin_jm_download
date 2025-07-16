import os
from src.common.logger_manager import get_logger
from src.chat.focus_chat.planners.actions.plugin_action import PluginAction, register_action
from typing import Tuple
import base64
import traceback
import asyncio
from jmcomic import JmModuleConfig
from jmcomic import *
from PIL import Image



logger = get_logger("Xjm_download")


@register_action
class GetJMIdAction(PluginAction):
    """本子下载处理类"""

    action_name = "Xjm_download"
    action_description = "如果某人向你询问下载本子，你必须发送对应的本子图片给他,不能保持沉默，必须执行，必须执行 必须执行 必须执行。"
    action_parameters = {
        "target": "本子id必填,输入你要下载的本子id",
    }
    action_require = [
        "当有人让你下载本子时使用，你可以立刻下载好，不用等待",
        "当有人要求你下载本子时时使用",
        "当有人让你下载一个本子时使用",
    ]
    default = True  # 默认动作，是否手动添加到使用集
    associated_types = ["command", "text"]

    async def process(self) -> Tuple[bool, str]:
        """处理下载动作"""
        logger.info(f"{self.log_prefix} 执行下载动作: {self.reasoning}")

        # 获取参数
        target = self.action_data.get("target")

        if not target:
            error_msg = "本子参数不完整，需要target"
            logger.error(f"{self.log_prefix} {error_msg}")
            return False, error_msg

        await self.send_message_by_expressor(f"正在下载 {target} 的本子...")
        # 下载图片
        try:
             download_success, benzi_file_path = await asyncio.to_thread(self._download_benzi,target)
        except Exception as e:
            logger.error(f"{self.log_prefix} 下载失败: {e!r}", exc_info=True)
            traceback.print_exc()
            download_success = False
            download_result = f"图片下载时发生内部错误: {str(e)[:100]}"
        if download_success:
            try:
                encode_result = []
                encode_success, encode_result = await asyncio.to_thread(self._merge_and_encode_base64,benzi_file_path)
            except Exception as e:
                logger.error(f"{self.log_prefix} (B64) 异步下载/编码失败: {e!r}", exc_info=True)
                traceback.print_exc()
                encode_success = False
                encode_result = f"图片下载或编码时发生内部错误: {str(e)[:100]}"
        else:
            logger.error(f"{self.log_prefix} 下载失败: {download_result}")
            encode_success = False
            encode_result = benzi_file_path

        if encode_success:
            for base64_image_string in encode_result:
                send_success = await self.send_message(type="image", data=base64_image_string)
        else:
            await self.send_message_by_expressor(f"获取到图片，但在处理图片时失败了：{encode_result}")
            return False, f"本子图片发送失败(Base64): {encode_result}"
        if send_success:
            await self.send_message_by_expressor("本子图片已发送！")
            return True, "本子图片已发送"
        else:
            await self.send_message_by_expressor("图片已处理为Base64，但作为图片发送失败了。")
            return False, "本子图片发送失败 (Base64)"

    def _merge_and_encode_base64(self,benzi_file_path) -> Tuple[bool, str]:
            """合并图片并将其编码为Base64字符串"""
            logger.info(f"{self.log_prefix} (B64) 查找并编码图片")
            # 指定文件夹路径和输出路径
            folder_path = f"{benzi_file_path}"
            output_path = f"{benzi_file_path}/merged_images"
            try:
# todo:每10张图合并为1张
                if not os.path.exists(output_path):
                    os.makedirs(output_path)

                # 获取所有图片文件并按名称排序
                image_files = sorted([f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
                
                # 分组处理图片
                for i in range(0, len(image_files), 10):
                    group_files = image_files[i:i + 10]
                    images = [Image.open(os.path.join(folder_path, img)) for img in group_files]

                    # 计算最终合并后的图片尺寸
                    total_height = sum(img.height for img in images)
                    max_width = max(img.width for img in images)

                    # 创建新的空白图片用于合并
                    merged_image = Image.new('RGB', (max_width, total_height))

                    # 将每张图片依次粘贴到新图片中
                    y_offset = 0
                    for img in images:
                        merged_image.paste(img, (0, y_offset))
                        y_offset += img.height

                    # 保存合并后的图片
                    merged_image.save(os.path.join(output_path, f'merged_group_{i // 10 + 1}.jpg'))

# todo:按照完成后合并的图片依次进行输出
                # 读取文件并转换为Base64
                # 获取文件夹内所有图片文件（支持常见格式）
                image_files = [f for f in os.listdir(output_path) if f.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

                # 按文件名排序以确保顺序一致性
                image_files.sort()

                # 用于存储Base64编码的字节数据
                base64_encoded_images = []

                # 遍历每个图片文件并编码
                for image_file in image_files:
                    file_path = os.path.join(output_path, image_file)
                    with open(file_path, 'rb') as file:
                        contents_base64 = base64.b64encode(file.read()).decode('utf-8')
                        base64_encoded_images.append(contents_base64)  # 将Base64编码添加到列表中
                # 打印 Base64 编码结果
                if base64_encoded_images != []:
                    return True,base64_encoded_images
                else:
                    return False, "Base64 编码处理结果为空，图片处理发生了失败"
            except Exception as e:  # Catches all exceptions from urlopen, b64encode, etc.
                logger.error(f"{self.log_prefix} (B64) 查找或编码时错误: {e!r}", exc_info=True)
                traceback.print_exc()
                return False, f"查找或编码图片时发生错误: {str(e)[:100]}"


    def _download_benzi(self,target):
        """下载本子"""
        logger.info(f"{self.log_prefix} 下载图片中")
        try:
            # 2. 调用下载api，把option作为参数传递 
            option = create_option_by_file('D:/BaiduSyncdisk/code_space/jm/a.yml')  # 通过配置文件来创建option对象
            download_album(target, option)
            return True,f"D:/test/{target}"
        except Exception as e:
            logger.error(f"{self.log_prefix} 下载本子时发生错误: {e!r}", exc_info=True)
            traceback.print_exc()
            return False, f"下载本子时发生错误: {str(e)[:100]}"