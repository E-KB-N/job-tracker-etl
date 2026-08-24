from __future__ import annotations

import os
import re

import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="My Job Hunt Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================

SHEET_ID = "1XcdyusjyMP_5p6QBXwQXNI-QJ-_bn6qsLZC5dkzwuX8"

TOKEN_PATH = "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events",
]


# ============================================================
# DATA CONFIGURATION
# ============================================================

REQUIRED_COLUMNS = [
    "Company_Name",
    "Job_Title",
    "Application_Date",
    "Current_Status",
    "Pipeline_Stage",
    "JD_Summary",
    "Job_Posting_URL",
    "Point_of_Contact",
    "Action_Deadline",
    "Constructive_Feedback",
    "Location_Type",
    "Platform_Source",
    "Salary_Range_Posted",
    "Interview_Date",
    "Last_Updated",
]

DATE_COLUMNS = [
    "Application_Date",
    "Action_Deadline",
    "Interview_Date",
    "Last_Updated",
]

CLOSED_STATUSES = {
    "Rejected",
    "Withdrawn",
    "Closed",
    "Offer",
    "Accepted",
}

PIPELINE_ORDER = [
    "Applied",
    "Resume Screen",
    "Recruiter Screen",
    "Assessment",
    "Hiring Manager Interview",
    "Final Interview",
    "Offer",
    "Accepted",
]

PIPELINE_RANK = {
    stage: index
    for index, stage in enumerate(PIPELINE_ORDER)
}

AGE_BANDS = [
    "0–7 days",
    "8–14 days",
    "15–30 days",
    "31–60 days",
    "60+ days",
]

JOB_FAMILY_RULES = {
    "Business Intelligence": [
        "business intelligence",
        "power bi",
        "tableau",
        "bi analyst",
        "reporting analyst",
        "visualization",
    ],
    "Data Analytics": [
        "data analyst",
        "data analytics",
        "insight analyst",
        "insights analyst",
        "quantitative analyst",
        "analytics analyst",
        "data scientist",
        "data science",
    ],
    "Business Analysis": [
        "business analyst",
        "business analysis",
        "business systems",
        "product analyst",
        "strategy analyst",
    ],
    "AI / LLM": [
        "llm",
        "artificial intelligence",
        "ai trainer",
        "ai evaluator",
        "model evaluator",
        "machine learning",
        "prompt engineer",
        "annotation",
    ],
    "Operations": [
        "operations",
        "supply chain",
        "procurement",
        "logistics",
        "performance analyst",
        "project coordinator",
    ],
    "Sales / Commercial": [
        "sales",
        "commercial",
        "account executive",
        "business development",
        "customer success",
        "account manager",
    ],
}


# ============================================================
# THEME CONFIGURATION
# ============================================================

THEMES = {
    "Light": {
        "primary": "#6258F4",
        "primary_light": "#A39DFC",
        "success": "#12B981",
        "warning": "#F4A723",
        "danger": "#EF5A67",
        "text": "#20263B",
        "muted": "#718096",
        "border": "#DCE3EE",
        "surface": "#FFFFFF",
        "surface_alt": "#F2F4FA",
        "background": "#E9EDF5",
        "sidebar": "#F5F6FB",
        "header": "#F5F6FB",
        "grid": "#E6EAF2",
        "input": "#FFFFFF",
        "tab_hover": "#EEECFF",
        "shadow": "rgba(15, 23, 42, 0.05)",
    },
    "Dark": {
        "primary": "#938DFF",
        "primary_light": "#726CF0",
        "success": "#34D399",
        "warning": "#FBBF24",
        "danger": "#FB7185",
        "text": "#EDF1FA",
        "muted": "#A4AFC2",
        "border": "#303A50",
        "surface": "#1A2233",
        "surface_alt": "#202A3D",
        "background": "#111827",
        "sidebar": "#161E2E",
        "header": "#161E2E",
        "grid": "#293449",
        "input": "#202A3D",
        "tab_hover": "#28334A",
        "shadow": "rgba(0, 0, 0, 0.18)",
    },
}

if "dashboard_theme" not in st.session_state:
    st.session_state["dashboard_theme"] = "Light"

selected_theme = st.sidebar.radio(
    "Appearance",
    options=["Light", "Dark"],
    horizontal=True,
    key="dashboard_theme",
)

COLORS = THEMES[selected_theme]

# NOTE on theming limits:
# st.dataframe / st.data_editor render through Streamlit's built-in
# "glide-data-grid" component, which draws its contents on an HTML
# <canvas> element. Canvas pixels cannot be restyled with CSS, so the
# THEMES/dashboard_styles block below (which works fine for metrics,
# buttons, tabs, sidebar, etc.) has NO effect on table/grid coloring.
# Those widgets always follow Streamlit's actual configured theme
# (set via .streamlit/config.toml or the user's browser preference),
# independent of this in-app Light/Dark toggle. If you want the grid
# to match, the real fix is a .streamlit/config.toml [theme] block —
# not anything achievable from inside this script with CSS.

STATUS_COLORS = {
    "Applied": COLORS["primary"],
    "Screening": "#60A5FA",
    "Interviewing": COLORS["success"],
    "Assessment": "#A78BFA",
    "On Hold": COLORS["warning"],
    "Rejected": COLORS["danger"],
    "Withdrawn": "#94A3B8",
    "Closed": "#64748B",
    "Offer": "#10B981",
    "Accepted": "#059669",
    "Not specified": (
        "#64748B"
        if selected_theme == "Dark"
        else "#CBD5E1"
    ),
}


# ============================================================
# VISUAL STYLING
# ============================================================

theme_variables = f"""
<style>
    :root {{
        --dashboard-primary: {COLORS["primary"]};
        --dashboard-primary-light: {COLORS["primary_light"]};
        --dashboard-success: {COLORS["success"]};
        --dashboard-warning: {COLORS["warning"]};
        --dashboard-danger: {COLORS["danger"]};
        --dashboard-text: {COLORS["text"]};
        --dashboard-muted: {COLORS["muted"]};
        --dashboard-border: {COLORS["border"]};
        --dashboard-surface: {COLORS["surface"]};
        --dashboard-surface-alt: {COLORS["surface_alt"]};
        --dashboard-background: {COLORS["background"]};
        --dashboard-sidebar: {COLORS["sidebar"]};
        --dashboard-header: {COLORS["header"]};
        --dashboard-grid: {COLORS["grid"]};
        --dashboard-input: {COLORS["input"]};
        --dashboard-tab-hover: {COLORS["tab_hover"]};
        --dashboard-shadow: {COLORS["shadow"]};
    }}
</style>
"""

dashboard_styles = """
<style>

    .stApp {
        background-color: var(--dashboard-background);
        color: var(--dashboard-text);
    }

    header[data-testid="stHeader"] {
        background-color: var(--dashboard-header);
        border-bottom: 1px solid var(--dashboard-border);
    }

    .block-container {
        max-width: 1500px;

        /*
        Extra top padding prevents the eyebrow text
        from disappearing beneath Streamlit's header.
        */
        padding-top: 5.5rem;
        padding-bottom: 3rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }

    h1,
    h2,
    h3,
    h4 {
        color: var(--dashboard-text) !important;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Inter,
            Roboto,
            sans-serif;

        letter-spacing: -0.035em;
    }

    h1 {
        font-size: 2.4rem !important;
        font-weight: 760 !important;
        line-height: 1.12 !important;
        margin-bottom: 0.4rem !important;
    }

    h2 {
        font-size: 1.35rem !important;
        font-weight: 690 !important;
    }

    h3 {
        font-size: 1.08rem !important;
        font-weight: 650 !important;
    }

    p,
    label,
    div[data-testid="stMarkdownContainer"] {
        color: var(--dashboard-text);
    }

    .eyebrow {
        color: var(--dashboard-primary) !important;

        font-size: 0.78rem;
        font-weight: 750;

        letter-spacing: 0.13em;
        text-transform: uppercase;

        margin-top: 0.25rem;
        margin-bottom: 0.7rem;
    }

    .page-description {
        color: var(--dashboard-muted) !important;

        font-size: 0.98rem;
        line-height: 1.55;

        margin-top: 0.15rem;
        margin-bottom: 1.65rem;
    }

    .section-description {
        color: var(--dashboard-muted) !important;

        font-size: 0.87rem;
        line-height: 1.5;

        margin-top: -0.3rem;
        margin-bottom: 0.85rem;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--dashboard-sidebar);

        border-right:
            1px solid var(--dashboard-border);
    }

    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {
        color: var(--dashboard-text);
    }

    section[data-testid="stSidebar"] hr {
        border-color: var(--dashboard-border);
    }

    div[data-testid="stMetric"] {
        background-color: var(--dashboard-surface);

        border:
            1px solid var(--dashboard-border);

        border-radius: 14px;

        padding: 18px 20px;
        min-height: 122px;

        box-shadow:
            0 4px 14px var(--dashboard-shadow);

        transition:
            border-color 180ms ease,
            transform 180ms ease,
            box-shadow 180ms ease;
    }

    div[data-testid="stMetric"]:hover {
        border-color: var(--dashboard-primary);
        transform: translateY(-2px);
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p {
        color: var(--dashboard-muted) !important;

        font-size: 0.86rem !important;
        font-weight: 550 !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--dashboard-text) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--dashboard-surface);

        border:
            1px solid var(--dashboard-border);

        border-radius: 14px;

        box-shadow:
            0 4px 14px var(--dashboard-shadow);
    }

    div[data-testid="stTabs"] button {
        color: var(--dashboard-muted) !important;

        font-size: 0.92rem;
        font-weight: 600;

        padding-top: 0.8rem;
        padding-bottom: 0.8rem;
    }

    div[data-testid="stTabs"] button:hover {
        color: var(--dashboard-primary) !important;

        background-color:
            var(--dashboard-tab-hover);
    }

    div[data-testid="stTabs"] button[
        aria-selected="true"
    ] {
        color: var(--dashboard-primary) !important;
    }

    div[data-testid="stTabs"] button[
        aria-selected="true"
    ] p {
        color: var(--dashboard-primary) !important;
    }

    div[data-testid="stDataFrame"] {
        border:
            1px solid var(--dashboard-border);

        border-radius: 10px;
        overflow: hidden;
    }

    details {
        background-color: var(--dashboard-surface);

        border:
            1px solid var(--dashboard-border);

        border-radius: 10px;
    }

    details summary,
    details summary p {
        color: var(--dashboard-text) !important;
    }

    div[data-baseweb="input"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"] {
        background-color: var(--dashboard-input);

        border-color:
            var(--dashboard-border);

        color: var(--dashboard-text);
    }

    div[data-baseweb="input"] input {
        color: var(--dashboard-text);
    }

    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        background-color:
            var(--dashboard-surface);

        color:
            var(--dashboard-text);

        border:
            1px solid var(--dashboard-border);

        border-radius: 9px;
        font-weight: 550;
    }

    div[data-testid="stButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        color:
            var(--dashboard-primary);

        border-color:
            var(--dashboard-primary);

        background-color:
            var(--dashboard-surface-alt);
    }

    div[data-testid="stCaptionContainer"] p {
        color:
            var(--dashboard-muted) !important;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    @media screen and (max-width: 768px) {
        .block-container {
            padding-top: 5.75rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        h1 {
            font-size: 1.9rem !important;
        }

        div[data-testid="stMetric"] {
            min-height: 105px;
        }
    }

</style>
"""

