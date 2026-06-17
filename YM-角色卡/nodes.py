import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .prompts import (
    FALLBACK_PROMPT_TEMPLATE,
    FALLBACK_REQUIREMENTS,
    PROMPT_TYPE_OPTIONS,
    USER_PROMPT_TEMPLATE,
    load_system_prompt,
)


LLM_BASE_URL = "https://llm.runninghub.cn/v1"
LLM_MODELS_URL = "https://llm.runninghub.ai/v1/models"
LLM_CHAT_URL = f"{LLM_BASE_URL}/chat/completions"
CHAT_MAX_RETRIES = 3
DEFAULT_MODEL = "google/gemini-3.1-flash-lite-preview"
DEFAULT_TIMEOUT_SECONDS = 180
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "qwen/qwen3-vl-235b-a22b-instruct",
    "qwen/qwen-plus",
    "qwen/qwen-max",
    "qwen/qwen3-235b-a22b-2507",
    "deepseek/deepseek-v3.2",
    "deepseek/deepseek-chat",
    "rh-llm-o/rh-t-55",
    "rh-llm-o/rh-t-54",
    "rh-llm-g/rh-g-flash-preview-3",
    "rh-llm-g/rh-g-pro-preview-31",
]


def _fetch_rh_models():
    try:
        request = urllib.request.Request(LLM_MODELS_URL, method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [
            str(item.get("id")).strip()
            for item in data.get("data", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        ]
        if models:
            return models
    except Exception as exc:
        print(f"[YM-角色卡] Failed to fetch RH model list, using fallback models. Error: {type(exc).__name__}")
    return list(FALLBACK_MODELS)


def _default_model(models):
    return DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]


def _load_rh_openapi_helpers():
    try:
        from ComfyUI_RH_OpenAPI.core.api_key import get_config
        from ComfyUI_RH_OpenAPI.core.image import tensor_to_pil
        from ComfyUI_RH_OpenAPI.core.upload import upload_file

        return get_config, tensor_to_pil, upload_file
    except Exception:
        pass

    custom_nodes_dir = Path(__file__).resolve().parents[1]
    rh_dir = custom_nodes_dir / "ComfyUI_RH_OpenAPI"
    if rh_dir.exists():
        parent = str(custom_nodes_dir)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        try:
            from ComfyUI_RH_OpenAPI.core.api_key import get_config
            from ComfyUI_RH_OpenAPI.core.image import tensor_to_pil
            from ComfyUI_RH_OpenAPI.core.upload import upload_file

            return get_config, tensor_to_pil, upload_file
        except Exception:
            pass

    raise RuntimeError("未找到 ComfyUI_RH_OpenAPI。请先安装 RH OpenAPI 插件。")


def _images_to_jpeg_bytes(images, tensor_to_pil):
    image_bytes = []
    for image in images:
        for pil_image in tensor_to_pil(image):
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            buffer = io.BytesIO()
            pil_image.save(buffer, format="JPEG", quality=90)
            image_bytes.append(buffer.getvalue())
    return image_bytes


def _upload_images(images, config, tensor_to_pil, upload_file):
    urls = []
    for index, jpeg_bytes in enumerate(_images_to_jpeg_bytes(images, tensor_to_pil), start=1):
        url = upload_file(
            jpeg_bytes,
            f"ym_character_card_image_{index}.jpg",
            "image/jpeg",
            config["api_key"],
            config["base_url"],
            timeout=config.get("upload_timeout", 60),
            logger_prefix=f"YM_CharacterCard_Image{index}",
        )
        urls.append(url)
    return urls


def _extract_json_object(text):
    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _extract_prompt(text):
    data = _extract_json_object(text)
    prompt = data.get("prompt") if isinstance(data, dict) else None
    if prompt:
        return _clean_output_prompt(str(prompt))
    return _clean_output_prompt(str(text or ""))


def _clean_output_prompt(prompt):
    text = str(prompt or "").strip()
    if not text:
        return ""

    unwanted_clauses = {
        "no text",
        "no title",
        "no label",
        "no labels",
        "no number",
        "no numbers",
        "no dividing line",
        "no dividing lines",
        "no border",
        "no borders",
        "no table line",
        "no table lines",
        "no complex background",
        "no story scene",
        "no poster style",
        "no expression thumbnail",
        "no expression thumbnails",
        "no action pose group",
        "no pose references",
        "no pose reference area",
        "no extra pose figures",
        "no repeated expressions",
        "do not repeat expressions",
    }
    unwanted_patterns = [
        r"^不要(加入|出现|使用|写)?(任何)?(标题|编号|英文标签|中文标签|说明文字|分隔线|边框|虚线|表格线|复杂背景|故事场景|海报风格|动作姿态组|姿态参考区|额外小人姿态|重复表情).*",
        r"^不要让\s*4\s*个小表情重复.*",
    ]

    sentences = re.split(r"(?<=[。.!?])\s*|\n+", text)
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if any(re.search(pattern, sentence, flags=re.I) for pattern in unwanted_patterns):
            continue

        clauses = re.split(r"[,，]\s*", sentence)
        cleaned_clauses = []
        for clause in clauses:
            stripped = clause.strip().strip(".。")
            if not stripped:
                continue
            if stripped.lower() in unwanted_clauses:
                continue
            cleaned_clauses.append(clause.strip())
        if cleaned_clauses:
            cleaned_sentences.append("，".join(cleaned_clauses).strip(" ，,"))

    if not cleaned_sentences:
        return text

    result = "。".join(cleaned_sentences)
    result = re.sub(r"\s+", " ", result).strip(" ，,")
    result = re.sub(r"。{2,}", "。", result)
    return result


def _build_messages(system_prompt, user_prompt, image_urls):
    content = [{"type": "text", "text": user_prompt}]

    if image_urls:
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        return [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": content},
        ]

    return [
        {"role": "system", "content": system_prompt or ""},
        {"role": "user", "content": user_prompt or ""},
    ]


def _post_json_with_retries(url, headers, payload, timeout):
    last_error = None
    for attempt in range(CHAT_MAX_RETRIES):
        if attempt > 0:
            time.sleep(min(2 ** attempt, 5))

        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code}: {text[:300]}")
            if exc.code < 500 and exc.code != 429:
                raise last_error
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError("RH LLM request failed.")


