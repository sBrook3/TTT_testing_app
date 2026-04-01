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
            x="timestamp",
            y="power",
            color="rider_id",
            title="Power vs Time"
        )
        st.plotly_chart(fig_power, use_container_width=True)

        # Full Speed plot
        fig_speed = px.line(
            df,
            x="timestamp",
            y="speed",
            color="rider_id",
            title="Speed vs Time"
        )
        st.plotly_chart(fig_speed, use_container_width=True)
        
        # Full Cadence plot
        fig_cadence = px.line(
            df,
            x="timestamp",
            y="cadence",
            color="rider_id",
            title="cadence vs Time"
        )
        st.plotly_chart(fig_cadence, use_container_width=True)
        
        rider_1_df = combined_long[combined_long['rider'] == 'rider1'].copy()
        rider_1_cad = rider_1_df['cadence']
        future_above_20 = rider_1_cad[::-1].gt(20).cummax()[::-1]
        mask = (rider_1_cad == 0) & (~future_above_20)
        finish_time = rider_1_df.loc[mask, 'timestamp'].iloc[0]
                       
        combined_long_finished = combined_long[combined_long['timestamp'] <= finish_time]
        
        finish_dist = combined_long_finished[combined_long_finished['rider'] == 'rider1']['distance'].tail(1).iloc[0]
        start_dist = finish_dist - 2000
        nearest_idx = (rider_1_df['distance'] - start_dist).abs().idxmin()
        start_time = rider_1_df.loc[nearest_idx, 'timestamp']
        
        combined_long_trimmed = combined_long_finished[combined_long_finished['timestamp'] >= start_time]
        
        st.write("Finish time: ", finish_time,
                 "Finish distance: ", finish_dist,
                 "Start distance: ", start_dist,
                 "Start time: ", start_time)
        
        # cut Power plot
        fig_power_cut = px.line(
            combined_long_trimmed,
            x="timestamp",
            y="power",
            color="rider_id",
            title="Power vs Time"
        )
        st.plotly_chart(fig_power_cut, use_container_width=True)

    

# ------------------------------
# TAB 3: Calculate Drag
# ------------------------------
with tab3:
    st.header("Drag Calculation")
    
    rider_drags = (combined_long_trimmed
                   .groupby('rider', as_index=False)
                   .agg({
                       'speed':'mean',
                       'power':'mean'})
                   )
    rider_drags = (rider_drags
                   .assign(
                       k=lambda d: d['speed']**3 / d['power'],
                       power_for_50=lambda d: 125000 / d['k']
                       )
                   )
    cols=rider_drags.columns.drop('rider')
    rider_drags.loc["Average", cols] = rider_drags[cols].mean()
    rider_drags.loc["Average", "rider"] = "Average"
    
        
    col_map = {
        'speed': ('Average Speed (km/h)', '{:.1f}'),
        'power': ('Average Power (W)', '{:.0f}'),
        'power_for_50': (f'Power required for 50 km/h (run {run_no})', '{:.0f}')
    }
    
    rename_dict = {k: v[0] for k, v in col_map.items()}
    format_dict = {v[0]: v[1] for v in col_map.values()}
        
    rider_drags_styled = (rider_drags
                          .drop(columns=['k'])
                          .rename(columns=rename_dict)
                          .style
                          .format(format_dict)
                          .apply(
                              lambda x: ['background-color: lightgrey'] * len(x)
                              if x.name == 'Average' else [''] * len(x),
                              axis=1
                              )
                          )
    
    st.dataframe(rider_drags_styled, hide_index=True, use_container_width=False)
    
    #set 250 splits and give drag per split
    #add distance to first page next to run number and build into start_dist calculator to allow shorter runs.
    
    
    
    
    
    