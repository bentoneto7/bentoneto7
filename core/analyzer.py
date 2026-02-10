from collections import Counter

import pandas as pd

from core import database


def get_posts_dataframe(account_username: str = None, days: int = None) -> pd.DataFrame:
    posts = database.get_posts(account_username=account_username, days=days)
    if not posts:
        return pd.DataFrame()

    df = pd.DataFrame(posts)
    if "posted_at" in df.columns:
        df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce")
    return df


def get_top_hashtags(days: int = 30, limit: int = 20,
                     account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame(columns=["hashtag", "count"])

    all_hashtags = []
    for tags in df["hashtags"]:
        if isinstance(tags, list):
            all_hashtags.extend(tags)

    counter = Counter(all_hashtags)
    top = counter.most_common(limit)

    return pd.DataFrame(top, columns=["hashtag", "count"])


def get_engagement_summary(days: int = 30,
                           account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame()

    summary = df.groupby("account_username").agg(
        total_posts=("id", "count"),
        avg_likes=("likes", "mean"),
        avg_comments=("comments", "mean"),
        avg_engagement_rate=("engagement_rate", "mean"),
        max_likes=("likes", "max"),
        max_comments=("comments", "max"),
    ).round(2).reset_index()

    return summary


def get_post_type_distribution(days: int = 30,
                               account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame(columns=["post_type", "count"])

    dist = df["post_type"].value_counts().reset_index()
    dist.columns = ["post_type", "count"]
    return dist


def get_posting_patterns(days: int = 30,
                         account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame()

    df = df.dropna(subset=["posted_at"])
    df["hour"] = df["posted_at"].dt.hour
    df["day_of_week"] = df["posted_at"].dt.day_name()

    pattern = df.groupby(["day_of_week", "hour"]).size().reset_index(name="count")
    return pattern


def get_top_posts(days: int = 30, limit: int = 10,
                  account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame()

    top = df.nlargest(limit, "engagement_rate")
    return top[["shortcode", "account_username", "caption", "post_type",
                "likes", "comments", "engagement_rate", "posted_at", "url"]]


def get_top_captions(days: int = 30, limit: int = 5) -> list[str]:
    df = get_posts_dataframe(days=days)
    if df.empty:
        return []

    top = df.nlargest(limit, "engagement_rate")
    return top["caption"].tolist()


def get_caption_keywords(days: int = 30, limit: int = 30,
                         account_username: str = None) -> pd.DataFrame:
    df = get_posts_dataframe(account_username=account_username, days=days)
    if df.empty:
        return pd.DataFrame(columns=["keyword", "count"])

    stop_words = {
        "a", "o", "e", "de", "do", "da", "em", "que", "para", "com", "um",
        "uma", "os", "as", "no", "na", "por", "se", "não", "mais", "muito",
        "como", "mas", "ao", "ele", "ela", "seu", "sua", "ou", "quando",
        "the", "is", "in", "it", "of", "and", "to", "this", "that", "you",
        "for", "on", "are", "with", "was", "be", "have", "has", "at", "an",
        "i", "my", "your", "we", "they", "so", "if", "me", "up", "can",
        "", "es", "en", "la", "el", "los", "las", "un", "y", "del",
    }

    all_words = []
    for caption in df["caption"].dropna():
        words = caption.lower().split()
        words = [w.strip(".,!?#@\"'()[]{}") for w in words]
        words = [w for w in words if len(w) > 2 and w not in stop_words and not w.startswith("#")]
        all_words.extend(words)

    counter = Counter(all_words)
    top = counter.most_common(limit)
    return pd.DataFrame(top, columns=["keyword", "count"])


def get_avg_engagement_rate(days: int = 30) -> float:
    df = get_posts_dataframe(days=days)
    if df.empty:
        return 0.0
    return round(df["engagement_rate"].mean(), 4)
