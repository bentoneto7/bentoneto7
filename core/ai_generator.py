import json

import anthropic

import config
from core import analyzer, database


SYSTEM_PROMPT = """Você é um estrategista de conteúdo para Instagram, especialista em engajamento e tendências digitais.

Com base nos dados de tendências fornecidos (hashtags populares, tipos de posts com melhor performance, captions de alto engajamento e padrões de postagem), gere ideias criativas de conteúdo.

Para cada ideia, forneça:
- title: Título curto e chamativo para o conteúdo
- description: 2-3 frases descrevendo o conteúdo, incluindo o gancho e CTA
- suggested_format: "image", "video", "carousel" ou "reel"
- suggested_hashtags: Lista de 5-10 hashtags relevantes
- reasoning: Por que essa ideia teria boa performance com base nos dados

IMPORTANTE: Retorne APENAS um JSON array válido, sem markdown ou texto adicional."""


def generate_content_ideas(
    accounts: list[str] = None,
    theme: str = "",
    num_ideas: int = 5,
) -> list[dict]:
    """Generate content ideas using Claude API based on trend data."""

    # Build context from analyzed data
    top_hashtags = analyzer.get_top_hashtags(days=30, limit=15)
    type_dist = analyzer.get_post_type_distribution(days=30)
    top_captions = analyzer.get_top_captions(days=30, limit=5)
    avg_engagement = analyzer.get_avg_engagement_rate(days=30)
    patterns = analyzer.get_posting_patterns(days=30)

    # Format best posting times
    best_times = ""
    if not patterns.empty:
        top_times = patterns.nlargest(5, "count")
        best_times = top_times.to_string(index=False)

    user_prompt = f"""Dados de tendências dos perfis monitorados no Instagram:

**Top Hashtags:**
{top_hashtags.to_string(index=False) if not top_hashtags.empty else "Sem dados ainda"}

**Tipos de Post com Melhor Performance:**
{type_dist.to_string(index=False) if not type_dist.empty else "Sem dados ainda"}

**Captions de Alto Engajamento (Top 5):**
{chr(10).join(f'- {c[:200]}' for c in top_captions) if top_captions else "Sem dados ainda"}

**Melhores Horários para Postar:**
{best_times if best_times else "Sem dados ainda"}

**Taxa Média de Engajamento:** {avg_engagement:.2%}

**Perfis Monitorados:** {', '.join(accounts) if accounts else 'Todos'}
"""

    if theme:
        user_prompt += f"\n**Foco temático solicitado:** {theme}\n"

    user_prompt += f"\nGere {num_ideas} ideias criativas de conteúdo baseadas nessas tendências."

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text

    # Try to parse JSON from the response
    try:
        ideas = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON array from the response
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start >= 0 and end > start:
            ideas = json.loads(response_text[start:end])
        else:
            ideas = [{
                "title": "Erro ao gerar ideias",
                "description": response_text[:500],
                "suggested_format": "image",
                "suggested_hashtags": [],
                "reasoning": "A resposta da IA não estava no formato esperado.",
            }]

    return ideas


def _parse_json_response(response_text: str) -> list:
    """Parse a JSON array from an AI response, handling markdown fences."""
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
        return []


def analyze_niche_and_suggest_creators(
    username: str,
    bio: str = "",
    captions: list[str] = None,
    hashtags: list[str] = None,
    num_suggestions: int = 5,
) -> dict:
    """Analyze a user's content niche and suggest top creators to follow.

    Uses AI to understand the user's niche from their bio, captions, and hashtags,
    then suggests the biggest creators in that same niche for inspiration.

    Returns: {niche, niche_description, creators: [{username, reason, followers_estimate}]}
    """
    if not config.ANTHROPIC_API_KEY:
        return {"niche": "", "niche_description": "", "creators": []}

    # Build context
    captions_text = ""
    if captions:
        captions_text = "\n".join(f"- {c[:200]}" for c in captions[:10])

    hashtags_text = ""
    if hashtags:
        hashtags_text = ", ".join(f"#{h}" for h in hashtags[:30])

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=(
            "Você é um especialista em Instagram e marketing digital no Brasil. "
            "Analise o perfil de um usuário e sugira os MAIORES creators/influenciadores "
            "do Instagram que produzem conteúdo similar ou no mesmo nicho. "
            "Foque em creators grandes e conhecidos (100K+ seguidores) que seriam boas "
            "referências de inspiração. Considere creators brasileiros E internacionais.\n\n"
            "IMPORTANTE: Retorne APENAS um JSON válido, sem markdown ou texto adicional."
        ),
        messages=[{
            "role": "user",
            "content": f"""Analise este perfil do Instagram e sugira {num_suggestions} grandes creators similares:

**Username:** @{username}
**Bio:** {bio or 'Não disponível'}

**Últimas captions (resumo do conteúdo):**
{captions_text or 'Não disponível'}

**Hashtags mais usadas:**
{hashtags_text or 'Não disponível'}

Retorne um JSON com este formato exato:
{{
  "niche": "nome curto do nicho (ex: fitness, empreendedorismo, humor)",
  "niche_description": "descrição de 1 frase do tipo de conteúdo",
  "creators": [
    {{
      "username": "username_real_do_instagram (sem @)",
      "name": "nome do creator",
      "reason": "por que é relevante como inspiração (1 frase)",
      "followers_estimate": "estimativa de seguidores (ex: 5M, 800K)"
    }}
  ]
}}"""
        }],
    )

    response_text = message.content[0].text

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON object
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(response_text[start:end])
            except json.JSONDecodeError:
                result = {"niche": "", "niche_description": "", "creators": []}
        else:
            result = {"niche": "", "niche_description": "", "creators": []}

    return result