st.markdown(
    theme_variables + dashboard_styles,
    unsafe_allow_html=True,
)


# ============================================================
# DATA ACCESS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sheet_data() -> pd.DataFrame:
    creds = None
    
    # 1. Try loading from Streamlit Cloud Secrets first
    try:
        if "gcp_service_account" in st.secrets:
            token_info = dict(st.secrets["gcp_service_account"])
            if "token" in token_info and isinstance(token_info["token"], str):
                import json
                token_dict = json.loads(token_info["token"])
                creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
    except Exception:
        pass  # Not running on Streamlit Cloud or secrets aren't set up yet
    
    # 2. Fallback to local token.json if it exists on your machine
    if not creds and os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # 3. If still no credentials, guide the user gracefully instead of crashing
    if not creds:
        st.error("Authentication credentials not found. Please ensure 'token.json' is in your project folder for local use, or Streamlit Secrets are configured for cloud deployment.")
        st.stop()

    if credentials_expired := (creds.expired and creds.refresh_token):
        creds.refresh(Request())

    if not creds.valid:
        raise ValueError("Google credentials are invalid. Please reauthenticate.")

    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SHEET_ID).sheet1
    records = worksheet.get_all_records(default_blank="")
    return pd.DataFrame(records)


# ============================================================
# DATA CLEANING
# ============================================================