def _post_rh_llm(model, system_prompt, user_prompt, face_image, outfit_image, timeout, api_config=None):
    get_config, tensor_to_pil, upload_file = _load_rh_openapi_helpers()
    config = get_config(api_config)
    images = [image for image in (face_image, outfit_image) if image is not None]
    image_urls = _upload_images(images, config, tensor_to_pil, upload_file) if images else []

    payload = {
        "model": model,
        "messages": _build_messages(system_prompt, user_prompt, image_urls),
        "temperature": 0.35,
        "max_tokens": 4096,
        "top_p": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "reasoning_effort": "none",
    }

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    data = _post_json_with_retries(LLM_CHAT_URL, headers, payload, timeout)

    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def _fallback_prompt(prompt_type, character_brief, visual_style):
    subject = character_brief.strip() or "original character"
    return _clean_output_prompt(FALLBACK_PROMPT_TEMPLATE.format(
        subject=subject,
        specific_requirements=f"{FALLBACK_REQUIREMENTS[prompt_type]}. Visual style: {visual_style}",
    ))


def _build_visual_style(preset, custom_style):
    preset_map = {
        "自定义": "",
        "专业动漫设定稿": "professional anime character design sheet, clean linework, accurate proportions, high detail, polished production-ready reference sheet",
        "写实角色设定稿": "realistic character design sheet, natural anatomy, realistic facial structure, detailed fabric and material rendering, clean studio reference",
        "国风角色设定稿": "Chinese fantasy character design sheet, elegant silhouette, refined costume structure, traditional-inspired fabric details, clean professional reference",
        "二次元游戏立绘设定": "anime game character design sheet, appealing game character proportions, clear costume layers, polished key visual reference, clean linework",
        "3D建模参考设定": "3D modeling reference sheet, orthographic views, consistent proportions, clear front side back silhouettes, readable material and accessory details",
        "厚涂概念设定": "painterly concept art character sheet, refined brushwork, strong shape design, detailed costume and material notes, clean presentation",
        "简洁线稿设定": "clean line art character design sheet, minimal shading, precise outlines, readable shapes, clear costume construction",
    }
    base_style = preset_map.get(preset, preset)
    if preset == "自定义":
        return custom_style.strip() or preset_map["写实角色设定稿"]
    if custom_style.strip():
        return f"{base_style}, {custom_style.strip()}"
    return base_style


class CharacterCardPromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        models = _fetch_rh_models()
        return {
            "required": {
                "prompt_type": (
                    PROMPT_TYPE_OPTIONS,
                    {"default": "人物角色卡"},
                ),
                "character_brief": (
                    "STRING",
                    {
                        "default": "一个原创人物角色。请在这里写角色简介、外貌、服装、气质，以及本次生成的额外要求。",
                        "multiline": True,
                    },
                ),
                "rh_model": (models, {"default": _default_model(models)}),
                "visual_style_preset": (
                    [
                        "自定义",
                        "专业动漫设定稿",
                        "写实角色设定稿",
                        "国风角色设定稿",
                        "二次元游戏立绘设定",
                        "3D建模参考设定",
                        "厚涂概念设定",
                        "简洁线稿设定",
                    ],
                    {"default": "专业动漫设定稿"},
                ),
                "custom_visual_style": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                    },
                ),
            },
            "optional": {
                "face_reference_image": ("IMAGE",),
                "outfit_reference_image": ("IMAGE",),
                "api_config": ("RH_OPENAPI_CONFIG",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("提示词",)
    FUNCTION = "build"
    CATEGORY = "YM-角色卡/提示词"

    def build(
        self,
        prompt_type,
        character_brief,
        rh_model,
        visual_style_preset,
        custom_visual_style,
        face_reference_image=None,
        outfit_reference_image=None,
        api_config=None,
    ):
        system_prompt = load_system_prompt(prompt_type, outfit_reference_image is not None)
        visual_style = _build_visual_style(visual_style_preset, custom_visual_style)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            prompt_type=prompt_type,
            character_brief=character_brief.strip(),
            face_reference_note=(
                "已连接面部参考图。请读取参考图中的脸型、五官、发型、发色、表情气质和头部轮廓。"
                if face_reference_image is not None
                else "未提供面部参考图。请根据角色简介/生成要求生成稳定的面部描述。"
            ),
            outfit_reference_note=(
                "已连接服装参考图。请读取参考图中的服装版型、层次、材质、颜色、纹样和配件。"
                if outfit_reference_image is not None
                else "未提供服装参考图。请根据角色简介/生成要求生成稳定的服装描述。"
            ),
            visual_style=visual_style.strip(),
            language="中文",
        )

        prompt = ""
        try:
            raw_response = _post_rh_llm(
                rh_model,
                system_prompt,
                user_prompt,
                face_reference_image,
                outfit_reference_image,
                DEFAULT_TIMEOUT_SECONDS,
                api_config,
            )
            prompt = _extract_prompt(raw_response)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
            print(f"[YM-角色卡] RH LLM call failed, fallback prompt generated. Error: {exc}")

        if not prompt:
            prompt = _fallback_prompt(prompt_type, character_brief.strip(), visual_style)

        return (_clean_output_prompt(prompt),)


NODE_CLASS_MAPPINGS = {
    "CharacterCardPromptBuilder": CharacterCardPromptBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CharacterCardPromptBuilder": "角色卡 提示词生成器",
}
