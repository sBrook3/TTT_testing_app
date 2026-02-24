import streamlit as st
import pandas as pd
import plotly.express as px
from process_race_ttt import read_fit_file, process_race_ttt

st.set_page_config(layout="wide", page_title="TTT Analysis App")

# ------------------------------
# Session state initialization
# ------------------------------
if "combined_long" not in st.session_state:
    st.session_state.combined_long = None
if "tt_2k" not in st.session_state:
    st.session_state.tt_2k = None
if "selected_finish_dist" not in st.session_state:
    st.session_state.selected_finish_dist = None
if "rider_data" not in st.session_state:
    st.session_state.rider_data = {}

# ------------------------------
# Tabs
# ------------------------------
tab1, tab2, tab3 = st.tabs(["Import Files", "View Charts", "Calculate Drag"])

@st.cache_data(show_spinner=True)
def process_combined_files(file_dict):
    """
    file_dict: dict of {rider_name: file_buffer}
    Returns: combined_long, combined_wide
    """
    combined_list = []
    
    for rider_name, uploader in file_dict.items():
        if uploader is not None:
            fit_data = read_fit_file(uploader)
            processed = process_race_ttt(fit_data, rider_name)
            df = processed["full_race"].copy()
            df["rider_id"] = rider_name
            combined_list.append(df)
    if not combined_list:
        return None, None
    combined_long = pd.concat(combined_list, ignore_index=True)
    
    value_cols = ["power", "torque", "cadence", "speed", "heart_rate", "distance"]
    wide = combined_long.pivot(index="timestamp", columns="rider", values=value_cols)
    
    wide.columns = [
        f"{val}_{str(rider)}"
        for val, rider in zip(
                wide.columns.get_level_values(0),
                wide.columns.get_level_values(1)
        )
    ]
    combined_wide = wide.reset_index()
    return combined_long, combined_wide
# ------------------------------
# TAB 1: Import Files
# ------------------------------
with tab1:
    st.header("Upload Rider FIT files")

    run_no = st.text_input("Run number")

    uploaders = {}
    for i in range(1, 9):
        uploader = st.file_uploader(label=f"Rider{i}",
                                    type=".fit",
                                    key=f"uploader{i}"
        )
        uploaders[f"rider{i}"] = uploader
        
    
#upload button
    if st.button("Upload and Process Files"):
        #clear previous session state
        st.session_state.rider_data.clear()
        st.session_state.combined_long = None
        st.session_state.combined_wide = None
        #process files via cached function
        combined_long, combined_wide = process_combined_files(uploaders)
        
        if combined_long is not None and combined_wide is not None:
            st.session_state.combined_long = combined_long
            st.session_state.combined_wide = combined_wide
            
            #save rider data for ref
            for rider_name, uploader in uploaders.items():
                if uploader is not None:
                    fit_data = read_fit_file(uploader)
                    processed = process_race_ttt(fit_data, rider_name)
                    st.session_state.rider_data[rider_name] = processed
            st.success("All files processed successfully")
            
            #download buttons
        if "combined_long" in st.session_state and "combined_wide" in st.session_state:
            long_data = st.session_state.combined_long.to_csv(index=False).encode()
            wide_data = st.session_state.combined_wide.to_csv(index=False).encode()
    
        st.download_button(
            label="Download Combined (long) CSV",
            data=long_data,
            file_name=f"ttt_combined_{run_no if run_no else 'run'}_long.csv",
            mime="text/csv"
            )
        st.download_button(
            label="Download Combined (wide) CSV",
            data=wide_data,
            file_name=f"ttt_combined_{run_no if run_no else 'run'}_wide.csv",
            mime="text/csv"
            )
        

# ------------------------------
# TAB 2: View Charts
# ------------------------------
with tab2:
    df = st.session_state.combined_long

    if df is None:
        st.info("Upload and process files first in Tab 1.")
        st.stop()
    else:
        st.header("Full Files Plots")
        df = df.copy()

        # Full Power plot
        fig_power = px.line(
            df,
            x="distance",
            y="power",
            color="rider_id",
            title="Power vs Distance"
        )
        st.plotly_chart(fig_power, use_container_width=True)

        # Full Speed plot
        fig_speed = px.line(
            df,
            x="distance",
            y="speed",
            color="rider_id",
            title="Speed vs Distance"
        )
        st.plotly_chart(fig_speed, use_container_width=True)
        
        summary = df[["power", "speed", "rider"]].groupby("rider").mean().round(0)
        time = df.groupby("rider")["timestamp"].max()-df.groupby("rider")["timestamp"].min()
        time_secs = time.dt.total_seconds()
        time_secs = time_secs.apply(lambda x: f"{int(x//60)}m {int(x%60)}s")
        summary = pd.concat([summary, time_secs], axis=1)
        summary=summary.reset_index().rename(columns={"rider":""})
        summary = summary.rename(columns={
            "power":"Average Power (w)", 
            "speed":"Average Speed (m/s)", 
            "timestamp":"Total Time (s)"})
        
        st.dataframe(summary, hide_index=True)


        # ------------------------------
        # Slider for Finish Distance (replaces click)
        # ------------------------------
        timestamps = sorted(df["timestamp"].tolist())

        finish_time = st.select_slider(
            "Select Finish Time",
            options=timestamps,
            value=timestamps[-1],
            key="finish_time_slider"
        )
        st.session_state.selected_finish_time = finish_time
        st.write(finish_time)


        # Calculate start distance for 2k effort

    

# ------------------------------
# TAB 3: Calculate Drag (placeholder)
# ------------------------------
with tab3:
    st.header("Drag Calculation")
    st.info("Tab not implemented yet.")