def clean_text_value(
    value: object,
) -> str | None:
    """Normalize blank-like values and text spacing."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    cleaned = str(value).strip()

    if cleaned.casefold() in {
        "",
        "none",
        "nan",
        "nat",
        "null",
        "n/a",
        "na",
        "0",
    }:
        return None

    return re.sub(
        r"\s+",
        " ",
        cleaned,
    )


def parse_mixed_dates(
    series: pd.Series,
) -> pd.Series:
    """Parse standard dates and Google Sheets serial dates."""

    cleaned = series.map(
        clean_text_value
    )

    parsed = pd.Series(
        pd.NaT,
        index=series.index,
        dtype="datetime64[ns]",
    )

    numeric_values = pd.to_numeric(
        cleaned,
        errors="coerce",
    )

    serial_mask = numeric_values.between(
        20_000,
        80_000,
        inclusive="both",
    )

    if serial_mask.any():
        parsed.loc[serial_mask] = pd.to_datetime(
            numeric_values.loc[serial_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )

    text_mask = (
        cleaned.notna()
        & ~serial_mask
    )

    if text_mask.any():
        text_values = cleaned.loc[
            text_mask
        ]

        try:
            text_dates = pd.to_datetime(
                text_values,
                format="mixed",
                dayfirst=True,
                errors="coerce",
            )
        except (TypeError, ValueError):
            text_dates = pd.to_datetime(
                text_values,
                dayfirst=True,
                errors="coerce",
            )

        parsed.loc[
            text_mask
        ] = text_dates

    return parsed


def normalize_status(
    value: object,
) -> str:
    """Standardize application status labels."""

    cleaned = clean_text_value(
        value
    )

    if not cleaned:
        return "Not specified"

    status_mapping = {
        "applied": "Applied",
        "application submitted": "Applied",
        "submitted": "Applied",
        "screening": "Screening",
        "resume screen": "Screening",
        "interviewing": "Interviewing",
        "interview": "Interviewing",
        "interview scheduled": "Interviewing",
        "assessment": "Assessment",
        "assessment pending": "Assessment",
        "on hold": "On Hold",
        "hold": "On Hold",
        "rejected": "Rejected",
        "unsuccessful": "Rejected",
        "declined": "Rejected",
        "withdrawn": "Withdrawn",
        "closed": "Closed",
        "offer": "Offer",
        "offered": "Offer",
        "offer received": "Offer",
        "accepted": "Accepted",
        "hired": "Accepted",
    }

    return status_mapping.get(
        cleaned.casefold(),
        cleaned.title(),
    )


def normalize_stage(
    value: object,
) -> str:
    """Standardize hiring pipeline stages."""

    cleaned = clean_text_value(
        value
    )

    if not cleaned:
        return "Applied"

    stage_mapping = {
        "applied": "Applied",
        "application submitted": "Applied",
        "resume screen": "Resume Screen",
        "resume screening": "Resume Screen",
        "cv screen": "Resume Screen",
        "recruiter screen": "Recruiter Screen",
        "recruiter screening": "Recruiter Screen",
        "phone screen": "Recruiter Screen",
        "video screen": "Recruiter Screen",
        "video screening": "Recruiter Screen",
        "assessment": "Assessment",
        "technical assessment": "Assessment",
        "case study": "Assessment",
        "assignment": "Assessment",
        "hiring manager": "Hiring Manager Interview",
        "hiring manager interview": "Hiring Manager Interview",
        "manager interview": "Hiring Manager Interview",
        "final interview": "Final Interview",
        "final round": "Final Interview",
        "offer": "Offer",
        "offer received": "Offer",
        "accepted": "Accepted",
    }

    return stage_mapping.get(
        cleaned.casefold(),
        cleaned,
    )


def normalize_location(
    value: object,
) -> str:
    """Normalize remote, hybrid, and on-site labels."""

    cleaned = clean_text_value(
        value
    )

    if not cleaned:
        return "Not specified"

    location_mapping = {
        "remote": "Remote",
        "fully remote": "Remote",
        "work from home": "Remote",
        "wfh": "Remote",
        "hybrid": "Hybrid",
        "on-site": "On-site",
        "onsite": "On-site",
        "on site": "On-site",
        "office": "On-site",
    }

    return location_mapping.get(
        cleaned.casefold(),
        cleaned,
    )


def classify_job_family(
    job_title: object,
) -> str:
    """Classify job titles into useful reporting categories."""

    title = clean_text_value(
        job_title
    )

    if not title:
        return "Not specified"

    lowered = title.casefold()

    for family, keywords in JOB_FAMILY_RULES.items():
        if any(
            keyword in lowered
            for keyword in keywords
        ):
            return family

    return "Other"


def parse_salary_range(
    value: object,
) -> tuple[
    str | None,
    float | None,
    float | None,
]:
    """Extract salary currency and an approximate salary range."""

    cleaned = clean_text_value(
        value
    )

    if not cleaned:
        return None, None, None

    upper_text = cleaned.upper()

    currency_patterns = {
        "USD": [
            r"\bUSD\b",
            r"\$",
        ],
        "GHS": [
            r"\bGHS\b",
            r"GH₵",
            r"₵",
        ],
        "GBP": [
            r"\bGBP\b",
            r"£",
        ],
        "EUR": [
            r"\bEUR\b",
            r"€",
        ],
    }

    currency = None

    for candidate, patterns in currency_patterns.items():
        if any(
            re.search(
                pattern,
                upper_text,
            )
            for pattern in patterns
        ):
            currency = candidate
            break

    matches = re.findall(
        r"(\d[\d,]*(?:\.\d+)?)\s*([kKmM]?)",
        cleaned,
    )

    amounts = []

    for number_text, multiplier in matches:
        try:
            amount = float(
                number_text.replace(
                    ",",
                    "",
                )
            )
        except ValueError:
            continue

        if multiplier.lower() == "k":
            amount *= 1_000

        elif multiplier.lower() == "m":
            amount *= 1_000_000

        amounts.append(
            amount
        )

    if not amounts:
        return currency, None, None

    if len(amounts) == 1:
        return (
            currency,
            amounts[0],
            amounts[0],
        )

    return (
        currency,
        min(amounts[:2]),
        max(amounts[:2]),
    )


def safe_percentage(
    numerator: int | float,
    denominator: int | float,
) -> float:
    """Calculate a percentage safely."""

    if not denominator:
        return 0.0

    return (
        float(numerator)
        / float(denominator)
        * 100
    )


def format_optional_number(
    value: float | int | None,
    suffix: str = "",
) -> str:
    """Format optional values without displaying NaN."""

    if value is None or pd.isna(value):
        return "—"

    return f"{value:,.0f}{suffix}"


def format_display_date(
    value: "pd.Timestamp | None",
) -> str:
    """Format a date for on-screen display.

    Returns an empty string for missing values instead of relying on
    st.column_config.DateColumn, which renders NaT/None as the
    literal text "None" in the data grid.
    """

    if value is None or pd.isna(value):
        return ""

    return value.strftime("%d %b %Y")


def normalize_dataframe(
    raw_df: pd.DataFrame,
) -> pd.DataFrame:
    """Validate, clean, and enrich source records."""

    df = raw_df.copy()

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Google Sheet is missing required columns: "
            + ", ".join(
                missing_columns
            )
        )

    for column in REQUIRED_COLUMNS:
        if column not in DATE_COLUMNS:
            df[column] = df[column].map(
                clean_text_value
            )

    for column in DATE_COLUMNS:
        df[column] = parse_mixed_dates(
            df[column]
        )

    df["Company_Name"] = df[
        "Company_Name"
    ].fillna(
        "Unknown company"
    )

    df["Job_Title"] = df[
        "Job_Title"
    ].fillna(
        "Not specified"
    )

    df["Current_Status"] = df[
        "Current_Status"
    ].map(
        normalize_status
    )

    df["Pipeline_Stage"] = df[
        "Pipeline_Stage"
    ].map(
        normalize_stage
    )

    df["Location_Type"] = df[
        "Location_Type"
    ].map(
        normalize_location
    )

    df["Platform_Source"] = df[
        "Platform_Source"
    ].fillna(
        "Not specified"
    )

    df["Job_Family"] = df[
        "Job_Title"
    ].map(
        classify_job_family
    )

    df["Is_Active"] = ~df[
        "Current_Status"
    ].isin(
        CLOSED_STATUSES
    )

    today = pd.Timestamp.now().normalize()

    df["Days_Open"] = (
        today
        - df["Application_Date"]
    ).dt.days

    df.loc[
        df["Days_Open"] < 0,
        "Days_Open",
    ] = np.nan

    df["Days_Since_Update"] = (
        today
        - df["Last_Updated"]
    ).dt.days

    df.loc[
        df["Days_Since_Update"] < 0,
        "Days_Since_Update",
    ] = np.nan

    df["Days_To_Interview"] = (
        df["Interview_Date"]
        - df["Application_Date"]
    ).dt.days

    df.loc[
        df["Days_To_Interview"] < 0,
        "Days_To_Interview",
    ] = np.nan

    df["Deadline_Overdue"] = (
        df["Is_Active"]
        & df["Action_Deadline"].notna()
        & (
            df["Action_Deadline"]
            < today
        )
    )

    df["Deadline_Upcoming"] = (
        df["Is_Active"]
        & df["Action_Deadline"].notna()
        & (
            df["Action_Deadline"]
            >= today
        )
        & (
            df["Action_Deadline"]
            <= today + pd.Timedelta(
                days=7
            )
        )
    )

    df["Interview_Upcoming"] = (
        df["Is_Active"]
        & df["Interview_Date"].notna()
        & (
            df["Interview_Date"]
            >= today
        )
        & (
            df["Interview_Date"]
            <= today + pd.Timedelta(
                days=7
            )
        )
    )

    df["Is_Stale"] = (
        df["Is_Active"]
        & (
            df["Days_Since_Update"]
            > 7
        )
    )

    df["Needs_Attention"] = (
        df["Deadline_Overdue"]
        | df["Deadline_Upcoming"]
        | df["Interview_Upcoming"]
        | df["Is_Stale"]
    )

    df["Age_Band"] = pd.cut(
        df["Days_Open"],
        bins=[
            -1,
            7,
            14,
            30,
            60,
            np.inf,
        ],
        labels=AGE_BANDS,
    )

    salary_details = df[
        "Salary_Range_Posted"
    ].apply(
        parse_salary_range
    )

    df[
        [
            "Salary_Currency",
            "Salary_Min",
            "Salary_Max",
        ]
    ] = pd.DataFrame(
        salary_details.tolist(),
        index=df.index,
    )

    df["Salary_Midpoint"] = (
        df["Salary_Min"]
        + df["Salary_Max"]
    ) / 2

    interview_related_stages = {
        "Recruiter Screen",
        "Hiring Manager Interview",
        "Final Interview",
        "Offer",
        "Accepted",
    }

    df["Reached_Interview"] = (
        df["Interview_Date"].notna()
        | df["Current_Status"].isin(
            {
                "Interviewing",
                "Offer",
                "Accepted",
            }
        )
        | df["Pipeline_Stage"].isin(
            interview_related_stages
        )
    )

    df["Received_Offer"] = (
        df["Current_Status"].isin(
            {
                "Offer",
                "Accepted",
            }
        )
        | df["Pipeline_Stage"].isin(
            {
                "Offer",
                "Accepted",
            }
        )
    )

    return df


# ============================================================
# CHART HELPERS
# ============================================================

def style_chart(
    figure: go.Figure,
    height: int = 330,
) -> go.Figure:
    """Apply consistent light-mode or dark-mode chart styling."""

    figure.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={
            "t": 35,
            "r": 20,
            "b": 35,
            "l": 15,
        },
        font={
            "family": (
                "Inter, -apple-system, "
                "BlinkMacSystemFont, "
                "Segoe UI, sans-serif"
            ),
            "size": 12,
            "color": COLORS["muted"],
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {
                "color": COLORS["text"],
            },
        },
        hoverlabel={
            "bgcolor": COLORS["surface"],
            "bordercolor": COLORS["border"],
            "font": {
                "size": 12,
                "color": COLORS["text"],
            },
        },
    )

    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        color=COLORS["muted"],
        tickfont={
            "color": COLORS["muted"],
        },
        title_font={
            "color": COLORS["muted"],
        },
    )

    figure.update_yaxes(
        gridcolor=COLORS["grid"],
        zeroline=False,
        color=COLORS["muted"],
        tickfont={
            "color": COLORS["muted"],
        },
        title_font={
            "color": COLORS["muted"],
        },
    )

    return figure


def render_chart(
    figure: go.Figure,
) -> None:
    """Render a responsive Plotly chart."""

    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


def render_empty_state(
    message: str,
) -> None:
    """Render a compact explanatory empty state."""

    st.info(
        message,
        icon="ℹ️",
    )


def section_header(
    title: str,
    description: str | None = None,
) -> None:
    """Render a dashboard section heading."""

    st.subheader(
        title
    )

    if description:
        st.markdown(
            (
                '<p class="section-description">'
                f"{description}"
                "</p>"
            ),
            unsafe_allow_html=True,
        )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    df: pd.DataFrame,
) -> dict[str, float | int]:
    """Calculate executive dashboard metrics."""

    total = len(
        df
    )

    active = int(
        df["Is_Active"].sum()
    )

    interviews = int(
        df["Reached_Interview"].sum()
    )

    offers = int(
        df["Received_Offer"].sum()
    )

    rejections = int(
        df["Current_Status"]
        .eq("Rejected")
        .sum()
    )

    attention = int(
        df["Needs_Attention"].sum()
    )

    stale = int(
        df["Is_Stale"].sum()
    )

    interview_days = df[
        "Days_To_Interview"
    ].dropna()

    median_interview_days = (
        float(
            interview_days.median()
        )
        if not interview_days.empty
        else np.nan
    )

    today = pd.Timestamp.now().normalize()

    month_start = today.replace(
        day=1
    )

    previous_month_end = (
        month_start
        - pd.Timedelta(
            days=1
        )
    )

    previous_month_start = (
        previous_month_end.replace(
            day=1
        )
    )

    applications_this_month = int(
        (
            df["Application_Date"]
            >= month_start
        ).sum()
    )

    applications_previous_month = int(
        (
            (
                df["Application_Date"]
                >= previous_month_start
            )
            & (
                df["Application_Date"]
                < month_start
            )
        ).sum()
    )

    return {
        "total": total,
        "active": active,
        "interviews": interviews,
        "offers": offers,
        "rejections": rejections,
        "needs_attention": attention,
        "stale": stale,
        "interview_rate": safe_percentage(
            interviews,
            total,
        ),
        "offer_rate": safe_percentage(
            offers,
            total,
        ),
        "rejection_rate": safe_percentage(
            rejections,
            total,
        ),
        "median_days_to_interview": (
            median_interview_days
        ),
        "applications_this_month": (
            applications_this_month
        ),
        "applications_previous_month": (
            applications_previous_month
        ),
    }


def build_group_performance(
    df: pd.DataFrame,
    group_column: str,
) -> pd.DataFrame:
    """Summarize outcomes by source, role, or location."""

    if df.empty:
        return pd.DataFrame()

    grouped = (
        df.groupby(
            group_column,
            dropna=False,
        )
        .agg(
            Applications=(
                "Company_Name",
                "size",
            ),
            Interviews=(
                "Reached_Interview",
                "sum",
            ),
            Offers=(
                "Received_Offer",
                "sum",
            ),
            Active=(
                "Is_Active",
                "sum",
            ),
            Rejections=(
                "Current_Status",
                lambda values: values.eq(
                    "Rejected"
                ).sum(),
            ),
            Median_Days_To_Interview=(
                "Days_To_Interview",
                "median",
            ),
        )
        .reset_index()
    )

    grouped["Interview_Rate"] = (
        grouped["Interviews"]
        / grouped["Applications"]
        * 100
    )

    grouped["Offer_Rate"] = (
        grouped["Offers"]
        / grouped["Applications"]
        * 100
    )

    grouped["Rejection_Rate"] = (
        grouped["Rejections"]
        / grouped["Applications"]
        * 100
    )

    return grouped.sort_values(
        [
            "Applications",
            "Interview_Rate",
        ],
        ascending=[
            False,
            False,
        ],
    )


def effective_pipeline_rank(
    row: pd.Series,
) -> int:
    """Estimate the furthest known hiring stage."""

    stage_rank = PIPELINE_RANK.get(
        row["Pipeline_Stage"],
        0,
    )

    if row["Current_Status"] == "Accepted":
        return PIPELINE_RANK[
            "Accepted"
        ]

    if row["Received_Offer"]:
        return max(
            stage_rank,
            PIPELINE_RANK[
                "Offer"
            ],
        )

    if row["Reached_Interview"]:
        return max(
            stage_rank,
            PIPELINE_RANK[
                "Recruiter Screen"
            ],
        )

    return stage_rank


def build_inferred_funnel(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Build an inferred cumulative hiring funnel."""

    if df.empty:
        return pd.DataFrame(
            columns=[
                "Stage",
                "Applications",
                "Conversion",
            ]
        )

    stage_ranks = df.apply(
        effective_pipeline_rank,
        axis=1,
    )

    rows = []

    previous_count = None

    for stage in PIPELINE_ORDER:
        current_rank = PIPELINE_RANK[
            stage
        ]

        count = int(
            (
                stage_ranks
                >= current_rank
            ).sum()
        )

        conversion = (
            100.0
            if previous_count is None
            else safe_percentage(
                count,
                previous_count,
            )
        )

        rows.append(
            {
                "Stage": stage,
                "Applications": count,
                "Conversion": conversion,
            }
        )

        previous_count = count

    return pd.DataFrame(
        rows
    )


