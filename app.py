import streamlit as st
import pandas as pd
import time
import threading
import os
from datetime import datetime, timedelta, UTC
from db import (init_db, insert_reading, fetch_all, add_device, get_all_devices, 
                delete_device, update_device_status, get_device_status,
                add_classroom, get_all_classrooms, delete_classroom, get_classroom_devices,
                get_classroom_device_stats, update_device_switch_code)
from tuya_play import get_power_voltage_current, TuyaTokenInfo, request, set_device_switch, get_device_switch
import json

init_db()

st.set_page_config(page_title="Farashuddin Bhaban (FUB) Energy Monitoring", layout="wide", page_icon="EWU.png")

# SESSION STATE INITIALIZATION
if 'page' not in st.session_state:
    st.session_state['page'] = 'home'
if 'selected_classroom' not in st.session_state:
    st.session_state['selected_classroom'] = None
if 'selected_device' not in st.session_state:
    st.session_state['selected_device'] = None
if 'polling_threads' not in st.session_state:
    st.session_state['polling_threads'] = {}
if 'stop_events' not in st.session_state:
    st.session_state['stop_events'] = {}
if 'last_polls' not in st.session_state:
    st.session_state['last_polls'] = {}

UNIT_COST = float(os.getenv("ENERGY_UNIT_COST", 3.80))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", 60))

# Add default classroom if no classrooms exist
classrooms = get_all_classrooms()
if not classrooms:
    try:
        add_classroom("FUB-101")
        classrooms = get_all_classrooms()
    except:
        pass

# BACKGROUND POLLING FOR ALL DEVICES
def poll_loop(device_info, stop_event):
    device_id = device_info['id']
    consecutive_failures = 0
    
    while not stop_event.is_set():
        try:
            result = request("GET", "/v1.0/token", {"grant_type": 1}, None, 
                           device_info['access_id'], device_info['access_key'], 
                           device_info['api_endpoint'])
            
            if not result.get("success"):
                consecutive_failures += 1
                if consecutive_failures > 3:
                    update_device_status(device_id, "offline")
                time.sleep(POLL_INTERVAL)
                continue
                
            token_info = TuyaTokenInfo(result)
            
            switch_status = get_device_switch(
                device_info['device_id'],
                device_info['access_id'],
                device_info['access_key'],
                device_info['api_endpoint'],
                token_info
            )
            
            if switch_status is None:
                consecutive_failures += 1
                if consecutive_failures > 3:
                    update_device_status(device_id, "offline")
            else:
                status = "on" if switch_status else "off"
                update_device_status(device_id, status)
                consecutive_failures = 0
            
            power, voltage, current = get_power_voltage_current(
                device_info['device_id'],
                device_info['access_id'],
                device_info['access_key'],
                device_info['api_endpoint'],
                token_info
            )
            
            ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            if power is not None or voltage is not None or current is not None:
                insert_reading(
                    device_id,
                    ts, 
                    float(power) if power is not None else None,
                    float(voltage) if voltage is not None else None,
                    float(current) if current is not None else None
                )
            
        except Exception as e:
            print(f"Polling error for device {device_info['name']}: {e}")
            consecutive_failures += 1
            if consecutive_failures > 3:
                update_device_status(device_id, "offline")
        
        time.sleep(POLL_INTERVAL)

def start_all_polling():
    devices = get_all_devices()
    for device in devices:
        device_info = {
            'id': device[0],
            'name': device[1],
            'classroom_id': device[2],
            'access_id': device[3],
            'access_key': device[4],
            'device_id': device[5],
            'api_endpoint': device[6]
        }
        
        if device_info['id'] not in st.session_state['polling_threads']:
            stop_event = threading.Event()
            st.session_state['stop_events'][device_info['id']] = stop_event
            
            t = threading.Thread(
                target=poll_loop, 
                args=(device_info, stop_event),
                daemon=True
            )
            t.start()
            st.session_state['polling_threads'][device_info['id']] = t

start_all_polling()

