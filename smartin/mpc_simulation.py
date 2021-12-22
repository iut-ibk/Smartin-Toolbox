#!/usr/bin/python3

import sys
import pandas as pd
import pyswmm

import weather_forecast

mpc_swmm_file = sys.argv[1]
forecast_path = sys.argv[2]
weatherforecast_accumulationtime = int(sys.argv[3])*2

open_RB = True
rain_on = storm_on = False

Rain_Barrel_DrainageCoefficient = 123.7

weatherforecast = weather_forecast.read_in_weather_forecast(forecast_path)

with pyswmm.Simulation(mpc_swmm_file) as mpc_sim:
    system_stats = pyswmm.SystemStats(mpc_sim) #get system stats (rainfall)

    RainBarrel_control = pyswmm.LidControls(mpc_sim)["SRB_total"]
    RainBarrel = pyswmm.LidGroups(mpc_sim)["Case_study_total"][0] #get single LID units of a single building

    RainBarrel_volume = RainBarrel_control.storage.thickness/1000 * RainBarrel.unit_area

    Subarea = pyswmm.Subcatchments(mpc_sim)['Case_study_total']
    Roof_area = Subarea.area*Subarea.percent_impervious

    start_time = mpc_sim.start_time
    analysetime = start_time + pd.Timedelta(seconds=1800)

    for step_mpc in mpc_sim:
        ct = mpc_sim.current_time # current SWMM simulation time

        RainBarrel_storage = RainBarrel.storage.depth/1000*RainBarrel.unit_area #[m3] get actual storage volume
        RainBarrel_available_storage = (RainBarrel_volume - RainBarrel_storage) #[m3] calclate available storage volume

        if open_RB and ct > analysetime:
            open_RB = False
            RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient

        if not open_RB and ct > analysetime:
            weatherforecast_analysetime = weatherforecast.loc[analysetime,'900':str(weatherforecast_accumulationtime)] #get weatherforecast specific analysetime
            weatherforecast_sum = sum(weatherforecast_analysetime) #get rainsum of choosen analysetime
            future_rain_sum = weatherforecast_sum*0.95 #calculate effictive rainfall [mm]
            previous_rain_sum = system_stats.runoff_stats['rainfall'] #get previous rainsum (rainsum is accumulated over simulation time)

            if future_rain_sum > 0:
                future_outflow_house = future_rain_sum/1000*Roof_area*10000 #calculate future inflow SRB
                if future_outflow_house > RainBarrel_available_storage and future_outflow_house < RainBarrel_volume: #if predicted rainfall is higher than storage volume but less than rainbarrel volume
                    RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient
                    rain_on = True #only open valve at analysetime
                if future_outflow_house > RainBarrel_volume:
                    max_intensity_lead_time =  weatherforecast_analysetime.idxmax()
                    closing_time_RainBarrel = weatherforecast_analysetime.name + pd.Timedelta(seconds=int(max_intensity_lead_time)) - pd.Timedelta(seconds=900)
                    storm_on = True #only open valve at analysetime
                    RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient

            analysetime += pd.Timedelta(seconds=weatherforecast_accumulationtime/2)        

        if rain_on: #control rules for rainfall lower than rain barrel volume
            future_rain_storage = (max(future_rain_sum - (system_stats.runoff_stats['rainfall']-previous_rain_sum),0))/1000*Roof_area*10000 #calcute actuell rain storage volume
            if future_rain_storage < RainBarrel_available_storage: #if enough volume is available
                rain_on = False #stop emptying
                RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0
        if storm_on: #control rules for rainfall higher than rain barrel volume
            if ct >= closing_time_RainBarrel:
                storm_on = False #close valve
                RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0    




 
    overflow_volume_CSO = pyswmm.Nodes(mpc_sim)['CSO'].cumulative_inflow

print('overflow volume: {}'.format(overflow_volume_CSO))
