import json

import anthropic

import config
from core import analyzer


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
