import os
from src.common.logger_manager import get_logger
from src.chat.focus_chat.planners.actions.plugin_action import PluginAction, register_action
from typing import Tuple
import base64
import traceback
import asyncio
from jmcomic import JmModuleConfig
from jmcomic import *


logger = get_logger("Xjm_download")


@register_action
class GetJMIdAction(PluginAction):
    """本子下载处理类"""

    action_name = "Xjm_download"
    action_description = "如果某人向你询问下载本子，你必须发送对应的本子图片给他。"
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
            base64_image_string = encode_result
            send_success = await self.send_message(type="image", data=base64_image_string)
            if send_success:
                await self.send_message_by_expressor("本子图片已发送！")
                return True, "本子图片已发送"
            else:
                await self.send_message_by_expressor("图片已处理为Base64，但作为图片发送失败了。")
                return False, "本子图片发送失败 (Base64)"
        else:
            await self.send_message_by_expressor(f"获取到图片，但在处理图片时失败了：{encode_result}")
            return False, f"本子图片发送失败(Base64): {encode_result}"

    def _merge_and_encode_base64(self,benzi_file_path) -> Tuple[bool, str]:
            """合并图片并将其编码为Base64字符串"""
            logger.info(f"{self.log_prefix} (B64) 查找并编码图片")
            # 指定文件夹路径和输出路径
            folder_path = f"{benzi_file_path}"
            output_path = f"{benzi_file_path}/merged_image.jpg"
            try:
                # 获取文件夹中的所有图片文件
                image_files = [f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                
                # 按文件名排序（可以根据需要调整排序规则）
                image_files.sort()

                # 打开所有图片并获取图片尺寸
                images = [Image.open(os.path.join(folder_path, img)) for img in image_files]
                widths, heights = zip(*(img.size for img in images))  # 获取每个图片的宽度和高度

                # 计算总宽度和总高度（假设所有图片宽度一致，以最大宽度为准）
                total_width = max(widths)
                total_height = sum(heights)

                # 创建一个空白的长图，背景为白色，可根据需要调整为其他颜色
                long_image = Image.new('RGB', (total_width, total_height), (255, 255, 255))

                # 按顺序将每张图片粘贴到长图上
                y_offset = 0
                for img in images:
                    long_image.paste(img, (0, y_offset))  # 将图片粘贴到指定位置
                    y_offset += img.size[1]  # 更新 y 偏移量

                # 保存合并后的长图
                long_image.save(output_path)
                logger.info(f"合并完成，长图已保存为：{output_path}")
                # 读取文件并转换为Base64
                with open(output_path, "rb") as file:  # 以二进制形式读取文件
                    # 将文件内容编码为 Base64
                    base64_encoded_image = base64.b64encode(file.read()).decode('utf-8')
                    logger.info(f"：{str(base64_encoded_image)[:100]}")
                # 打印 Base64 编码结果
                if base64_encoded_image != "":
                    return True,base64_encoded_image
                else:
                    return False, "Base64 编码结果为空，图片处理发生了失败"
            except Exception as e:  # Catches all exceptions from urlopen, b64encode, etc.
                logger.error(f"{self.log_prefix} (B64) 查找或编码时错误: {e!r}", exc_info=True)
                traceback.print_exc()
                return False, f"查找或编码图片时发生错误: {str(e)[:100]}"


    def _download_benzi(self,target):
        """下载本子"""
        logger.info(f"{self.log_prefix} 下载图片中")
        try:
            # 2. 调用下载api，把option作为参数传递 
            JmModuleConfig.PFIELD_ADVICE['myname'] = lambda photo: f'{photo.id}'
            option = create_option_by_file('D:/BaiduSyncdisk/code_space/jm/a.yml')  # 通过配置文件来创建option对象
            download_album(target, option)
            return True,f"D:/test/{target}"
        except Exception as e:
            logger.error(f"{self.log_prefix} 下载本子时发生错误: {e!r}", exc_info=True)
            traceback.print_exc()
            return False, f"下载本子时发生错误: {str(e)[:100]}"