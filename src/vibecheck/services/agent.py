"""pydantic-ai vibe analysis agent — class-based with free-model cascade + retry."""
from __future__ import annotations

import asyncio

from loguru import logger
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

from vibecheck.core.config import Settings
from vibecheck.schemas.profile import AnalysisMode, ScrapedProfile, VibeReport


VIBE_PROMPT = """Ты аналитик социальных профилей. По публичной активности из Reddit,
GitHub и Instagram сгенерируй структурированный vibe-отчёт.

ЦЕЛИ:
- Топ интересы (5-10 тем, от сильного сигнала к слабому)
- Черты характера с КОНКРЕТНЫМИ доказательствами из постов
- Red flags (токсичность, проблемные сабреддиты, агрессия)
- Green flags (дружелюбие, вдумчивость, навыки, полезность)
- vibe_score 0-100 — насколько приятно взаимодействовать:
  0-30 = тревожные паттерны доминируют
  31-65 = обычный человек, есть закидоны
  66-100 = вдумчивый, добрый, интересный

ПРАВИЛА:
- Отвечай ЧЕСТНО. Не сглаживай red flags.
- Цитируй конкретные доказательства (названия сабов, репо, цитаты).
- Не выводи гендер/расу/защищённые признаки из постов.
- ВЕСЬ ТЕКСТ В ОТВЕТЕ — СТРОГО НА РУССКОМ ЯЗЫКЕ, независимо от языка постов.
- НЕ используй markdown (`**`, `__`, `##`, `*`, `-`, backticks) — только plain text.
- summary 2-3 абзаца, прямой язык, без канцелярита.

AVATAR:
Produce an `avatar` object for a cartoon character representing this person:
- gender: "boy" | "girl" | "neutral" — best guess; "neutral" if ambiguous
- mood: joyful | chill | curious | focused | shy | sad | angry | suspicious
  (score 80+ → joyful/chill; 60-79 → chill/curious/focused; 40-59 → curious/focused/shy;
  20-39 → sad/shy; 0-19 → angry/suspicious/sad)
- vibe_color: hex ("#ffa94d" warm, "#ff6b9d" coral, "#7c4dff" violet, "#10b981" mint,
  "#fbbf24" sunny, "#6b7280" moody, "#ef4444" danger)
- accessories: 1-3 from glasses|shades|headphones|cap|beanie|crown|flowers|laptop|
  gamepad|camera|paintbrush|mic|book|mask|hoodie|earring|piercing|scarf
  (coder → laptop+glasses, gamer → gamepad+headphones, artist → paintbrush,
   musician → headphones+mic, bookworm → book+glasses, suspicious → mask)
- emoji: one emoji (🎮🎨💻📚🎧👑🌸🔥😎🤓🧸)
"""


SELF_PROMPT = """Ты аудитор цифрового следа. Пользователь анализирует СВОЙ профиль,
чтобы увидеть каким его видят чужие (HR, свидания, клиенты) из публичной активности.

ЦЕЛИ:
- headline: одно предложение «первое впечатление за 30 секунд»
- top_interests: 5-10 тем, которые профиль транслирует наружу
- personality_traits: какие черты считываются (с доказательствами),
  включая НЕПРЕДНАМЕРЕННЫЕ
- red_flags: что вредит найму/свиданиям/профессионалу — кринж-посты, спорные мнения,
  агрессивный тон, несогласованный бренд, утечка NSFW, заброшенные проекты, опечатки
- green_flags: что помогает — сильное портфолио, вдумчивые тексты, консистентный бренд
- vibe_score 0-100 — привлекательность для HR/свидания/клиента
  0-30 = нужна генеральная уборка
  31-65 = норм, но забывается, можно отполировать
  66-100 = сильный, осмысленный, убедительный
- summary: 2-3 абзаца с КОНКРЕТНЫМИ, ДЕЙСТВЕННЫМИ советами по уборке
  («Запинь топ-3 репо», «Удали злой пост 2017», «Добавь био», «Скрой звёзды у X»)

ПРАВИЛА:
- Формулируй как конструктивный аудит — ты помогаешь, не судишь.
- Конкретные советы важнее размытой обратной связи.
- ВЕСЬ ТЕКСТ В ОТВЕТЕ — СТРОГО НА РУССКОМ ЯЗЫКЕ.
- НЕ используй markdown (`**`, `__`, `##`, `*`, `-`, backticks) — только plain text.
- Не выводи защищённые признаки.

AVATAR:
Produce an `avatar` object:
- gender: "boy" | "girl" | "neutral"
- mood: map score 80+→joyful/chill, 60-79→focused/curious, 40-59→shy/curious, <40→sad/shy
- vibe_color: hex
- accessories: 1-3 matching dominant identity (coder→laptop+glasses, artist→paintbrush)
- emoji: one emoji
"""