# HOME PAGE (CLASSROOM SELECTION)
if st.session_state['page'] == 'home':
    st.title("FUB Available Classrooms")
    st.subheader("Select Classroom")
    
    classrooms = get_all_classrooms()
    
    cols_per_row = 3
    classroom_count = len(classrooms)
    
    for row in range((classroom_count + cols_per_row) // cols_per_row):
        cols = st.columns(cols_per_row)
        
        for col_idx in range(cols_per_row):
            classroom_idx = row * cols_per_row + col_idx
            
            with cols[col_idx]:
                if classroom_idx < classroom_count:
                    classroom = classrooms[classroom_idx]
                    classroom_id = classroom[0]
                    classroom_name = classroom[1]
                    
                    stats = get_classroom_device_stats(classroom_id)
                    total = stats['total']
                    on_count = stats['on']
                    off_count = stats['off']
                    offline_count = stats['offline']
                    
                    if total == 0:
                        bg_color = "#e2e3e5"
                        border_color = "#6c757d"
                    elif offline_count == total:
                        bg_color = "#e2e3e5"
                        border_color = "#6c757d"
                    elif on_count > 0:
                        bg_color = "#d4edda"
                        border_color = "#28a745"
                    else:
                        bg_color = "#f8d7da"
                        border_color = "#dc3545"
                    
                    st.markdown(f"""
                        <div style="
                            background-color: {bg_color};
                            border: 3px solid {border_color};
                            border-radius: 10px;
                            padding: 30px 20px;
                            text-align: center;
                            min-height: 200px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            margin-bottom: 10px;
                        ">
                            <div style="font-size: 2em; margin-bottom: 10px;">🚪</div>
                            <div style="font-size: 1.3em; font-weight: bold; color: #333; margin-bottom: 15px;">{classroom_name}</div>
                            <div style="display: flex; gap: 15px; justify-content: center; margin-top: 10px;">
                                <div style="text-align: center;">
                                    <div style="font-size: 1.5em; font-weight: bold; color: #333;">{total}</div>
                                    <div style="font-size: 0.8em; color: #666;">Total</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 1.5em; font-weight: bold; color: #28a745;">🟢 {on_count}</div>
                                    <div style="font-size: 0.8em; color: #666;">ON</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 1.5em; font-weight: bold; color: #dc3545;">🔴 {off_count}</div>
                                    <div style="font-size: 0.8em; color: #666;">OFF</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 1.5em; font-weight: bold; color: #6c757d;">⚫ {offline_count}</div>
                                    <div style="font-size: 0.8em; color: #666;">Offline</div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Open Classroom", key=f"open_class_{classroom_id}", width='stretch'):
                        st.session_state['selected_classroom'] = {
                            'id': classroom_id,
                            'name': classroom_name
                        }
                        st.session_state['page'] = 'classroom'
                        st.rerun()
                
                elif classroom_idx == classroom_count:
                    st.markdown("""
                        <div style="
                            background-color: #e7f3ff;
                            border: 3px dashed #007bff;
                            border-radius: 10px;
                            padding: 30px 20px;
                            text-align: center;
                            min-height: 200px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            margin-bottom: 10px;
                        ">
                            <div style="font-size: 3em; color: #007bff; margin-bottom: 10px;">+</div>
                            <div style="font-size: 1.2em; font-weight: bold; color: #007bff;">Add New Classroom</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Add Classroom", key="add_new_classroom", width='stretch'):
                        st.session_state['page'] = 'add_classroom'
                        st.rerun()

# ADD CLASSROOM PAGE
elif st.session_state['page'] == 'add_classroom':
    st.title("Add New Classroom")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("← Back to Home", width='stretch'):
            st.session_state['page'] = 'home'
            st.rerun()
    
    st.divider()
    
    with st.form("add_classroom_form"):
        classroom_name = st.text_input("Classroom Name*", placeholder="e.g., Room 101, Lab A, Office 201")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.form_submit_button("Add Classroom", width='stretch')
        with col2:
            cancel = st.form_submit_button("Cancel", width='stretch')
        
        if submitted:
            if classroom_name:
                try:
                    add_classroom(classroom_name)
                    st.success(f"✅ Classroom '{classroom_name}' added successfully!")
                    time.sleep(1)
                    st.session_state['page'] = 'home'
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add classroom: {e}")
            else:
                st.warning("Please enter a classroom name")
        
        if cancel:
            st.session_state['page'] = 'home'
            st.rerun()

# CLASSROOM DEVICES PAGE 
elif st.session_state['page'] == 'classroom':
    selected_classroom = st.session_state.get('selected_classroom')
    
    if not selected_classroom:
        st.session_state['page'] = 'home'
        st.rerun()
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Back to Classrooms", width='stretch'):
            st.session_state['page'] = 'home'
            st.rerun()
    with col2:
        st.title(f" {selected_classroom['name']}")
    with col3:
        if st.button("Delete Classroom", width='stretch'):
            try:
                delete_classroom(selected_classroom['id'])
                st.success("Classroom deleted!")
                time.sleep(1)
                st.session_state['page'] = 'home'
                st.session_state['selected_classroom'] = None
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete: {e}")
    
    st.divider()
    st.subheader("Devices in this Classroom")
    
    devices = get_classroom_devices(selected_classroom['id'])
    
    cols_per_row = 3
    device_count = len(devices)
    
    for row in range((device_count + cols_per_row) // cols_per_row):
        cols = st.columns(cols_per_row)
        
        for col_idx in range(cols_per_row):
            device_idx = row * cols_per_row + col_idx
            
            with cols[col_idx]:
                if device_idx < device_count:
                    device = devices[device_idx]
                    device_id = device[0]
                    device_name = device[1]
                    
                    status = get_device_status(device_id)
                    
                    if status == "on":
                        bg_color = "#d4edda"
                        border_color = "#28a745"
                        status_icon = "🟢"
                    elif status == "off":
                        bg_color = "#f8d7da"
                        border_color = "#dc3545"
                        status_icon = "🔴"
                    else:
                        bg_color = "#e2e3e5"
                        border_color = "#6c757d"
                        status_icon = "⚫"
                    
                    st.markdown(f"""
                        <div style="
                            background-color: {bg_color};
                            border: 3px solid {border_color};
                            border-radius: 10px;
                            padding: 40px 20px;
                            text-align: center;
                            min-height: 150px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            margin-bottom: 10px;
                        ">
                            <div style="font-size: 2em; margin-bottom: 10px;">{status_icon}</div>
                            <div style="font-size: 1.2em; font-weight: bold; color: #333;">{device_name}</div>
                            <div style="font-size: 0.9em; color: #666; margin-top: 5px; text-transform: capitalize;">{status}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Open Dashboard", key=f"open_dev_{device_id}", width='stretch'):
                        st.session_state['selected_device'] = {
                            'id': device[0],
                            'name': device[1],
                            'classroom_id': device[2],
                            'access_id': device[3],
                            'access_key': device[4],
                            'device_id': device[5],
                            'api_endpoint': device[6]
                        }
                        st.session_state['page'] = 'dashboard'
                        st.rerun()
                
                elif device_idx == device_count:
                    st.markdown("""
                        <div style="
                            background-color: #e7f3ff;
                            border: 3px dashed #007bff;
                            border-radius: 10px;
                            padding: 40px 20px;
                            text-align: center;
                            min-height: 150px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            margin-bottom: 10px;
                        ">
                            <div style="font-size: 3em; color: #007bff; margin-bottom: 10px;">+</div>
                            <div style="font-size: 1.2em; font-weight: bold; color: #007bff;">Add New Device</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Add Device", key="add_new_device", width='stretch'):
                        st.session_state['page'] = 'add_device'
                        st.rerun()

# ADD DEVICE PAGE
elif st.session_state['page'] == 'add_device':
    st.title("➕ Add New Device")
    
    selected_classroom = st.session_state.get('selected_classroom')
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("← Back to Classroom", width='stretch'):
            st.session_state['page'] = 'classroom'
            st.rerun()
    
    st.divider()
    
    with st.form("add_device_form"):
        device_name = st.text_input("Device Name*", placeholder="e.g., Smart Plug 1, Breaker A")
        access_id = st.text_input("Access ID*", placeholder="Tuya Access ID")
        access_key = st.text_input("Access Key*", type="password", placeholder="Tuya Access Key")
        device_id = st.text_input("Device ID*", placeholder="Tuya Device ID")
        api_endpoint = st.text_input("API Endpoint*", value="https://openapi.tuyaeu.com")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.form_submit_button("Add Device", width='stretch')
        with col2:
            cancel = st.form_submit_button("Cancel", width='stretch')
        
        if submitted:
            if device_name and access_id and access_key and device_id and api_endpoint:
                try:
                    add_device(device_name, selected_classroom['id'], access_id, access_key, device_id, api_endpoint)
                    st.success(f"✅ Device '{device_name}' added successfully!")
                    time.sleep(1)
                    st.session_state['page'] = 'classroom'
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add device: {e}")
            else:
                st.warning("Please fill all required fields")
        
        if cancel:
            st.session_state['page'] = 'classroom'
            st.rerun()

# DASHBOARD PAGE
elif st.session_state['page'] == 'dashboard':
    selected_device = st.session_state.get('selected_device')
    
    if not selected_device:
        st.session_state['page'] = 'classroom'
        st.rerun()
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Back to Devices", width='stretch'):
            st.session_state['page'] = 'classroom'
            st.rerun()
    with col2:
        st.title(f"💡 {selected_device['name']}")
    with col3:
        if st.button("🗑️ Delete Device", width='stretch'):
            try:
                if selected_device['id'] in st.session_state['stop_events']:
                    st.session_state['stop_events'][selected_device['id']].set()
                delete_device(selected_device['id'])
                st.success("Device deleted!")
                time.sleep(1)
                st.session_state['page'] = 'classroom'
                st.session_state['selected_device'] = None
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete: {e}")
    
    st.divider()
    
# SIDEBAR
    st.sidebar.header("⚙️ Device Control")
    
    try:
        result = request("GET", "/v1.0/token", {"grant_type": 1}, None, 
                       selected_device['access_id'], selected_device['access_key'], 
                       selected_device['api_endpoint'])
        token_info = TuyaTokenInfo(result)
        
        switch_state = get_device_switch(
            selected_device['device_id'],
            selected_device['access_id'],
            selected_device['access_key'],
            selected_device['api_endpoint'],
            token_info
        )
        
        col1, col2 = st.sidebar.columns(2)
        if col1.button("🟢 Turn ON", width='stretch', disabled=(switch_state == True)):
            success, actual_code = set_device_switch(True, selected_device['device_id'], selected_device['access_id'], 
                            selected_device['access_key'], selected_device['api_endpoint'], token_info,
                            selected_device.get('switch_code', 'switch'))
            if success:
                if actual_code != selected_device.get('switch_code'):
                    update_device_switch_code(selected_device['id'], actual_code)
                    selected_device['switch_code'] = actual_code
                st.sidebar.success("Device turned ON")
                time.sleep(1)
                st.rerun()
        
        if col2.button("🔴 Turn OFF", width='stretch', disabled=(switch_state == False)):
            success, actual_code = set_device_switch(False, selected_device['device_id'], selected_device['access_id'], 
                            selected_device['access_key'], selected_device['api_endpoint'], token_info,
                            selected_device.get('switch_code', 'switch'))
            if success:
                if actual_code != selected_device.get('switch_code'):
                    update_device_switch_code(selected_device['id'], actual_code)
                    selected_device['switch_code'] = actual_code
                st.sidebar.warning("Device turned OFF")
                time.sleep(1)
                st.rerun()
        
        status_color = "🟢" if switch_state else "🔴"
        status_text = "ON" if switch_state else "OFF"
        st.sidebar.metric("Current Status", f"{status_color} {status_text}")
    except:
        st.sidebar.error("Unable to connect to device")
    
    st.sidebar.divider()
    
    st.sidebar.header("📊 Data View")
    range_option = st.sidebar.selectbox(
        "Select Time Range", 
        ["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "Custom Range"],
        index=1
    )
    
    start_time = None
    end_time = None
    if range_option == "Custom Range":
        st.sidebar.caption("Enter custom date/time range")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date")
            start_time_input = st.time_input("Start Time", value=datetime.now().replace(hour=0, minute=0, second=0).time())
        with col2:
            end_date = st.date_input("End Date")
            end_time_input = st.time_input("End Time", value=datetime.now().time())
        
        start_time = datetime.combine(start_date, start_time_input).replace(tzinfo=UTC)
        end_time = datetime.combine(end_date, end_time_input).replace(tzinfo=UTC)
    
    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=False)
    
    st.sidebar.divider()
    
    st.sidebar.header("💰 Cost Settings")
    unit_cost_input = st.sidebar.number_input(
        "Cost per kWh (BDT)", 
        min_value=1.00, 
        max_value=20.00, 
        value=UNIT_COST, 
        step=0.01,
        format="%.3f"
    )
    
# LOAD DATA
    rows = fetch_all(selected_device['id'])
    if rows:
        df = pd.DataFrame(rows, columns=["timestamp", "power", "voltage", "current"])
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    else:
        df = pd.DataFrame(columns=["timestamp", "power", "voltage", "current"])
    
    now = datetime.now(UTC)
    if range_option == "Custom Range" and start_time and end_time:
        df_filtered = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)].copy()
    else:
        time_filters = {
            "Last Hour": timedelta(hours=1),
            "Last 24 Hours": timedelta(days=1),
            "Last 7 Days": timedelta(days=7),
            "Last 30 Days": timedelta(days=30),
        }
        selected_delta = time_filters.get(range_option)
        if selected_delta:
            cutoff = now - selected_delta
            df_filtered = df[df['timestamp'] >= cutoff].copy()
        else:
            df_filtered = df.copy()
    
# METRICS
    latest = df_filtered.iloc[-1] if not df_filtered.empty else None
    if latest is not None:
        current_power = latest['power'] if pd.notna(latest['power']) else 0.0
        current_voltage = latest['voltage'] if pd.notna(latest['voltage']) else 0.0
        current_current = latest['current'] if pd.notna(latest['current']) else 0.0
    else:
        current_power = 0.0
        current_voltage = 0.0
        current_current = 0.0
    
    if current_voltage > 0 and current_current > 0:
        apparent_power = current_voltage * current_current
        power_factor = (current_power / apparent_power) if apparent_power > 0 else 0.0
    else:
        power_factor = 0.0
    
    if not df_filtered.empty and df_filtered['power'].notna().any():
        df_sorted = df_filtered.sort_values('timestamp')
        df_sorted['delta_s'] = df_sorted['timestamp'].diff().dt.total_seconds().fillna(0)
        df_sorted['energy_kwh_interval'] = df_sorted['power'] * df_sorted['delta_s'] / 3_600_000.0
        total_kwh = df_sorted['energy_kwh_interval'].sum()
    else:
        total_kwh = 0.0
        df_sorted = df_filtered.copy()
    
    total_cost = total_kwh * unit_cost_input
    
    st.subheader("⚡ Real-Time Metrics")
    metric_cols = st.columns(4)
    
    with metric_cols[0]:
        st.metric("Voltage (V)", f"{current_voltage:.1f}")
    with metric_cols[1]:
        st.metric("Current (A)", f"{current_current:.3f}")
    with metric_cols[2]:
        st.metric("Power (W)", f"{current_power:.2f}")
    with metric_cols[3]:
        st.metric("Power Factor", f"{power_factor:.3f}")
    
    st.divider()
    
    st.subheader("💰 Cost Analysis")
    cost_cols = st.columns(4)
    
    with cost_cols[0]:
        st.metric("Total Energy", f"{total_kwh:.4f} kWh")
    with cost_cols[1]:
        st.metric("Total Cost", f"৳ {total_cost:.2f}")
    with cost_cols[2]:
        if range_option == "Custom Range" and start_time and end_time:
            days = max((end_time - start_time).days, 1)
        else:
            days = time_filters.get(range_option, timedelta(days=1)).days if range_option != "Custom Range" else 1
        
        avg_daily_kwh = total_kwh / max(days, 1)
        avg_daily_cost = avg_daily_kwh * unit_cost_input
        st.metric("Avg Daily Cost", f"৳ {avg_daily_cost:.2f}")
    with cost_cols[3]:
        projected_monthly = avg_daily_cost * 30
        st.metric("Projected Monthly", f"৳ {projected_monthly:.2f}")
    
    st.divider()
    
    if not df_filtered.empty:
        st.subheader("📈 Power Consumption Over Time")
        chart_df = df_filtered.set_index('timestamp')[['power']].dropna()
        if not chart_df.empty:
            st.line_chart(chart_df, height=400)
        
        st.subheader("🔌 Voltage Over Time")
        voltage_df = df_filtered.set_index('timestamp')[['voltage']].dropna()
        if not voltage_df.empty:
            st.line_chart(voltage_df, height=400)
        
        st.subheader("⚡ Current Over Time")
        current_df = df_filtered.set_index('timestamp')[['current']].dropna()
        if not current_df.empty:
            st.line_chart(current_df, height=400)
        
        if range_option in ["Last 7 Days", "Last 30 Days"] or (range_option == "Custom Range" and days > 1):
            st.subheader("📊 Daily Summary")
            if not df_sorted.empty and 'energy_kwh_interval' in df_sorted.columns:
                daily_energy = df_sorted.groupby(df_sorted['timestamp'].dt.date)['energy_kwh_interval'].sum()
                daily_summary = pd.DataFrame({
                    'Date': daily_energy.index,
                    'Energy (kWh)': daily_energy.values,
                    'Cost (৳)': daily_energy.values * unit_cost_input
                })
                daily_summary = daily_summary.sort_values('Date', ascending=False)
                st.dataframe(daily_summary, width='stretch', hide_index=True)
        
        with st.expander("📊 Detailed Statistics"):
            stat_cols = st.columns(3)
            with stat_cols[0]:
                st.metric("Avg Power", f"{df_filtered['power'].mean():.2f} W")
                st.metric("Max Power", f"{df_filtered['power'].max():.2f} W")
                st.metric("Min Power", f"{df_filtered['power'].min():.2f} W")
            with stat_cols[1]:
                st.metric("Avg Voltage", f"{df_filtered['voltage'].mean():.2f} V")
                st.metric("Max Voltage", f"{df_filtered['voltage'].max():.2f} V")
                st.metric("Min Voltage", f"{df_filtered['voltage'].min():.2f} V")
            with stat_cols[2]:
                st.metric("Avg Current", f"{df_filtered['current'].mean():.3f} A")
                st.metric("Max Current", f"{df_filtered['current'].max():.3f} A")
                st.metric("Min Current", f"{df_filtered['current'].min():.3f} A")
        
        st.subheader("📋 Raw Data Readings")
        display_df = df_filtered[['timestamp', 'power', 'voltage', 'current']].sort_values('timestamp', ascending=False)
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(display_df.head(100), width='stretch', hide_index=True)
        
        st.divider()
        export_col1, export_col2 = st.columns([3, 1])
        with export_col1:
            st.caption(f"📥 Export data for {selected_device['name']}")
        with export_col2:
            csv = df_filtered.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV", 
                csv, 
                file_name=f"energy_{selected_device['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width='stretch'
            )
    else:
        st.info("📊 No data available yet. The system is collecting readings in the background.")
    
    if auto_refresh:
        time.sleep(60)
        st.rerun()