def generate_insights(
    df: pd.DataFrame,
    minimum_source_sample: int = 3,
) -> list[str]:
    """Generate evidence-based observations."""

    if df.empty:
        return [
            "No applications match the current filters."
        ]

    insights = []

    metrics = calculate_metrics(
        df
    )

    source_performance = build_group_performance(
        df,
        "Platform_Source",
    )

    eligible_sources = source_performance[
        (
            source_performance["Applications"]
            >= minimum_source_sample
        )
        & (
            source_performance["Platform_Source"]
            != "Not specified"
        )
    ]

    if not eligible_sources.empty:
        best_source = (
            eligible_sources.sort_values(
                [
                    "Interview_Rate",
                    "Applications",
                ],
                ascending=False,
            )
            .iloc[0]
        )

        insights.append(
            f"Best-performing source: "
            f"{best_source['Platform_Source']} "
            f"with a "
            f"{best_source['Interview_Rate']:.0f}% "
            f"interview rate across "
            f"{int(best_source['Applications'])} "
            "applications."
        )

    else:
        insights.append(
            "Source conversion is still directional: "
            f"no platform has at least "
            f"{minimum_source_sample} applications."
        )

    if metrics["active"] > 0:
        stale_share = safe_percentage(
            metrics["stale"],
            metrics["active"],
        )

        insights.append(
            f"{metrics['stale']} of "
            f"{metrics['active']} active applications "
            f"({stale_share:.0f}%) have not been "
            "updated for more than seven days."
        )

    role_performance = build_group_performance(
        df,
        "Job_Family",
    )

    eligible_roles = role_performance[
        (
            role_performance["Applications"]
            >= 2
        )
        & (
            role_performance["Job_Family"]
            != "Not specified"
        )
    ]

    if not eligible_roles.empty:
        strongest_role = (
            eligible_roles.sort_values(
                [
                    "Interview_Rate",
                    "Applications",
                ],
                ascending=False,
            )
            .iloc[0]
        )

        insights.append(
            f"Strongest role family: "
            f"{strongest_role['Job_Family']} at "
            f"{strongest_role['Interview_Rate']:.0f}% "
            "interview conversion."
        )

    upcoming_deadlines = df[
        df["Deadline_Upcoming"]
    ].sort_values(
        "Action_Deadline"
    )

    if not upcoming_deadlines.empty:
        next_deadline = upcoming_deadlines.iloc[
            0
        ]

        deadline_text = format_display_date(
            next_deadline[
                "Action_Deadline"
            ]
        )

        insights.append(
            f"Nearest upcoming action: "
            f"{next_deadline['Company_Name']} "
            f"on {deadline_text}."
        )

    current_month = metrics[
        "applications_this_month"
    ]

    previous_month = metrics[
        "applications_previous_month"
    ]

    if previous_month > 0:
        monthly_change = safe_percentage(
            current_month - previous_month,
            previous_month,
        )

        direction = (
            "up"
            if monthly_change >= 0
            else "down"
        )

        insights.append(
            f"Application activity is {direction} "
            f"{abs(monthly_change):.0f}% compared "
            "with the previous month."
        )

    return insights[:5]


# ============================================================
# SIDEBAR FILTERS
# ============================================================

