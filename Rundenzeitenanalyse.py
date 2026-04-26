from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# 1. Seiteneinstellungen
st.set_page_config(page_title="Rundenzeitenanalyse", layout="wide")


# 2. Hilfsfunktionen
def parse_lap_time_to_seconds(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text == "" or text.lower() in {"nan", "nat", "none"}:
        return None

    parts = text.split(":")

    try:
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1].replace(",", "."))
            return minutes * 60 + seconds

        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[1].replace(",", "."))
            return hours * 3600 + minutes * 60 + seconds

        return None
    except ValueError:
        return None


def format_seconds_to_mmss(total_seconds):
    if pd.isna(total_seconds):
        return ""

    total_seconds = int(round(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def build_file_options(excel_files):
    file_options = {}

    for file_path in excel_files:
        display_name = file_path.stem.split("_")[0]

        if display_name in file_options:
            display_name = f"{display_name} | {file_path.name}"

        file_options[display_name] = file_path

    return file_options


# 3. Basisordner
base_path = Path(".")
excel_files = sorted(list(base_path.glob("*.xlsx")) + list(base_path.glob("*.xls")))

if not excel_files:
    st.error(f"Keine Excel-Dateien im Ordner gefunden: {base_path}")
    st.stop()


# 4. Dateiauswahl vorbereiten
file_options = build_file_options(excel_files)


# 5. Titel
st.title("Rundenzeitenanalyse")


# 6. Datei und Contest auswählen
top_col_1, top_col_2 = st.columns([1, 1])

with top_col_1:
    selected_file_label = st.selectbox("Datei auswählen", list(file_options.keys()))

selected_file_path = file_options[selected_file_label]

df = pd.read_excel(selected_file_path)

df["Name_with_pos"] = df["Name"].astype(str) + " (" + df["Pos"].astype(str) + ")"

required_columns = ["Contest", "Name"]
missing_required_columns = [col for col in required_columns if col not in df.columns]

if missing_required_columns:
    st.error(
        "Diese benötigten Spalten fehlen in der Datei: "
        + ", ".join(missing_required_columns)
    )
    st.stop()


# 7. Rundenspalten erkennen
lap_columns = [str(i) for i in range(1, 11)]
available_lap_columns = [col for col in lap_columns if col in df.columns]

if not available_lap_columns:
    st.error("Es wurden keine Rundenspalten 1 bis 10 gefunden.")
    st.stop()


# 8. Zeiten umwandeln
for col in available_lap_columns:
    df[col] = df[col].apply(parse_lap_time_to_seconds)


# 9. Long-Format
df_long = df.melt(
    id_vars=["Contest", "Name", "Name_with_pos"],
    value_vars=available_lap_columns,
    var_name="Lap",
    value_name="LapTimeSeconds"
)

df_long = df_long.dropna(subset=["LapTimeSeconds"]).copy()
df_long["Lap"] = df_long["Lap"].astype(int)
df_long = df_long.sort_values(["Contest", "Name", "Lap"])


# 10. Contest-Auswahl
contest_options = sorted(df_long["Contest"].dropna().unique())

if not contest_options:
    st.error("Keine Contest-Werte gefunden.")
    st.stop()

with top_col_2:
    selected_contest = st.selectbox("Contest auswählen", contest_options)


# 11. Namen für Contest
name_options = sorted(
    df_long.loc[df_long["Contest"] == selected_contest, "Name"].dropna().unique()
)

if not name_options:
    st.warning("Keine Namen für den gewählten Contest gefunden.")
    st.stop()


# 12. Session-State für Auswahl
selection_state_key = f"selected_names::{selected_file_label}::{selected_contest}"
meta_state_key = f"name_meta::{selected_file_label}::{selected_contest}"

current_meta = {
    "file": selected_file_label,
    "contest": selected_contest,
    "names": tuple(name_options)
}

if selection_state_key not in st.session_state:
    contest_df = df.loc[df["Contest"] == selected_contest].copy()

    if "Pos" in contest_df.columns:
        contest_df["Pos_num"] = pd.to_numeric(
            contest_df["Pos"].astype(str).str.replace(".", "", regex=False),
            errors="coerce"
        )
        contest_df = contest_df.sort_values("Pos_num")
        top_names = contest_df["Name"].dropna().head(15).tolist()
    else:
        top_names = name_options[:15]

    st.session_state[selection_state_key] = set(top_names)

if meta_state_key not in st.session_state:
    st.session_state[meta_state_key] = current_meta
else:
    previous_meta = st.session_state[meta_state_key]
    if previous_meta != current_meta:
        previous_selected = st.session_state.get(selection_state_key, set())
        st.session_state[selection_state_key] = {
            name for name in previous_selected if name in name_options
        }
        st.session_state[meta_state_key] = current_meta


# 13. Layout: Plot links, Auswahl rechts
plot_col, select_col = st.columns([4.5, 1.6], gap="large")


# 14. Rechte Seite: scrollbare Checkbox-Liste
with select_col:
    st.subheader("Namen auswählen")

    action_col_1, action_col_2 = st.columns([1, 1])

    with action_col_1:
        if st.button("Alle", use_container_width=True, key=f"all_btn_{selected_file_label}_{selected_contest}"):
            st.session_state[selection_state_key] = set(name_options)

    with action_col_2:
        if st.button("Keine", use_container_width=True, key=f"none_btn_{selected_file_label}_{selected_contest}"):
            st.session_state[selection_state_key] = set()

    st.caption(f"{len(name_options)} Namen")

    checkbox_container = st.container(height=560, border=True)

    for name in name_options:
        checkbox_key = f"checkbox::{selected_file_label}::{selected_contest}::{name}"
        current_value = name in st.session_state[selection_state_key]

        checked = checkbox_container.checkbox(
            name,
            value=current_value,
            key=checkbox_key
        )

        if checked:
            st.session_state[selection_state_key].add(name)
        else:
            st.session_state[selection_state_key].discard(name)

    selected_names = sorted(st.session_state[selection_state_key])


# 15. Plot links
with plot_col:
    filtered_df = df_long[
        (df_long["Contest"] == selected_contest) &
        (df_long["Name"].isin(selected_names))
    ].copy()

    if filtered_df.empty:
        st.info("Bitte rechts mindestens einen Namen auswählen.")
    else:
        filtered_df["LapTimeLabel"] = filtered_df["LapTimeSeconds"].apply(format_seconds_to_mmss)

        fig = px.line(
            filtered_df,
            x="Lap",
            y="LapTimeSeconds",
            color="Name_with_pos",
            markers=True,
            title=f"{selected_file_label} - {selected_contest}",
            hover_data={
                "Lap": False,
                "LapTimeSeconds": False,
                "LapTimeLabel": True,
                "Name_with_pos": False,
                "Name": True
            }
        )

        max_lap = int(filtered_df["Lap"].max())
        y_min = int(filtered_df["LapTimeSeconds"].min())
        y_max = int(filtered_df["LapTimeSeconds"].max())

        tick_start = max(0, (y_min // 30) * 30)
        tick_end = ((y_max // 30) + 1) * 30
        y_tick_values = list(range(tick_start, tick_end + 1, 30))

        if len(y_tick_values) < 2:
            if y_min == y_max:
                y_tick_values = [y_min, y_min + 30]
            else:
                y_tick_values = [y_min, y_max]

        fig.update_layout(
            xaxis_title="Runde",
            yaxis_title="Rundenzeit",
            hovermode="closest",
            height=700,
            legend_title_text="Name"
        )

        fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(1, max_lap + 1)),
            range=[0.8, max_lap + 0.2]
        )

        fig.update_yaxes(
            tickmode="array",
            tickvals=y_tick_values,
            ticktext=[format_seconds_to_mmss(value) for value in y_tick_values]
        )

        st.plotly_chart(fig, use_container_width=True)