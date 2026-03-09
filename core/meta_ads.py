"""Meta Ads (Facebook Marketing API) integration module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import config


def _get_api():
    """Initialize and return a FacebookAdsApi instance."""
    from facebook_business.api import FacebookAdsApi
    FacebookAdsApi.init(
        app_id=config.META_APP_ID,
        app_secret=config.META_APP_SECRET,
        access_token=config.META_ACCESS_TOKEN,
    )
    return FacebookAdsApi.get_default_api()


def init_api() -> bool:
    """Initialize Meta API and verify credentials. Returns True if successful."""
    try:
        if not config.META_ACCESS_TOKEN or not config.META_AD_ACCOUNT_ID:
            return False
        _get_api()
        # Quick check: fetch account info
        get_account_info()
        return True
    except Exception:
        return False


def get_account_info() -> dict:
    """Return ad account name, status, currency, and timezone."""
    from facebook_business.adobjects.adaccount import AdAccount

    _get_api()
    account = AdAccount(config.META_AD_ACCOUNT_ID)
    fields = ["name", "account_status", "currency", "timezone_name", "balance"]
    data = account.api_get(fields=fields)

    status_map = {
        1: "Ativa",
        2: "Desativada",
        3: "Não confirmada",
        7: "Em revisão",
        9: "Fechada",
        100: "Pendente",
        101: "Pendente de encerramento",
        201: "Temporariamente indisponível",
    }

    return {
        "name": data.get("name", ""),
        "status": status_map.get(data.get("account_status"), str(data.get("account_status", ""))),
        "currency": data.get("currency", "BRL"),
        "timezone": data.get("timezone_name", ""),
        "balance": float(data.get("balance", 0)) / 100,
    }


def get_campaigns() -> list[dict]:
    """List all campaigns in the ad account."""
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign

    _get_api()
    account = AdAccount(config.META_AD_ACCOUNT_ID)
    fields = [
        Campaign.Field.id,
        Campaign.Field.name,
        Campaign.Field.status,
        Campaign.Field.objective,
        Campaign.Field.daily_budget,
        Campaign.Field.created_time,
    ]
    campaigns = account.get_campaigns(fields=fields)

    result = []
    for c in campaigns:
        result.append({
            "campaign_id": c.get(Campaign.Field.id, ""),
            "name": c.get(Campaign.Field.name, ""),
            "status": c.get(Campaign.Field.status, ""),
            "objective": c.get(Campaign.Field.objective, ""),
            "daily_budget": float(c.get(Campaign.Field.daily_budget) or 0) / 100,
            "created_time": str(c.get(Campaign.Field.created_time, "")),
        })
    return result


def create_campaign(name: str, objective: str, daily_budget_brl: float) -> dict:
    """
    Create a campaign (starts as PAUSED).
    objective: OUTCOME_ENGAGEMENT | OUTCOME_TRAFFIC | OUTCOME_LEADS | OUTCOME_AWARENESS
    Returns: {campaign_id, name, status}
    """
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign

    _get_api()
    account = AdAccount(config.META_AD_ACCOUNT_ID)

    daily_budget_cents = int(daily_budget_brl * 100)

    params = {
        Campaign.Field.name: name,
        Campaign.Field.objective: objective,
        Campaign.Field.status: Campaign.Status.paused,
        Campaign.Field.daily_budget: daily_budget_cents,
        Campaign.Field.special_ad_categories: [],
    }

    campaign = account.create_campaign(fields=[], params=params)
    return {
        "campaign_id": campaign["id"],
        "name": name,
        "status": "PAUSED",
    }


def create_ad_set(campaign_id: str, name: str, targeting: dict,
                  daily_budget_brl: float, optimization_goal: str = "REACH",
                  billing_event: str = "IMPRESSIONS") -> dict:
    """
    Create an ad set under a campaign.
    targeting = {'geo_locations': {'countries': ['BR']}, 'age_min': 18, 'age_max': 65}
    Returns: {adset_id, name}
    """
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet

    _get_api()
    account = AdAccount(config.META_AD_ACCOUNT_ID)

    daily_budget_cents = int(daily_budget_brl * 100)

    params = {
        AdSet.Field.name: name,
        AdSet.Field.campaign_id: campaign_id,
        AdSet.Field.daily_budget: daily_budget_cents,
        AdSet.Field.billing_event: billing_event,
        AdSet.Field.optimization_goal: optimization_goal,
        AdSet.Field.targeting: targeting,
        AdSet.Field.status: AdSet.Status.paused,
    }

    adset = account.create_ad_set(fields=[], params=params)
    return {
        "adset_id": adset["id"],
        "name": name,
    }


def get_campaign_insights(campaign_id: str, date_preset: str = "last_7_d") -> dict:
    """
    Fetch metrics for a campaign.
    date_preset: 'today' | 'last_7_d' | 'last_30_d'
    Returns: {impressions, clicks, reach, spend, ctr, cpc}
    """
    from facebook_business.adobjects.campaign import Campaign

    _get_api()
    campaign = Campaign(campaign_id)
    fields = ["impressions", "clicks", "reach", "spend", "ctr", "cpc"]
    params = {"date_preset": date_preset}

    insights = campaign.get_insights(fields=fields, params=params)

    if not insights:
        return {"impressions": 0, "clicks": 0, "reach": 0, "spend": 0.0, "ctr": 0.0, "cpc": 0.0}

    data = insights[0]
    return {
        "impressions": int(data.get("impressions", 0)),
        "clicks": int(data.get("clicks", 0)),
        "reach": int(data.get("reach", 0)),
        "spend": float(data.get("spend", 0)),
        "ctr": float(data.get("ctr", 0)),
        "cpc": float(data.get("cpc", 0)),
    }


def update_campaign_status(campaign_id: str, status: str) -> bool:
    """Set campaign status to ACTIVE or PAUSED. Returns True on success."""
    from facebook_business.adobjects.campaign import Campaign

    _get_api()
    campaign = Campaign(campaign_id)
    try:
        campaign.api_update(params={Campaign.Field.status: status})
        return True
    except Exception:
        return False


def create_campaign_from_idea(idea: dict, budget_brl: float, objective: str,
                               countries: list[str] = None,
                               age_min: int = 18, age_max: int = 65) -> dict:
    """
    Full flow: create campaign + ad set from a Claude-generated content idea.
    Returns: {campaign_id, adset_id, name}
    """
    if countries is None:
        countries = ["BR"]

    name = idea.get("title", "Campanha sem título")[:70]

    # Create campaign
    campaign_result = create_campaign(
        name=name,
        objective=objective,
        daily_budget_brl=budget_brl,
    )
    campaign_id = campaign_result["campaign_id"]

    # Build targeting
    targeting = {
        "geo_locations": {"countries": countries},
        "age_min": age_min,
        "age_max": age_max,
    }

    # Map objective to optimization goal
    objective_to_goal = {
        "OUTCOME_ENGAGEMENT": "POST_ENGAGEMENT",
        "OUTCOME_TRAFFIC": "LINK_CLICKS",
        "OUTCOME_LEADS": "LEAD_GENERATION",
        "OUTCOME_AWARENESS": "REACH",
    }
    optimization_goal = objective_to_goal.get(objective, "REACH")

    billing_map = {
        "POST_ENGAGEMENT": "POST_ENGAGEMENT",
        "LINK_CLICKS": "LINK_CLICKS",
        "LEAD_GENERATION": "IMPRESSIONS",
        "REACH": "IMPRESSIONS",
    }
    billing_event = billing_map.get(optimization_goal, "IMPRESSIONS")

    adset_result = create_ad_set(
        campaign_id=campaign_id,
        name=f"{name} — Conjunto",
        targeting=targeting,
        daily_budget_brl=budget_brl,
        optimization_goal=optimization_goal,
        billing_event=billing_event,
    )

    return {
        "campaign_id": campaign_id,
        "adset_id": adset_result["adset_id"],
        "name": name,
        "status": "PAUSED",
    }