def render_sidebar(
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    """Render dashboard-wide filters."""

    st.sidebar.divider()

    st.sidebar.markdown(
        "### Dashboard Controls"
    )

    st.sidebar.caption(
        "Filter every dashboard section."
    )

    if st.sidebar.button(
        "Refresh Google Sheets",
        use_container_width=True,
    ):
        load_sheet_data.clear()
        st.rerun()

    if st.sidebar.button(
        "Reset Filters",
        use_container_width=True,
    ):
        filter_keys = [
            key
            for key in st.session_state
            if key.startswith(
                "filter_"
            )
        ]

        for key in filter_keys:
            del st.session_state[
                key
            ]

        st.rerun()

    filtered = source_df.copy()

    valid_dates = source_df[
        "Application_Date"
    ].dropna()

    if not valid_dates.empty:
        minimum_date = valid_dates.min().date()

        maximum_date = valid_dates.max().date()

        selected_dates = st.sidebar.date_input(
            "Application date range",
            value=(
                minimum_date,
                maximum_date,
            ),
            min_value=minimum_date,
            max_value=maximum_date,
            key="filter_date_range",
        )

        include_missing_dates = (
            st.sidebar.checkbox(
                "Include applications without a valid date",
                value=True,
                key="filter_include_missing_dates",
            )
        )

        if (
            isinstance(
                selected_dates,
                (tuple, list),
            )
            and len(
                selected_dates
            )
            == 2
        ):
            start_date, end_date = (
                selected_dates
            )

            matching_dates = (
                filtered["Application_Date"]
                .dt.date.between(
                    start_date,
                    end_date,
                )
                .fillna(
                    False
                )
            )

            if include_missing_dates:
                matching_dates = (
                    matching_dates
                    | filtered[
                        "Application_Date"
                    ].isna()
                )

            filtered = filtered[
                matching_dates
            ]

    selected_statuses = st.sidebar.multiselect(
        "Current status",
        options=sorted(
            source_df[
                "Current_Status"
            ].dropna().unique()
        ),
        key="filter_status",
    )

    if selected_statuses:
        filtered = filtered[
            filtered["Current_Status"].isin(
                selected_statuses
            )
        ]

    available_stages = set(
        source_df[
            "Pipeline_Stage"
        ].dropna()
    )

    ordered_stages = [
        stage
        for stage in PIPELINE_ORDER
        if stage in available_stages
    ]

    additional_stages = sorted(
        available_stages
        - set(
            ordered_stages
        )
    )

    selected_stages = st.sidebar.multiselect(
        "Pipeline stage",
        options=(
            ordered_stages
            + additional_stages
        ),
        key="filter_stage",
    )

    if selected_stages:
        filtered = filtered[
            filtered["Pipeline_Stage"].isin(
                selected_stages
            )
        ]

    selected_sources = st.sidebar.multiselect(
        "Platform source",
        options=sorted(
            source_df[
                "Platform_Source"
            ].dropna().unique()
        ),
        key="filter_source",
    )

    if selected_sources:
        filtered = filtered[
            filtered["Platform_Source"].isin(
                selected_sources
            )
        ]

    selected_locations = st.sidebar.multiselect(
        "Location type",
        options=sorted(
            source_df[
                "Location_Type"
            ].dropna().unique()
        ),
        key="filter_location",
    )

    if selected_locations:
        filtered = filtered[
            filtered["Location_Type"].isin(
                selected_locations
            )
        ]

    selected_job_families = (
        st.sidebar.multiselect(
            "Job family",
            options=sorted(
                source_df[
                    "Job_Family"
                ].dropna().unique()
            ),
            key="filter_job_family",
        )
    )

    if selected_job_families:
        filtered = filtered[
            filtered["Job_Family"].isin(
                selected_job_families
            )
        ]

    selected_companies = st.sidebar.multiselect(
        "Company",
        options=sorted(
            source_df[
                "Company_Name"
            ].dropna().unique()
        ),
        key="filter_company",
    )

    if selected_companies:
        filtered = filtered[
            filtered["Company_Name"].isin(
                selected_companies
            )
        ]

    application_view = st.sidebar.radio(
        "Application view",
        options=[
            "All applications",
            "Active only",
            "Closed only",
        ],
        key="filter_application_view",
    )

    if application_view == "Active only":
        filtered = filtered[
            filtered["Is_Active"]
        ]

    elif application_view == "Closed only":
        filtered = filtered[
            ~filtered["Is_Active"]
        ]

    title_keyword = st.sidebar.text_input(
        "Job title keyword",
        placeholder="Example: analyst",
        key="filter_title_keyword",
    )

    if title_keyword.strip():
        filtered = filtered[
            filtered["Job_Title"].str.contains(
                title_keyword.strip(),
                case=False,
                na=False,
                regex=False,
            )
        ]

    st.sidebar.divider()

    st.sidebar.caption(
        f"Showing {len(filtered):,} of "
        f"{len(source_df):,} applications."
    )

    return filtered


# ============================================================
# EXECUTIVE OVERVIEW
# ============================================================

def render_overview(
    df: pd.DataFrame,
) -> None:
    """Render executive KPIs and primary charts."""

    metrics = calculate_metrics(
        df
    )

    first_row = st.columns(
        4
    )

    first_row[0].metric(
        "Total Applications",
        f"{metrics['total']:,}",
    )

    first_row[1].metric(
        "Active Pipeline",
        f"{metrics['active']:,}",
    )

    monthly_delta = (
        metrics["applications_this_month"]
        - metrics["applications_previous_month"]
    )

    first_row[2].metric(
        "Applications This Month",
        f"{metrics['applications_this_month']:,}",
        delta=(
            f"{monthly_delta:+,} vs previous month"
            if metrics[
                "applications_previous_month"
            ]
            > 0
            else None
        ),
    )

    first_row[3].metric(
        "Needs Attention",
        f"{metrics['needs_attention']:,}",
    )

    st.write("")

    second_row = st.columns(
        4
    )

    second_row[0].metric(
        "Interview Rate",
        f"{metrics['interview_rate']:.1f}%",
    )

    second_row[1].metric(
        "Offer Rate",
        f"{metrics['offer_rate']:.1f}%",
    )

    second_row[2].metric(
        "Rejection Rate",
        f"{metrics['rejection_rate']:.1f}%",
    )

    second_row[3].metric(
        "Median Days to Interview",
        format_optional_number(
            metrics[
                "median_days_to_interview"
            ],
            " days",
        ),
    )

    st.write("")

    trend_column, funnel_column = st.columns(
        [
            1.15,
            1,
        ]
    )

    with trend_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Application Momentum",
                "Weekly applications and "
                "four-week rolling activity.",
            )

            valid_dates = df[
                "Application_Date"
            ].dropna()

            if valid_dates.empty:
                render_empty_state(
                    "Add valid application dates "
                    "to display application momentum."
                )

            else:
                weekly_counts = (
                    df.dropna(
                        subset=[
                            "Application_Date"
                        ]
                    )
                    .set_index(
                        "Application_Date"
                    )
                    .resample(
                        "W-MON"
                    )
                    .size()
                    .rename(
                        "Applications"
                    )
                    .reset_index()
                )

                weekly_counts[
                    "Four_Week_Average"
                ] = (
                    weekly_counts[
                        "Applications"
                    ]
                    .rolling(
                        window=4,
                        min_periods=1,
                    )
                    .mean()
                )

                figure = go.Figure()

                figure.add_bar(
                    x=weekly_counts[
                        "Application_Date"
                    ],
                    y=weekly_counts[
                        "Applications"
                    ],
                    name="Applications",
                    marker_color=COLORS[
                        "primary_light"
                    ],
                    opacity=0.85,
                    hovertemplate=(
                        "%{x|%d %b %Y}"
                        "<br>"
                        "Applications: %{y}"
                        "<extra></extra>"
                    ),
                )

                figure.add_scatter(
                    x=weekly_counts[
                        "Application_Date"
                    ],
                    y=weekly_counts[
                        "Four_Week_Average"
                    ],
                    name="4-week average",
                    mode="lines+markers",
                    line={
                        "color": COLORS[
                            "primary"
                        ],
                        "width": 3,
                    },
                    hovertemplate=(
                        "%{x|%d %b %Y}"
                        "<br>"
                        "4-week average: %{y:.1f}"
                        "<extra></extra>"
                    ),
                )

                figure.update_yaxes(
                    title="Applications",
                    dtick=1,
                )

                render_chart(
                    style_chart(
                        figure,
                        height=340,
                    )
                )

    with funnel_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Recruitment Funnel",
                "Estimated progression through "
                "the hiring pipeline.",
            )

            funnel = build_inferred_funnel(
                df
            )

            nonzero_funnel = funnel[
                (
                    funnel[
                        "Applications"
                    ]
                    > 0
                )
                | funnel[
                    "Stage"
                ].eq(
                    "Applied"
                )
            ]

            funnel_colors = [
                COLORS["primary"],
                "#726CF0",
                "#818CF8",
                "#A78BFA",
                "#C4B5FD",
                "#DDD6FE",
                COLORS["success"],
                "#059669",
            ]

            figure = go.Figure(
                go.Funnel(
                    y=nonzero_funnel[
                        "Stage"
                    ],
                    x=nonzero_funnel[
                        "Applications"
                    ],
                    textinfo=(
                        "value+percent initial"
                    ),
                    marker={
                        "color": funnel_colors[
                            :len(
                                nonzero_funnel
                            )
                        ],
                    },
                    connector={
                        "line": {
                            "color": COLORS[
                                "border"
                            ],
                        }
                    },
                )
            )

            render_chart(
                style_chart(
                    figure,
                    height=340,
                )
            )

    st.write("")

    status_column, insight_column = st.columns(
        [
            1,
            1.15,
        ]
    )

    with status_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Current Status",
                "Distribution of application "
                "statuses.",
            )

            status_counts = (
                df["Current_Status"]
                .value_counts()
                .rename_axis(
                    "Status"
                )
                .reset_index(
                    name="Applications"
                )
            )

            figure = px.pie(
                status_counts,
                names="Status",
                values="Applications",
                hole=0.68,
                color="Status",
                color_discrete_map=(
                    STATUS_COLORS
                ),
            )

            figure.update_traces(
                textposition="inside",
                textinfo="percent",
                hovertemplate=(
                    "%{label}"
                    "<br>"
                    "Applications: %{value}"
                    "<br>"
                    "Share: %{percent}"
                    "<extra></extra>"
                ),
            )

            figure.add_annotation(
                text=(
                    f"<b>{len(df)}</b>"
                    "<br>"
                    "applications"
                ),
                x=0.5,
                y=0.5,
                showarrow=False,
                font={
                    "size": 15,
                    "color": COLORS[
                        "text"
                    ],
                },
            )

            render_chart(
                style_chart(
                    figure,
                    height=310,
                )
            )

    with insight_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Key Insights",
                "Evidence-based observations "
                "from your current application data.",
            )

            for insight in generate_insights(
                df
            ):
                st.markdown(
                    f"- {insight}"
                )

            st.caption(
                "Small samples are directional "
                "rather than conclusive."
            )

    st.write("")

    with st.container(
        border=True,
    ):
        section_header(
            "Needs Attention",
            "Overdue actions, upcoming deadlines, "
            "interviews, and applications "
            "requiring follow-up.",
        )

        attention_df = df[
            df["Needs_Attention"]
        ].copy()

        if attention_df.empty:
            st.success(
                "No active applications currently "
                "require immediate attention."
            )

        else:
            attention_df["Priority"] = np.select(
                [
                    attention_df[
                        "Deadline_Overdue"
                    ],
                    attention_df[
                        "Interview_Upcoming"
                    ],
                    attention_df[
                        "Deadline_Upcoming"
                    ],
                    attention_df[
                        "Is_Stale"
                    ],
                ],
                [
                    "🔴 Overdue",
                    "🟣 Interview soon",
                    "🟠 Deadline soon",
                    "🟡 Follow up",
                ],
                default="Review",
            )

            priority_order = {
                "🔴 Overdue": 0,
                "🟣 Interview soon": 1,
                "🟠 Deadline soon": 2,
                "🟡 Follow up": 3,
                "Review": 4,
            }

            attention_df[
                "_priority_order"
            ] = attention_df[
                "Priority"
            ].map(
                priority_order
            )

            attention_df = attention_df.sort_values(
                [
                    "_priority_order",
                    "Action_Deadline",
                    "Days_Since_Update",
                ],
                ascending=[
                    True,
                    True,
                    False,
                ],
                na_position="last",
            )

            # Convert dates to display-ready strings *after* sorting
            # (sorting still needs real datetimes) so the grid never
            # has to render a raw NaT/None value itself.
            attention_df["Action_Deadline"] = attention_df[
                "Action_Deadline"
            ].map(format_display_date)

            attention_df["Interview_Date"] = attention_df[
                "Interview_Date"
            ].map(format_display_date)

            display_columns = [
                "Priority",
                "Company_Name",
                "Job_Title",
                "Current_Status",
                "Pipeline_Stage",
                "Action_Deadline",
                "Interview_Date",
                "Days_Since_Update",
            ]

            st.dataframe(
                attention_df[
                    display_columns
                ],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Company_Name": "Company",
                    "Job_Title": "Job Title",
                    "Current_Status": "Status",
                    "Pipeline_Stage": (
                        "Pipeline Stage"
                    ),
                    "Action_Deadline": (
                        "Action Deadline"
                    ),
                    "Interview_Date": (
                        "Interview Date"
                    ),
                    "Days_Since_Update": (
                        st.column_config.NumberColumn(
                            "Days Since Update",
                            format="%d days",
                        )
                    ),
                },
            )


