"""Ticker news and explainable sentiment from Massive."""

from datetime import datetime
from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.news_data import (
    NewsDataError,
    clear_news_cache,
    get_stock_news,
    summarize_sentiment,
)
from utils.market_analysis import build_market_analysis
from utils.watchlist import load_watchlist


def display_time(value):
    """Format an RFC3339 timestamp for compact display."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%b %d, %Y · %H:%M UTC")
    except (AttributeError, ValueError):
        return value or "Time unavailable"


st.set_page_config(
    page_title="Sentinel AI news and sentiment",
    page_icon=":material/newspaper:",
    layout="wide",
)

st.title(":material/newspaper: News & sentiment")
st.caption(
    "Review ticker-specific headlines and Massive's explainable sentiment alongside Sentinel's technical view."
)

try:
    massive_api_key = str(st.secrets.get("MASSIVE_API_KEY", "")).strip()
except Exception:
    st.error(
        'The secrets file is not valid TOML. Use: MASSIVE_API_KEY = "your-key"'
    )
    st.stop()

if not massive_api_key:
    st.error("Add MASSIVE_API_KEY to .streamlit/secrets.toml before loading news.")
    st.stop()

watchlist = load_watchlist()
default_symbol = watchlist[0] if watchlist else "AAPL"

with st.form("news_search_form", border=False):
    search_row = st.container(horizontal=True, vertical_alignment="bottom")
    symbol = search_row.text_input(
        "Stock symbol",
        value=st.session_state.get("news_symbol", default_symbol),
        max_chars=10,
    )
    article_limit = search_row.selectbox(
        "Headlines",
        options=[10, 20, 50],
        index=1,
    )
    search_clicked = search_row.form_submit_button(
        "Load news",
        icon=":material/search:",
        type="primary",
    )

if st.button(
    "Refresh news",
    icon=":material/refresh:",
    help="Clear the one-hour news cache.",
):
    clear_news_cache()
    st.session_state.pop("news_articles", None)
    st.toast("News cache cleared.")

if search_clicked:
    try:
        with st.spinner(f"Loading news for {symbol.strip().upper()}..."):
            articles = get_stock_news(
                symbol,
                limit=article_limit,
                _api_key=massive_api_key,
            )
        st.session_state["news_articles"] = articles
        st.session_state["news_symbol"] = symbol.strip().upper()
    except (NewsDataError, ValueError) as error:
        st.error(str(error))
        st.session_state.pop("news_articles", None)

articles = st.session_state.get("news_articles")
selected_symbol = st.session_state.get("news_symbol", default_symbol)
if articles is None:
    st.info("Enter a symbol and select **Load news** to begin.")
    st.stop()
if not articles:
    st.info(f"No recent Massive headlines were returned for {selected_symbol}.")
    st.stop()

summary = summarize_sentiment(articles)

with st.container(horizontal=True):
    st.metric("Overall sentiment", summary["label"], border=True)
    st.metric("Sentiment score", f'{summary["score"]:+.2f}', border=True)
    st.metric("Positive", summary["positive"], border=True)
    st.metric("Neutral", summary["neutral"], border=True)
    st.metric("Negative", summary["negative"], border=True)

try:
    technical = build_market_analysis(selected_symbol)
except Exception:
    technical = None

if technical:
    alignment = (
        "Aligned"
        if technical["Bias"].lower() == summary["label"].lower()
        else "Mixed"
    )
    with st.container(border=True):
        st.subheader("Sentiment + technical view")
        comparison = st.container(horizontal=True)
        comparison.metric("News sentiment", summary["label"], border=True)
        comparison.metric("Technical bias", technical["Bias"], border=True)
        comparison.metric("Signal alignment", alignment, border=True)
        if alignment == "Mixed":
            st.warning(
                "News sentiment and technical conditions disagree. Treat the setup with extra caution."
            )
        else:
            st.info("News sentiment and the current technical bias point in the same direction.")

for risk in summary["risks"]:
    st.warning(risk)

sentiment_filter = st.pills(
    "Show sentiment",
    options=["Positive", "Neutral", "Negative"],
    selection_mode="multi",
    default=["Positive", "Neutral", "Negative"],
)
selected_sentiments = {item.lower() for item in sentiment_filter}
visible_articles = [
    article
    for article in articles
    if article["sentiment"] in selected_sentiments
]

st.subheader(f"Recent {selected_symbol} headlines")
if not visible_articles:
    st.info("No headlines match the selected sentiment filters.")
else:
    for article in visible_articles:
        with st.container(border=True):
            header = st.container(horizontal=True, vertical_alignment="center")
            color = {
                "positive": "green",
                "negative": "red",
                "neutral": "gray",
            }[article["sentiment"]]
            header.badge(article["sentiment"].title(), color=color)
            header.caption(
                f'{article["publisher"]} · {display_time(article["published_utc"])}'
            )
            st.markdown(f'**{article["title"]}**')
            if article["description"]:
                st.write(article["description"])
            if article["sentiment_reasoning"]:
                st.caption(
                    f'Sentiment reasoning: {article["sentiment_reasoning"]}'
                )
            st.link_button(
                "Read original article",
                article["article_url"],
                icon=":material/open_in_new:",
            )

st.caption(
    "News and sentiment are supplied by Massive and may be delayed by the selected plan. "
    "Sentiment is contextual research, not a prediction or financial advice."
)