CATFISH_PROMPT = """Ты детектив подлинности профилей. Пользователь проверяет кого-то
(возможное свидание, онлайн-знакомство, бизнес-контакт) — РЕАЛЬНЫЙ человек или catfish,
бот, скам, фейк.

ЦЕЛИ:
- headline: вердикт — «Скорее реален / Смешанные сигналы / Серьёзные красные флаги»
- top_interests: темы по всей активности (настоящая широта vs. бот-узость)
- personality_traits: согласованность персоны между платформами
- red_flags: индикаторы catfish/скама/бота:
  * новые аккаунты без истории, сток-эстетика, общее био, нет локации
  * паттерны постинга не стыкуются с заявленным timezone/образом жизни
  * love-bombing / «слишком хорошо чтобы быть правдой», крипто/инвест-реклама
  * несовпадение username между платформами, аномалии в соотношении подписчиков
  * всплески активности потом тишина (куплен аккаунт)
- green_flags: сигналы подлинности:
  * многолетняя история с органическим ростом, теги друзей, реальные имена
  * живые фото, реальные локации, «мессу» настоящей жизни
  * консистентный голос, специфичные знания которые бывают только у практика
- vibe_score 0-100 — балл подлинности:
  0-30 = сильные сигналы catfish/бота/скама
  31-65 = смешано, нужна доп. верификация
  66-100 = реальный человек с реальной историей
- summary: 2-3 абзаца. Прямо озвучь вердикт. Список конкретных шагов проверки
  (reverse image search, видеозвонок, спросить деталь которую знает только реальный).

ПРАВИЛА:
- Прямо. Если неуверен — флагуй.
- Цитируй конкретику (даты, подписчики, состав сабов, возраст репо).
- ВЕСЬ ТЕКСТ В ОТВЕТЕ — СТРОГО НА РУССКОМ ЯЗЫКЕ.
- НЕ используй markdown (`**`, `__`, `##`, `*`, `-`, backticks) — только plain text.
- Не выводи защищённые признаки.

AVATAR:
- gender: "boy" | "girl" | "neutral"
- mood: low authenticity → suspicious/angry; high → chill/curious
- vibe_color: low auth → "#ef4444" or "#6b7280"; high → "#10b981"
- accessories: suspicious profiles → mask; otherwise match interests
- emoji: 🚩 major red flags, ❓ mixed, ✅ authentic, or character emoji
"""


PROMPTS: dict[AnalysisMode, str] = {
    "vibe": VIBE_PROMPT,
    "self": SELF_PROMPT,
    "catfish": CATFISH_PROMPT,
}


class VibeAgent:
    """pydantic-ai Agent wrapper with free-model cascade + per-model retries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key or "dummy",
        )

    def _model(self, name: str) -> OpenAIChatModel:
        return OpenAIChatModel(name, provider=self.provider)

    def _agent(self, mode: AnalysisMode) -> Agent:
        return Agent(
            model=self._model(self.settings.agent_model),
            system_prompt=PROMPTS[mode],
            output_type=PromptedOutput(VibeReport),
            retries=2,
        )

    @staticmethod
    def _format_profile(profile: ScrapedProfile) -> str:
        lines: list[str] = []
        if profile.reddit_username:
            lines.append(f"Reddit: u/{profile.reddit_username}")
        if profile.github_username:
            lines.append(f"GitHub: @{profile.github_username}")
        if profile.instagram_username:
            lines.append(f"Instagram: @{profile.instagram_username}")
        lines.append(f"\nTotal items: {len(profile.posts)}\n")

        by_platform: dict[str, list] = {}
        for p in profile.posts:
            by_platform.setdefault(p.platform, []).append(p)

        for platform, items in by_platform.items():
            lines.append(f"\n=== {platform.upper()} ({len(items)} items) ===")
            for p in items[:40]:
                lines.append(f"[{p.kind}] {p.context}: {p.text[:300]}")
        return "\n".join(lines)

    async def analyze(self, profile: ScrapedProfile, mode: AnalysisMode = "vibe") -> VibeReport:
        prompt = self._format_profile(profile)
        agent = self._agent(mode)
        logger.info("Analyzing ({}): {} items, {} platforms",
                    mode, len(profile.posts),
                    len({p.platform for p in profile.posts}))

        last_exc: Exception | None = None
        for model_name in self.settings.fallback_models:
            for attempt in range(1, self.settings.retries_per_model + 1):
                try:
                    result = await agent.run(prompt, model=self._model(model_name))
                    logger.info("Analysis ({}) OK via {} (try {})", mode, model_name, attempt)
                    return result.output
                except Exception as exc:
                    logger.warning("Model {} try {}/{} failed: {}: {}",
                                   model_name, attempt, self.settings.retries_per_model,
                                   type(exc).__name__, str(exc)[:200])
                    last_exc = exc
                    if attempt < self.settings.retries_per_model:
                        await asyncio.sleep(1.5 * attempt)
        raise RuntimeError(f"All models exhausted: {last_exc}")
