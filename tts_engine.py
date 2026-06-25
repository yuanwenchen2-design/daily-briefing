"""
每日简报 - 语音合成模块
使用 Microsoft Edge TTS (edge-tts) 生成语音
支持: 中文普通话、英语、粤语
"""
import asyncio
import logging
from pathlib import Path

from config import AUDIO_DIR, LANGUAGES

logger = logging.getLogger(__name__)


async def _generate_single(
    text: str, voice: str, output_path: str
) -> bool:
    """生成单个音频文件"""
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        logger.error(f"TTS 生成失败 [{voice}]: {e}")
        return False


async def generate_briefing_audio(
    plain_text: str, language: str = "chinese"
) -> str | None:
    """
    将简报文本转为语音 MP3 文件。

    参数:
        plain_text: 纯文本简报
        language: 语言代码

    返回:
        MP3 文件路径，失败返回 None
    """
    lang_info = LANGUAGES.get(language, LANGUAGES["chinese"])
    voice = lang_info["voice"]

    # 清理文本（移除特殊字符，保留标点）
    clean_text = plain_text.strip()

    if not clean_text:
        logger.warning("简报文本为空，跳过 TTS")
        return None

    # 输出文件
    output_path = AUDIO_DIR / f"briefing_{language}.mp3"

    logger.info(f"生成 TTS 音频: {lang_info['name']} ({voice})")
    success = await _generate_single(clean_text, voice, str(output_path))

    if success:
        logger.info(f"音频已保存: {output_path}")
        return str(output_path)
    else:
        return None


def generate_briefing_audio_sync(plain_text: str, language: str = "chinese") -> str | None:
    """同步封装，方便在非异步上下文中调用"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_briefing_audio(plain_text, language),
                )
                return future.result(timeout=120)
        else:
            return asyncio.run(generate_briefing_audio(plain_text, language))
    except RuntimeError:
        return asyncio.run(generate_briefing_audio(plain_text, language))
    except Exception as e:
        logger.error(f"TTS 同步调用失败: {e}")
        return None


# --- 预定义语音列表（供参考）---
AVAILABLE_VOICES = {
    "chinese": [
        "zh-CN-XiaoxiaoNeural",  # 女声（默认）
        "zh-CN-YunxiNeural",     # 男声
        "zh-CN-XiaoyiNeural",    # 女声
    ],
    "english": [
        "en-US-JennyNeural",     # 女声（默认）
        "en-US-GuyNeural",       # 男声
        "en-US-AriaNeural",      # 女声
    ],
    "cantonese": [
        "zh-HK-HiuMaanNeural",   # 女声（默认）
        "zh-HK-WanLungNeural",   # 男声
    ],
}
