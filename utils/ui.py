"""Shared visual foundation for the Sentinel AI interface."""

import streamlit as st


def apply_sentinel_style() -> None:
    """Apply restrained brand effects on top of the native Streamlit theme."""
    st.html(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 82% -10%, rgba(91, 39, 140, .22), transparent 32rem),
                radial-gradient(circle at 12% 110%, rgba(67, 28, 104, .12), transparent 30rem),
                #07060B;
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(23, 16, 34, .92), rgba(13, 9, 20, .98));
        }
        [data-testid="stMetric"] {
            background: linear-gradient(145deg, rgba(33, 22, 48, .88), rgba(15, 10, 22, .92));
            box-shadow: inset 0 1px rgba(255, 255, 255, .025), 0 16px 40px rgba(0, 0, 0, .16);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(145deg, rgba(23, 16, 34, .68), rgba(10, 7, 15, .72));
            box-shadow: inset 0 1px rgba(255, 255, 255, .02), 0 18px 50px rgba(0, 0, 0, .14);
        }
        [data-testid="stButton"] button[kind="primary"] {
            box-shadow: 0 10px 28px rgba(139, 92, 246, .20);
        }
        h1, h2, h3 { letter-spacing: -0.025em; }
        </style>
        """
    )