# ============================================================
# PIPELINE ANALYTICS
# ============================================================

def render_pipeline_analytics(
    df: pd.DataFrame,
) -> None:
    """Render pipeline progression and follow-up analytics."""

    active_df = df[
        df["Is_Active"]
    ].copy()

    funnel = build_inferred_funnel(
        df
    )

    metrics = calculate_metrics(
        df
    )

    average_pipeline_age = (
        active_df[
            "Days_Open"
        ].dropna().mean()
        if not active_df.empty
        else np.nan
    )

    overdue_count = int(
        df["Deadline_Overdue"].sum()
    )

    upcoming_interviews = int(
        df["Interview_Upcoming"].sum()
    )

    metric_columns = st.columns(
        4
    )

    metric_columns[0].metric(
        "Active Applications",
        f"{metrics['active']:,}",
    )

    metric_columns[1].metric(
        "Average Pipeline Age",
        format_optional_number(
            average_pipeline_age,
            " days",
        ),
    )

    metric_columns[2].metric(
        "Overdue Actions",
        f"{overdue_count:,}",
    )

    metric_columns[3].metric(
        "Upcoming Interviews",
        f"{upcoming_interviews:,}",
    )

    st.write("")

    stage_column, conversion_column = (
        st.columns(2)
    )

    with stage_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Current Pipeline Stages",
                "Where applications currently "
                "sit in the hiring process.",
            )

            stage_counts = (
                df["Pipeline_Stage"]
                .value_counts()
                .rename_axis(
                    "Stage"
                )
                .reset_index(
                    name="Applications"
                )
            )

            stage_counts[
                "_stage_rank"
            ] = stage_counts[
                "Stage"
            ].map(
                PIPELINE_RANK
            ).fillna(
                999
            )

            stage_counts = stage_counts.sort_values(
                "_stage_rank"
            )

            figure = px.bar(
                stage_counts,
                x="Applications",
                y="Stage",
                orientation="h",
                text="Applications",
                color_discrete_sequence=[
                    COLORS[
                        "primary"
                    ]
                ],
            )

            figure.update_layout(
                yaxis={
                    "autorange": (
                        "reversed"
                    )
                }
            )

            figure.update_traces(
                textposition="outside"
            )

            render_chart(
                style_chart(
                    figure,
                    height=350,
                )
            )

    with conversion_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Stage Conversion",
                "Estimated progression from "
                "the preceding pipeline stage.",
            )

            conversion_df = funnel[
                funnel[
                    "Applications"
                ]
                > 0
            ].copy()

            conversion_df = conversion_df[
                conversion_df[
                    "Stage"
                ]
                != "Applied"
            ]

            if conversion_df.empty:
                render_empty_state(
                    "Stage conversion becomes "
                    "available when applications "
                    "progress beyond the initial stage."
                )

            else:
                figure = px.bar(
                    conversion_df,
                    x="Conversion",
                    y="Stage",
                    orientation="h",
                    text=conversion_df[
                        "Conversion"
                    ].map(
                        lambda value: (
                            f"{value:.0f}%"
                        )
                    ),
                    color_discrete_sequence=[
                        COLORS[
                            "success"
                        ]
                    ],
                )

                figure.update_layout(
                    yaxis={
                        "autorange": (
                            "reversed"
                        )
                    },
                    xaxis={
                        "range": [
                            0,
                            110,
                        ]
                    },
                )

                figure.update_traces(
                    textposition="outside"
                )

                render_chart(
                    style_chart(
                        figure,
                        height=350,
                    )
                )

    st.caption(
        "Stage progression is inferred from the "
        "current stage and known outcomes. Exact "
        "stage timing requires a separate "
        "stage-history table."
    )

    st.write("")

    ageing_column, update_column = st.columns(
        2
    )

    with ageing_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Active Pipeline Ageing",
                "How long active applications "
                "have remained open.",
            )

            age_counts = (
                active_df["Age_Band"]
                .value_counts(
                    sort=False
                )
                .rename_axis(
                    "Age Band"
                )
                .reset_index(
                    name="Applications"
                )
            )

            if (
                age_counts[
                    "Applications"
                ].sum()
                == 0
            ):
                render_empty_state(
                    "Valid application dates "
                    "are required for pipeline "
                    "ageing."
                )

            else:
                figure = px.bar(
                    age_counts,
                    x="Age Band",
                    y="Applications",
                    text="Applications",
                    color="Age Band",
                    color_discrete_sequence=[
                        "#C7D2FE",
                        "#A5B4FC",
                        "#818CF8",
                        "#6366F1",
                        "#4338CA",
                    ],
                )

                figure.update_layout(
                    showlegend=False
                )

                figure.update_traces(
                    textposition="outside"
                )

                figure.update_yaxes(
                    dtick=1
                )

                render_chart(
                    style_chart(
                        figure,
                        height=320,
                    )
                )

    with update_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Follow-up Queue",
                "Applications with the longest "
                "time since their latest update.",
            )

            stale_applications = (
                active_df.dropna(
                    subset=[
                        "Days_Since_Update"
                    ]
                )
                .sort_values(
                    "Days_Since_Update",
                    ascending=False,
                )
                .head(10)
            )

            if stale_applications.empty:
                render_empty_state(
                    "Add Last_Updated values "
                    "to generate the follow-up "
                    "queue."
                )

            else:
                figure = px.bar(
                    stale_applications,
                    x="Days_Since_Update",
                    y="Company_Name",
                    orientation="h",
                    color="Is_Stale",
                    color_discrete_map={
                        True: COLORS[
                            "warning"
                        ],
                        False: COLORS[
                            "primary_light"
                        ],
                    },
                    hover_data=[
                        "Job_Title",
                        "Current_Status",
                    ],
                )

                figure.update_layout(
                    showlegend=False,
                    yaxis={
                        "autorange": (
                            "reversed"
                        )
                    },
                )

                figure.add_vline(
                    x=7,
                    line_dash="dash",
                    line_color=COLORS[
                        "danger"
                    ],
                    annotation_text=(
                        "7-day threshold"
                    ),
                )

                render_chart(
                    style_chart(
                        figure,
                        height=320,
                    )
                )

    st.write("")

    with st.container(
        border=True,
    ):
        section_header(
            "Upcoming Interviews",
            "Interviews scheduled within "
            "the next seven days.",
        )

        interviews = df[
            df["Interview_Upcoming"]
        ].sort_values(
            "Interview_Date"
        )

        if interviews.empty:
            render_empty_state(
                "No interviews are currently "
                "scheduled within the next "
                "seven days."
            )

        else:
            interviews = interviews.copy()

            # Convert to display-ready strings after sorting so
            # the grid doesn't render a raw NaT/None cell.
            interviews["Interview_Date"] = interviews[
                "Interview_Date"
            ].map(format_display_date)

            st.dataframe(
                interviews[
                    [
                        "Interview_Date",
                        "Company_Name",
                        "Job_Title",
                        "Pipeline_Stage",
                        "Point_of_Contact",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Interview_Date": (
                        "Interview Date"
                    ),
                    "Company_Name": "Company",
                    "Job_Title": "Job Title",
                    "Pipeline_Stage": (
                        "Pipeline Stage"
                    ),
                    "Point_of_Contact": (
                        "Point of Contact"
                    ),
                },
            )


# ============================================================
# SOURCE AND ROLE PERFORMANCE
# ============================================================

