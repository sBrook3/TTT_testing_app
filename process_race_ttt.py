#process_race_ttt for python

import pandas as pd 
import numpy as np 
import fitdecode
import math

#-----------------
#Read fit file
#-----------------

def read_fit_file(file_input):
    """
    Reads a fit file and returns a pandas df of records.

    """
    if file_input is None:
        print("No file uploaded.")
        return None
    
    #extract records into list of dicts
    records_list = []
    
    try:
        with fitdecode.FitReader(file_input) as fit:
            for frame in fit:
                # Only process data messages
                if isinstance(frame, fitdecode.records.FitDataMessage):
                    # Only keep record messages (time-series data)
                    if frame.name == "record":
                        record_dict = {}

                        for field in frame.fields:
                            record_dict[field.name] = field.value

                        records_list.append(record_dict)
    except Exception as e: 
        print(f"Error reading FIT file: {e}")
        return None
        
    if not records_list:
        print("No records found in file.")
        return None
    
    df = pd.DataFrame(records_list)
    
    if 'timestamp' in df.columns:
        df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df

#--------------------
#Process race data
#--------------------

def process_race_ttt(fit_data, rider_id):
    """
    processes fitfile for rider. returns dict with full_race DataFrame and warnings list

    """
    if fit_data is None:
        return None
    
    new_race = fit_data.copy()
    warnings_vec = []
    
    if 'speed' in new_race.columns:
        new_race['speed'] = new_race['speed']*3.6
    
    if  'power' in new_race.columns and 'cadence' in new_race.columns:
        new_race['torque'] = new_race.apply(
            lambda row: row['power']*60/(2*math.pi*row['cadence'])
            if pd.notna(row['power']) and pd.notna(row['cadence']) and row['cadence'] != 0
            else np.nan,
            axis=1
        )
        
    if 'power' in new_race.columns and (new_race['power'] > 2500).any():
        warnings_vec.append("WARNING: possible corrupted file, sprint data appears valid")
    
    if 'heart_rate' not in new_race.columns:
        new_race['heart_rate'] = np.nan 
    
    cols_to_keep = ['timestamp', 'power', 'torque', 'cadence', 'speed', 
                    'position_lat', 'position_long', 'heart_rate', 'altitude', 'distance']
    for col in cols_to_keep:
        if col not in new_race.columns:
            new_race[col] = np.nan
    
    new_race = new_race[cols_to_keep]
    new_race['rider'] = rider_id
    
    return {
        'full_race': new_race,
        'warnings': warnings_vec,
    }

#---------------------
#wprime and anaerobic calcs
#---------------------

def recalc_anaerobic(df, cp, wprime, recovery_rate):
    """
    Calculate anaerobic capacity
    """
    df = df.copy()
    df['dcp'] = cp - df['power']
    cumulative_sum = wprime
    anaerobic_capacity = []
    
    for i, row in df.iterrows():
        current_value = row['dcp']
        prev_ac = anaerobic_capacity[i-1] if i > 0 else 0
        
        if current_value <= 0:
            ac = cumulative_sum - row['power']
            cumulative_sum = ac
        else:
            ac = min(cumulative_sum + current_value * recovery_rate * (1 + (wprime - prev_ac)/wprime),
                     wprime)
            cumulative_sum = ac 
        
        anaerobic_capacity.append(ac)
    
    df['anaerobic_capacity_replenished'] = anaerobic_capacity
    return df
        