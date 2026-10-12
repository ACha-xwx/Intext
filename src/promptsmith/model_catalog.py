"""Text-capable model suggestions, including the user's requested catalog.

These are suggestions, not evidence that the user's API account has access.
Service URLs and credentials remain managed by the existing settings flow.
"""
from dataclasses import dataclass, replace


EFFORTS = ("low", "medium", "high", "max")
EFFORT_LABELS = dict(zip(EFFORTS, ("Low", "Medium", "High", "Max")))


@dataclass(frozen=True)
class ModelPreset:
    id: str
    name: str
    provider: str
    description: str
    default_effort: str = "high"
    image: bool = True
    effort_map: tuple[str, ...] = EFFORTS
    adaptive: bool = False
    reasoning: bool = True
    service_provider: str = ""

    def map_effort(self, effort: str) -> str:
        return self.effort_map[EFFORTS.index(effort)] if effort in EFFORTS else effort


MODELS = (
    ModelPreset("gpt-6.1-sol", "GPT-6.1 Sol", "OpenAI", "兼顾响应速度、成本与复杂任务能力"),
    ModelPreset("gpt-6-astra", "GPT-6 Astra", "OpenAI", "适合复杂分析、规划与高难度推理", "high"),
    ModelPreset("gpt-6-sol", "GPT-6 Sol", "OpenAI", "适合代码、方案整理与日常任务"),
    ModelPreset("gpt-6-luna", "GPT-6 Luna", "OpenAI", "适合轻量整理与快速草稿"),
    ModelPreset("gpt-5.6-sol", "GPT-5.6 Sol", "OpenAI", "适合复杂任务与深入分析"),
    ModelPreset("gpt-5.6-terra", "GPT-5.6 Terra", "OpenAI", "兼顾响应速度与通用分析"),
    ModelPreset("gpt-5.6-luna", "GPT-5.6 Luna", "OpenAI", "适合轻量任务和快速回复"),
    ModelPreset("gpt-5.5", "GPT-5.5", "OpenAI", "适合已有工作流与常规代码任务"),
    ModelPreset("claude-opus-5-5", "Claude Opus 5.5", "Anthropic", "适合深入分析、代码与长篇任务", adaptive=True),
    ModelPreset("claude-fable-5-1", "Claude Fable 5.1", "Anthropic", "适合复杂推理与长程任务规划", "high", adaptive=True),
    ModelPreset("claude-sonnet-5-5", "Claude Sonnet 5.5", "Anthropic", "兼顾代码、工具协作与日常任务", "high", adaptive=True),
    ModelPreset("claude-haiku-5-5", "Claude Haiku 5.5", "Anthropic", "适合快速整理、轻量分析与草稿", adaptive=True),
    ModelPreset("grok-4.7", "Grok 4.7", "xAI", "适合代码、分析与多步推理", "high", effort_map=("low", "medium", "high", "xhigh")),
    ModelPreset("grok-4.6", "Grok 4.6", "xAI", "适合复杂问题与深入思考", "high", effort_map=("low", "medium", "high", "xhigh")),
    ModelPreset("grok-4.5", "Grok 4.5", "xAI", "适合知识整理与通用推理", "high", effort_map=("low", "medium", "high", "high")),
    ModelPreset("gemini-3.8-flash", "Gemini 3.8 Flash", "Google", "适合快速分析、内容整理与多模态理解", effort_map=("low", "medium", "high", "high")),
    ModelPreset("gemini-3.1-pro-preview", "Gemini 3.1 Pro", "Google", "适合复杂分析与长上下文任务（预览）", "high", effort_map=("low", "medium", "high", "high")),
    ModelPreset("deepseek-flash", "Deepseek V4.1 Flash", "DeepSeek", "快速整理需求与方案，兼顾响应速度和推理能力", "high", image=False, effort_map=("low", "high", "high", "max")),
    ModelPreset("deepseek-v4-pro", "Deepseek V4 Pro", "DeepSeek", "适合复杂方案、深入分析与多步推理", "high", image=False, effort_map=("low", "high", "high", "max")),
)
PROVIDERS = ("OpenAI", "Anthropic", "xAI", "Google", "DeepSeek")
PROVIDER_LABELS = {"OpenAI": "OpenAI", "Anthropic": "Anthropic", "xAI": "xAI", "Google": "Google", "DeepSeek": "DeepSeek", "custom": "当前服务"}
PROVIDER_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "protocol": "openai_chat_completions", "model": "deepseek-flash"},
    "OpenAI": {"base_url": "https://api.openai.com/v1", "protocol": "openai_responses", "model": "gpt-6.1-sol"},
    "Anthropic": {"base_url": "https://api.anthropic.com/v1", "protocol": "anthropic_messages", "model": "claude-opus-5-5"},
    "xAI": {"base_url": "https://api.x.ai/v1", "protocol": "openai_responses", "model": "grok-4.7"},
    "Google": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "protocol": "openai_chat_completions", "model": "gemini-3.8-flash"},
}


def validate_model_provider(connection) -> str:
    """Custom service names require an explicit request family."""
    service = connection.get("provider", "").strip()
    family = service if service in PROVIDERS else connection.get("model_provider", "").strip()
    if family not in PROVIDERS:
        raise ValueError("请为自定义服务选择模型供应商（OpenAI、Anthropic、xAI、Google 或 DeepSeek）。")
    return family


def find_model(model_id: str) -> ModelPreset | None:
    return next((model for model in MODELS if model.id == model_id.strip()), None)


def picker_models(current_id: str, discovered_ids=(), *, service_provider="", model_provider="") -> tuple[ModelPreset, ...]:
    """Decorate actual fetched IDs with local metadata, never add suggestions."""
    seen = set()
    models = []
    for value in discovered_ids:
        model_id = str(value).strip()
        if model_id and model_id not in seen:
            seen.add(model_id)
            family = service_provider if service_provider in PROVIDERS else model_provider
            known = find_model(model_id)
            if family not in PROVIDERS and known is None:
                continue  # Legacy custom service must select a family in settings first.
            preset = known or ModelPreset(model_id, model_id, family,
                "当前接口返回的模型；暂无本地介绍与能力资料", image=False, reasoning=False)
            models.append(replace(preset, provider=family if service_provider not in PROVIDERS and family in PROVIDERS else preset.provider,
                                  service_provider=service_provider))
    return tuple(models)


def search_models(models, provider: str, query: str):
    query = query.strip().casefold()
    return tuple(model for model in models if (
        query in " ".join((model.id, model.name, model.provider, model.description)).casefold()
        if query else model.provider == provider
    ))


def effort_note(model: ModelPreset | None, effort: str) -> str:
    if model is None or effort not in EFFORTS:
        return "按当前接口的默认思考强度处理。"
    actual = model.map_effort(effort)
    if actual != effort:
        if actual == "xhigh":
            return "此模型的 Max 对应最高支持的思考档位。"
        return f"此模型将 {EFFORT_LABELS[effort]} 按 {actual.title()} 处理。"
    return "思考强度越高，通常耗时与用量越多。"