def render_source_and_role_performance(
    df: pd.DataFrame,
) -> None:
    """Render source, job-family, location, and salary analysis."""

    source_performance = build_group_performance(
        df,
        "Platform_Source",
    )

    role_performance = build_group_performance(
        df,
        "Job_Family",
    )

    location_performance = build_group_performance(
        df,
        "Location_Type",
    )

    salary_disclosure_rate = safe_percentage(
        int(
            df[
                "Salary_Range_Posted"
            ].notna().sum()
        ),
        len(df),
    )

    known_sources = df[
        df["Platform_Source"]
        != "Not specified"
    ]["Platform_Source"].nunique()

    known_locations = df[
        df["Location_Type"]
        != "Not specified"
    ]["Location_Type"].nunique()

    metric_columns = st.columns(
        4
    )

    metric_columns[0].metric(
        "Application Sources",
        f"{known_sources:,}",
    )

    metric_columns[1].metric(
        "Job Families",
        f"{df['Job_Family'].nunique():,}",
    )

    metric_columns[2].metric(
        "Location Categories",
        f"{known_locations:,}",
    )

    metric_columns[3].metric(
        "Salary Disclosure Rate",
        f"{salary_disclosure_rate:.1f}%",
    )

    st.write("")

    volume_column, conversion_column = (
        st.columns(2)
    )

    with volume_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Applications by Source",
                "Which channels generate "
                "your application volume.",
            )

            volume_data = (
                source_performance.sort_values(
                    "Applications",
                    ascending=True,
                )
                .tail(12)
            )

            figure = px.bar(
                volume_data,
                x="Applications",
                y="Platform_Source",
                orientation="h",
                text="Applications",
                color_discrete_sequence=[
                    COLORS[
                        "primary"
                    ]
                ],
            )

            figure.update_traces(
                textposition="outside"
            )

            render_chart(
                style_chart(
                    figure,
                    height=360,
                )
            )

    with conversion_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Interview Conversion by Source",
                "Which platforms generate "
                "interviews rather than "
                "only applications.",
            )

            conversion_data = (
                source_performance.sort_values(
                    [
                        "Interview_Rate",
                        "Applications",
                    ],
                    ascending=True,
                )
                .tail(12)
            )

            figure = px.bar(
                conversion_data,
                x="Interview_Rate",
                y="Platform_Source",
                orientation="h",
                text=conversion_data[
                    "Interview_Rate"
                ].map(
                    lambda value: (
                        f"{value:.0f}%"
                    )
                ),
                color_discrete_sequence=[
                    COLORS[
                        "success"
                    ]
                ],
                hover_data={
                    "Applications": True,
                    "Interviews": True,
                    "Interview_Rate": ":.1f",
                },
            )

            figure.update_layout(
                xaxis={
                    "range": [
                        0,
                        110,
                    ]
                }
            )

            figure.update_traces(
                textposition="outside"
            )

            render_chart(
                style_chart(
                    figure,
                    height=360,
                )
            )

    st.write("")

    with st.container(
        border=True,
    ):
        section_header(
            "Source Performance Matrix",
            "Compare application volume "
            "against interview conversion.",
        )

        if len(
            source_performance
        ) < 2:
            render_empty_state(
                "At least two distinct sources "
                "are needed for meaningful "
                "source comparison."
            )

        else:
            figure = px.scatter(
                source_performance,
                x="Applications",
                y="Interview_Rate",
                size="Applications",
                color="Offers",
                hover_name="Platform_Source",
                text="Platform_Source",
                color_continuous_scale=[
                    COLORS["primary_light"],
                    COLORS["primary"],
                ],
                size_max=45,
                hover_data={
                    "Interviews": True,
                    "Active": True,
                    "Rejections": True,
                    "Interview_Rate": ":.1f",
                },
            )

            figure.update_traces(
                textposition="top center"
            )

            figure.update_yaxes(
                title="Interview Rate (%)",
                range=[
                    -5,
                    110,
                ],
            )

            figure.update_xaxes(
                title="Applications"
            )

            render_chart(
                style_chart(
                    figure,
                    height=390,
                )
            )

    st.write("")

    role_column, location_column = (
        st.columns(2)
    )

    with role_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Performance by Job Family",
                "Application volume and "
                "interview success by role.",
            )

            role_chart_data = role_performance[
                [
                    "Job_Family",
                    "Applications",
                    "Interviews",
                ]
            ].melt(
                id_vars=[
                    "Job_Family"
                ],
                value_vars=[
                    "Applications",
                    "Interviews",
                ],
                var_name="Metric",
                value_name="Count",
            )

            figure = px.bar(
                role_chart_data,
                x="Count",
                y="Job_Family",
                color="Metric",
                orientation="h",
                barmode="group",
                color_discrete_map={
                    "Applications": COLORS[
                        "primary_light"
                    ],
                    "Interviews": COLORS[
                        "success"
                    ],
                },
            )

            figure.update_layout(
                yaxis={
                    "autorange": (
                        "reversed"
                    )
                }
            )

            render_chart(
                style_chart(
                    figure,
                    height=340,
                )
            )

    with location_column:
        with st.container(
            border=True,
        ):
            section_header(
                "Performance by Location Type",
                "Compare remote, hybrid, "
                "on-site, and unspecified roles.",
            )

            location_chart_data = (
                location_performance.sort_values(
                    "Applications",
                    ascending=False,
                )
            )

            figure = px.bar(
                location_chart_data,
                x="Location_Type",
                y="Applications",
                text="Applications",
                color="Interview_Rate",
                color_continuous_scale=[
                    COLORS["primary_light"],
                    COLORS["primary"],
                ],
                hover_data={
                    "Interviews": True,
                    "Interview_Rate": ":.1f",
                },
            )

            figure.update_traces(
                textposition="outside"
            )

            figure.update_yaxes(
                dtick=1
            )

            figure.update_layout(
                coloraxis_colorbar={
                    "title": (
                        "Interview %"
                    )
                }
            )

            render_chart(
                style_chart(
                    figure,
                    height=340,
                )
            )

    st.write("")

    with st.container(
        border=True,
    ):
        section_header(
            "Platform Performance Details",
            "Detailed conversion and "
            "application-outcome metrics.",
        )

        st.dataframe(
            source_performance,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Platform_Source": (
                    "Platform Source"
                ),
                "Median_Days_To_Interview": (
                    st.column_config.NumberColumn(
                        "Median Days to Interview",
                        format="%.0f",
                    )
                ),
                "Interview_Rate": (
                    st.column_config.NumberColumn(
                        "Interview Rate",
                        format="%.1f%%",
                    )
                ),
                "Offer_Rate": (
                    st.column_config.NumberColumn(
                        "Offer Rate",
                        format="%.1f%%",
                    )
                ),
                "Rejection_Rate": (
                    st.column_config.NumberColumn(
                        "Rejection Rate",
                        format="%.1f%%",
                    )
                ),
            },
        )

    st.write("")

    with st.container(
        border=True,
    ):
        section_header(
            "Salary Intelligence",
            "Salary ranges are analyzed "
            "separately by currency.",
        )

        salary_df = df[
            df[
                "Salary_Midpoint"
            ].notna()
            & df[
                "Salary_Currency"
            ].notna()
        ].copy()

        if salary_df.empty:
            render_empty_state(
                "Add salary ranges with "
                "recognizable currencies, "
                "such as USD 60,000–80,000 "
                "or GHS 8,000–12,000."
            )

        else:
            salary_summary = (
                salary_df.groupby(
                    "Salary_Currency"
                )
                .agg(
                    Applications=(
                        "Company_Name",
                        "size",
                    ),
                    Median_Midpoint=(
                        "Salary_Midpoint",
                        "median",
                    ),
                    Minimum_Posted=(
                        "Salary_Min",
                        "min",
                    ),
                    Maximum_Posted=(
                        "Salary_Max",
                        "max",
                    ),
                )
                .reset_index()
            )

            st.dataframe(
                salary_summary,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Salary_Currency": (
                        "Currency"
                    ),
                    "Median_Midpoint": (
                        st.column_config.NumberColumn(
                            "Median Midpoint",
                            format="%.0f",
                        )
                    ),
                    "Minimum_Posted": (
                        st.column_config.NumberColumn(
                            "Minimum Posted",
                            format="%.0f",
                        )
                    ),
                    "Maximum_Posted": (
                        st.column_config.NumberColumn(
                            "Maximum Posted",
                            format="%.0f",
                        )
                    ),
                },
            )

            st.caption(
                "Monthly, annual, hourly, "
                "and contract salaries are "
                "not automatically normalized."
            )

    with st.expander(
        "View job-family classification rules"
    ):
        for family, keywords in (
            JOB_FAMILY_RULES.items()
        ):
            st.markdown(
                f"**{family}:** "
                + ", ".join(
                    keywords
                )
            )


# ============================================================
# APPLICATION EXPLORER
# ============================================================

