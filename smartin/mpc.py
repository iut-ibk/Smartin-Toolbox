#!/usr/bin/python3

import pandas as pd
import datetime as dt
import sys
import copy
import random
import os
import pyswmm
import subprocess

import read_write_swmm
import modify_swmm_input

def read_in_historical_rain(path):
    rain = pd.read_csv(path, sep=';',skiprows = 1, header=None, names=['Date','Rain'])
    rain['Date'] = pd.to_datetime(rain['Date'], format='%d.%m.%Y %H:%M')
    rain.set_index('Date', inplace=True)
    rain['Rain'] = rain['Rain'].div(10)

    return rain

def create_rain_series(analysetime, weatherforecast_analysetime, weatherforecast_updatesteps, rain):
    rain_30min = rain.loc[analysetime-pd.Timedelta(seconds=2100):analysetime]
    rain_30min.index = rain_30min.index + pd.Timedelta(seconds=300)
    rain_30min = rain_30min[:-1]
    rain_series_mpc = pd.Series(rain_30min.Rain, index=rain_30min.index)
    time_point = []
    for n in range(0,int(weatherforecast_updatesteps+900), 900):
        time_point.append(analysetime + pd.Timedelta(seconds=n))

    value_point = []
    for n in range(900,int(weatherforecast_updatesteps+900), 900):
        value_point.append(weatherforecast_analysetime.loc[str(n)]/15)
    value_point.append(0)    
    weather_forecast_30min = pd.Series(value_point, index=time_point)
    weather_forecast_30min = weather_forecast_30min.resample('60s').mean().interpolate(method='pad')
    weather_forecast_30min.index = weather_forecast_30min.index + pd.Timedelta(seconds=300)
    rain_series_mpc = rain_series_mpc.append(weather_forecast_30min)

    return rain_series_mpc

def create_mpc_swmm_file(original_mpc_swmm_file, analysetime, rain_series_mpc, mpc_intitial_condition_CSO):
    f = open(original_mpc_swmm_file) #read in
    success, val = read_write_swmm.swmm_input_read(f)

    if not success:
        print(val)
        sys.exit(1)

    start_analysetime = analysetime - pd.Timedelta(seconds=1800)
    end_analyse_time = analysetime + pd.Timedelta(seconds=7200)
    val = modify_swmm_input.change_swmm_dates(val, start_analysetime, end_analyse_time)
    val = modify_swmm_input.change_node_initial(val, mpc_intitial_condition_CSO)
    val = modify_swmm_input.change_rain_series(val, rain_series_mpc)

    return val

def write_LID_rain_barrels(val, actual_storage_volume, actual_area_SRB, depth_total):
    if not 'LID_CONTROLS' in val:
        val['LID_CONTROLS'] = []
    else:
        val['LID_CONTROLS'] = []

    if not 'LID_USAGE' in val:
        val['LID_USAGE'] = []
    else:
        val['LID_USAGE'] = []

    val['LID_CONTROLS'].append(['SRB_total', 'RB'])
    val['LID_CONTROLS'].append(['SRB_total', 'STORAGE', str(depth_total*1000), '0.75', '0.5', '0'])
    val['LID_CONTROLS'].append(['SRB_total', 'DRAIN', '123.7', '0.5', '0', '0'])
    val["LID_USAGE"].append(['Case_study_total', 'SRB_total', '1', str(actual_area_SRB), '0', str(actual_storage_volume/actual_area_SRB*100), str(max(actual_area_SRB/(10000*15.82)*100,1)), '0'])

    return val

def write_mpc_swmm_file(val, mpc_swmm_file):
    f = open(mpc_swmm_file,'w')
    read_write_swmm.swmm_input_write(f,val)
    f.close()

def mpc_SRBs(rainbarrels_control_states, rain_barrel_total_area, rain_barrel_total_volume, roof_total_area, analysetime, weatherforecast_analysetime, weatherforecast_updatesteps,rain,  mpc_intitial_condition_CSO, original_mpc_swmm_file, mpc_name, forecast_path):
    mpc_swmm_file = mpc_name + '.inp'

    rain_series_mpc = create_rain_series(analysetime, weatherforecast_analysetime, weatherforecast_updatesteps, rain)
    val = create_mpc_swmm_file(original_mpc_swmm_file, analysetime, rain_series_mpc, mpc_intitial_condition_CSO)

    overflow_volume_CSO = 1
    actual_area_SRB = rain_barrel_total_area
    mpc_rainbarrels_control_states = copy.deepcopy(rainbarrels_control_states)

    while overflow_volume_CSO > 0:
        actual_storage_volume = 0
        for number in mpc_rainbarrels_control_states:
            actual_storage_volume += mpc_rainbarrels_control_states[number][0]

        val = write_LID_rain_barrels(val, actual_storage_volume, actual_area_SRB, rain_barrel_total_volume/rain_barrel_total_area)
        write_mpc_swmm_file(val, mpc_swmm_file)


        ## PySWMM overwrites sim_drainagy.py file -> start PySWMM with subprocess
        #subprocess.call('swmm5.exe {} {}'.format(mpc_swmm_file, mpc_swmm_report_file))
        #os.system('python test_mpc.py')
        #subprocess.call(['python', 'mpc_simulation.py', mpc_swmm_file])#, somescript_arg1, somescript_val1,...])
        return_string = subprocess.check_output(['python', 'mpc_simulation.py', mpc_swmm_file, forecast_path, str(int(weatherforecast_updatesteps))])#, somescript_arg1, somescript_val1,...])
        overflow_volume_CSO = float(return_string.decode('utf-8').split()[5])
        
        #report_read_in = open(mpc_swmm_report_file).readlines()

        # outfall_loading = False
        # for line in report_read_in:
        #     if 'Node Inflow Summary' in line:
        #         outfall_loading = True
        #     if 'Z1' in line and outfall_loading:    
        #         overflow_volume_CSO = float(line.split()[3]) #get maximum flow (l/s)
        #         break

        if overflow_volume_CSO > 0:
            try:
                for key in random.sample(mpc_rainbarrels_control_states.keys(), 24):
                    del mpc_rainbarrels_control_states[key]
                actual_area_SRB = rain_barrel_total_area*len(mpc_rainbarrels_control_states)/len(rainbarrels_control_states)
            except:
                mpc_rainbarrels_control_states.clear()    

        if len(mpc_rainbarrels_control_states) == 0:
            break
    
    
    os.remove(mpc_name + '.rpt') #delete report file
    os.remove(mpc_name + '.out') #delete report file
    os.remove(mpc_swmm_file) #delete swmm file

    for subcatchment_name, (RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time_RainBarrel, mpc_control_group, water_age_old) in rainbarrels_control_states.items():
        if subcatchment_name in mpc_rainbarrels_control_states:
            mpc_control_group = 1
        else:
            mpc_control_group = 0   
    
        rainbarrels_control_states[subcatchment_name] = [RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time_RainBarrel, mpc_control_group, water_age_old]

    return rainbarrels_control_states