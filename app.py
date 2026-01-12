import streamlit as st
import pandas as pd

st.set_page_config(page_title="On-Ball Player Eval", layout="wide")

DATA_PATH = "drives_streamlit.csv"

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    df["Player"] = df["firstName"].astype(str) + " " + df["lastName"].astype(str)
    df.drop(columns='PredictionDateKey', inplace=True)
    return df


COUNT_COLS = {"drives", "picks", "isos"}

@st.cache_data
def add_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    grp = ["SeasonKey", "playerPositionDescription"]

    COUNT_COLS = {"drives", "picks", "isos"}
    exclude = {"SeasonKey", "PlayerKey"} | COUNT_COLS

    cand_cols = [c for c in out.columns if c not in exclude]

    num_cols = []
    for c in cand_cols:
        s = pd.to_numeric(out[c], errors="coerce")
        if s.notna().any():
            out[c] = s
            num_cols.append(c)

    for c in num_cols:
        out[f"{c}_pct"] = (
            out.groupby(grp)[c]
               .rank(pct=True, method="average", ascending=True)
               .mul(100)
               .round(1)
        )

    out.attrs["pct_cols"] = [f"{c}_pct" for c in num_cols]
    return out


df = load_data(DATA_PATH)
df = add_percentiles(df)  # <-- percentiles computed BEFORE any filters

st.title("On-Ball Player Evaluation")

# -----------------------
# Sidebar filters
# -----------------------
with st.sidebar:
    st.header("Filters")

    teams = st.multiselect("Team", sorted(df["TeamAbbrev"].dropna().unique()))
    seasons = st.multiselect("Season", sorted(df["SeasonKey"].dropna().unique()))
    positions = st.multiselect("Position", sorted(df["playerPositionDescription"].dropna().unique()))
    players = st.multiselect(
        "Player",
        options=sorted(df["Player"].dropna().unique()),
    )


    def safe_int_max(s) -> int:
        return int(pd.to_numeric(s, errors="coerce").fillna(0).max())

    drives_max = safe_int_max(df.get("drives", pd.Series([0])))
    picks_max  = safe_int_max(df.get("picks",  pd.Series([0])))
    isos_max   = safe_int_max(df.get("isos",   pd.Series([0])))

    def slider_min(label: str, max_val: int) -> int:
        if max_val <= 0:
            st.slider(label, min_value=0, max_value=1, value=0, disabled=True)
            return 0
        return st.slider(label, min_value=0, max_value=max_val, value=0)

    min_drives = slider_min("Drives (min)", drives_max)
    min_picks  = slider_min("Picks (min)",  picks_max)
    min_isos   = slider_min("ISOs (min)",   isos_max)

# -----------------------
# Apply filters (AFTER percentiles exist)
# -----------------------
f = df.copy()

if teams:
    f = f[f["TeamAbbrev"].isin(teams)]
if seasons:
    f = f[f["SeasonKey"].isin(seasons)]
if positions:
    f = f[f["playerPositionDescription"].isin(positions)]
if players:
    f = f[f["Player"].isin(players)]


# numeric filters (counts)
for c in ["drives", "picks", "isos"]:
    if c in f.columns:
        f[c] = pd.to_numeric(f[c], errors="coerce")

f = f[
    (f.get("drives", 0).fillna(0) >= min_drives) &
    (f.get("picks",  0).fillna(0) >= min_picks) &
    (f.get("isos",   0).fillna(0) >= min_isos)
]

# -----------------------
# Display: percentiles only (color-coded red->blue)
# -----------------------
pct_cols = df.attrs.get("pct_cols", [])
id_cols = ["Player", "TeamAbbrev", "SeasonKey", "playerPositionDescription"]
show_cols = id_cols + pct_cols

# Optional: sort by key percentiles if present
sort_by = [c for c in ["defensive_impact_iso_pct", "defensive_impact_pick_pct"] if c in f.columns]
if not sort_by:
    sort_by = ["Player"]

out = f[show_cols].sort_values(sort_by, ascending=False)

styler = (
    out.style
      .format({c: "{:.1f}" for c in pct_cols})
      .background_gradient(
          cmap="RdBu",   # low=red, high=blue
          vmin=0, vmax=100,
          subset=pct_cols
      )
)

st.dataframe(styler, use_container_width=True)