def render_application_explorer(
    df: pd.DataFrame,
) -> None:
    """Render a searchable and downloadable application ledger."""

    search_column, sort_column = st.columns(
        [
            2,
            1,
        ]
    )

    with search_column:
        search_query = st.text_input(
            "Search applications",
            placeholder=(
                "Search company, role, source, "
                "contact, or job description"
            ),
            key="explorer_search",
        )

    with sort_column:
        sort_option = st.selectbox(
            "Sort by",
            options=[
                "Most recently updated",
                "Newest application",
                "Oldest application",
                "Upcoming deadline",
                "Company name",
            ],
            key="explorer_sort",
        )

    explorer_df = df.copy()

    if search_query.strip():
        searchable_columns = [
            "Company_Name",
            "Job_Title",
            "Platform_Source",
            "Point_of_Contact",
            "JD_Summary",
        ]

        matching_rows = pd.Series(
            False,
            index=explorer_df.index,
        )

        for column in searchable_columns:
            matching_rows = (
                matching_rows
                | explorer_df[column]
                .fillna("")
                .astype(str)
                .str.contains(
                    search_query.strip(),
                    case=False,
                    regex=False,
                )
            )

        explorer_df = explorer_df[
            matching_rows
        ]

    sort_configuration = {
        "Most recently updated": (
            "Last_Updated",
            False,
        ),
        "Newest application": (
            "Application_Date",
            False,
        ),
        "Oldest application": (
            "Application_Date",
            True,
        ),
        "Upcoming deadline": (
            "Action_Deadline",
            True,
        ),
        "Company name": (
            "Company_Name",
            True,
        ),
    }

    sort_column_name, ascending = (
        sort_configuration[
            sort_option
        ]
    )

    explorer_df = explorer_df.sort_values(
        sort_column_name,
        ascending=ascending,
        na_position="last",
    )

    explorer_df["Attention"] = np.select(
        [
            explorer_df[
                "Deadline_Overdue"
            ],
            explorer_df[
                "Interview_Upcoming"
            ],
            explorer_df[
                "Deadline_Upcoming"
            ],
            explorer_df[
                "Is_Stale"
            ],
        ],
        [
            "🔴 Overdue",
            "🟣 Interview",
            "🟠 Deadline",
            "🟡 Follow up",
        ],
        default="",
    )

    display_columns = [
        "Attention",
        "Company_Name",
        "Job_Title",
        "Job_Family",
        "Application_Date",
        "Current_Status",
        "Pipeline_Stage",
        "Location_Type",
        "Platform_Source",
        "Salary_Range_Posted",
        "Interview_Date",
        "Action_Deadline",
        "Days_Open",
        "Days_Since_Update",
        "Point_of_Contact",
        "Job_Posting_URL",
        "Constructive_Feedback",
        "Last_Updated",
        "JD_Summary",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in explorer_df.columns
    ]

    # Build the CSV export from the *raw* (still-datetime) columns
    # first, before we convert anything to display strings below —
    # this keeps ISO-style dates in the downloaded file, which plays
    # nicer with Excel/Sheets than the "DD MMM YYYY" display format.
    csv_data = (
        explorer_df[
            available_columns
        ]
        .to_csv(
            index=False
        )
        .encode(
            "utf-8"
        )
    )

    download_column, count_column = st.columns(
        [
            1,
            3,
        ]
    )

    with download_column:
        st.download_button(
            label="Download Filtered CSV",
            data=csv_data,
            file_name=(
                "job_application_pipeline.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

    with count_column:
        st.caption(
            f"Showing {len(explorer_df):,} "
            "matching applications."
        )

    # Convert date columns to display-ready strings *after* the CSV
    # export and *after* sorting, so the on-screen grid never has to
    # render a raw NaT/None value (which Streamlit's DateColumn shows
    # as the literal text "None").
    for date_column in [
        "Application_Date",
        "Interview_Date",
        "Action_Deadline",
        "Last_Updated",
    ]:
        if date_column in explorer_df.columns:
            explorer_df[date_column] = explorer_df[
                date_column
            ].map(format_display_date)

    st.dataframe(
        explorer_df[
            available_columns
        ],
        hide_index=True,
        use_container_width=True,
        height=600,
        column_config={
            "Company_Name": (
                st.column_config.TextColumn(
                    "Company",
                    width="medium",
                )
            ),
            "Job_Title": (
                st.column_config.TextColumn(
                    "Job Title",
                    width="large",
                )
            ),
            "Job_Family": (
                "Job Family"
            ),
            "Application_Date": (
                "Applied"
            ),
            "Current_Status": (
                "Status"
            ),
            "Pipeline_Stage": (
                "Pipeline Stage"
            ),
            "Location_Type": (
                "Location"
            ),
            "Platform_Source": (
                "Source"
            ),
            "Salary_Range_Posted": (
                "Posted Salary"
            ),
            "Interview_Date": (
                "Interview"
            ),
            "Action_Deadline": (
                "Deadline"
            ),
            "Days_Open": (
                st.column_config.NumberColumn(
                    "Days Open",
                    format="%d",
                )
            ),
            "Days_Since_Update": (
                st.column_config.NumberColumn(
                    "Days Since Update",
                    format="%d",
                )
            ),
            "Point_of_Contact": (
                "Contact"
            ),
            "Job_Posting_URL": (
                st.column_config.LinkColumn(
                    "Job Posting",
                    display_text="Open posting",
                )
            ),
            "Constructive_Feedback": (
                st.column_config.TextColumn(
                    "Feedback",
                    width="large",
                )
            ),
            "Last_Updated": (
                "Last Updated"
            ),
            "JD_Summary": (
                st.column_config.TextColumn(
                    "Job Description Summary",
                    width="large",
                )
            ),
        },
    )


# ============================================================
# DATA QUALITY
# ============================================================

def render_data_quality(
    df: pd.DataFrame,
) -> None:
    """Display completion rates for important reporting fields."""

    total_records = len(
        df
    )

    if total_records == 0:
        return

    quality_checks = {
        "Application date": int(
            df[
                "Application_Date"
            ].isna().sum()
        ),
        "Last updated": int(
            df[
                "Last_Updated"
            ].isna().sum()
        ),
        "Job title": int(
            df[
                "Job_Title"
            ].eq(
                "Not specified"
            ).sum()
        ),
        "Platform source": int(
            df[
                "Platform_Source"
            ].eq(
                "Not specified"
            ).sum()
        ),
        "Location type": int(
            df[
                "Location_Type"
            ].eq(
                "Not specified"
            ).sum()
        ),
    }

    missing_total = sum(
        quality_checks.values()
    )

    if missing_total == 0:
        st.caption(
            "Data quality: all core reporting "
            "fields are populated."
        )

        return

    with st.expander(
        "Data quality checks",
        expanded=False,
    ):
        quality_rows = []

        for field, missing_count in (
            quality_checks.items()
        ):
            completion_rate = (
                100
                - safe_percentage(
                    missing_count,
                    total_records,
                )
            )

            quality_rows.append(
                {
                    "Field": field,
                    "Missing Records": (
                        missing_count
                    ),
                    "Completion Rate": (
                        completion_rate
                    ),
                }
            )

        quality_df = pd.DataFrame(
            quality_rows
        )

        st.dataframe(
            quality_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Completion Rate": (
                    st.column_config.ProgressColumn(
                        "Completion Rate",
                        min_value=0,
                        max_value=100,
                        format="%.0f%%",
                    )
                )
            },
        )

        if quality_checks[
            "Application date"
        ] > 0:
            st.warning(
                "Missing application dates limit "
                "trend reporting, pipeline ageing, "
                "and interview timing analysis."
            )

        if quality_checks[
            "Last updated"
        ] > 0:
            st.info(
                "Missing Last_Updated values limit "
                "stale-application detection "
                "and follow-up tracking."
            )


# ============================================================
# MAIN APPLICATION
# ============================================================

def main() -> None:
    """Run the complete job-application dashboard."""

    st.markdown(
        '<p class="eyebrow">'
        "Job Search HQ"
        "</p>",
        unsafe_allow_html=True,
    )

    st.title(
        "My Job Hunt Dashboard"
    )

    st.markdown(
        '<p class="page-description">'
        "Track application momentum, recruitment "
        "conversion, source effectiveness, "
        "and follow-up priorities."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner(
            "Loading application data "
            "from Google Sheets..."
        ):
            raw_df = load_sheet_data()

    except FileNotFoundError as error:
        st.error(
            str(error)
        )

        st.info(
            "Place token.json in the same "
            "directory as your Streamlit "
            "application."
        )

        st.stop()

    except gspread.exceptions.APIError as error:
        st.error(
            "Google Sheets returned an API error. "
            "Check account permissions, spreadsheet "
            "access, and API quotas."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(
                error
            )

        st.stop()

    except Exception as error:
        st.error(
            "Unable to load application records "
            "from Google Sheets."
        )

        with st.expander(
            "Technical details"
        ):
            st.exception(
                error
            )

        st.stop()

    if raw_df.empty:
        st.warning(
            "Your Google Sheet is connected, "
            "but no application records "
            "were returned."
        )

        st.stop()

    try:
        dashboard_df = normalize_dataframe(
            raw_df
        )

    except ValueError as error:
        st.error(
            str(error)
        )

        st.stop()

    filtered_df = render_sidebar(
        dashboard_df
    )

    render_data_quality(
        dashboard_df
    )

    if filtered_df.empty:
        st.warning(
            "No applications match the "
            "selected filters."
        )

        st.stop()

    st.write("")

    (
        overview_tab,
        pipeline_tab,
        performance_tab,
        explorer_tab,
    ) = st.tabs(
        [
            "Executive Overview",
            "Pipeline Analytics",
            "Source & Role Performance",
            "Application Explorer",
        ]
    )

    with overview_tab:
        render_overview(
            filtered_df
        )

    with pipeline_tab:
        render_pipeline_analytics(
            filtered_df
        )

    with performance_tab:
        render_source_and_role_performance(
            filtered_df
        )

    with explorer_tab:
        render_application_explorer(
            filtered_df
        )


if __name__ == "__main__":
    main()