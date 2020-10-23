#!/usr/bin/python3
import pandas as pd
import datetime as dt
import json
import os

# import sys
# if os.name =='nt':
#     sys.path = ['.\\pyswmm'] + sys.path
# else:
#     sys.path = ['./pyswmm'] + sys.path

import pyswmm

import implement_LIDs
import calculate_irrigation_demand
import modify_swmm_input
import read_write_swmm
import weather_forecast

def simulation_drainage(year, weatherforecast_kind, weatherforecast_accumulationtime, weatherforecast_updatesteps, penetration_rate, control_type, number_simulation, original_swmm_file, irrigation_start, irrigation_end, classification):
    startTime = dt.datetime.now()

    if control_type == 'smart':
        smart = True
    elif control_type == 'uncontrolled':
        smart = False
    else:
        print('usage control type: "uncontrolled" or "smart"')
        sys.exit(1)

    #input variable runoff coefficient
    runoff_coefficient=0.95

    #input variable max garden area 
    max_garden = 25

    #created variables
    analysetime = pd.to_datetime('{}.{}.{}'.format(irrigation_start[1], irrigation_start[0], year), format='%d.%m.%Y')
    endtime = pd.to_datetime('{}.{}.{}'.format(irrigation_end[1], irrigation_end[0], year), format='%d.%m.%Y')

    #created file names
    name = original_swmm_file[:-4] + '_{}_{}_{}_{}_{}_{}'.format(year, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, number_simulation)
    swmm_file = name + '.inp'
    json_file = name + '.json'

    #create swmm input file
    f = open(original_swmm_file) #read in
    success, val = read_write_swmm.swmm_input_read(f)

    if not success:
        print(val)
        sys.exit(1)

    houses_implementation_RBs, val, rain_barrel_total_volume = implement_LIDs.implementation(val, penetration_rate, max_garden, '_H_', classification) #implementation of SRBs
    val = modify_swmm_input.change_parameters(val, analysetime, endtime, 'rain{}.dat'.format(year))

    #print((houses_implementation_RBs))

    f = open(swmm_file,'w')
    read_write_swmm.swmm_input_write(f,val)
    f.close()

    #set initial values - needed for simulation
    newday = analysetime
    irrigation_time = analysetime + pd.Timedelta(seconds=84600)
    ct_old = analysetime - pd.Timedelta(seconds = 60)

    irrigation = False

    number_rain_barrels = len(houses_implementation_RBs)
    houses_lid_parameters = {}
    rainbarrels_control_states = {}

    # set final results
    rainbarrels_results = {}
    water_demand_supply = {}
    water_harvesting = {}
    system_results = {}

    #read in temperature
    if os.name == 'nt':
        temperature_path = 'weather\\temperature_{}.csv'.format(year)
    else:
        temperature_path = 'weather/temperature_{}.csv'.format(year)
    Temperature_mean, Temperature_max, Temperature_min = calculate_irrigation_demand.read_in_temperature(temperature_path)

    #read in weather forecast
    if os.name == 'nt':
        forecast_path = 'weather\\rain_forecast_{}_{}.csv'.format(year, weatherforecast_kind)
    else:
        forecast_path = 'weather/rain_forecast_{}_{}.csv'.format(year, weatherforecast_kind)
    weatherforecast = weather_forecast.read_in_weather_forecast(forecast_path)

    with pyswmm.Simulation(swmm_file) as sim:
        system_stats = pyswmm.SystemStats(sim) #get system stats (rainfall)

        for n in range(number_rain_barrels):
            houses_lid_parameters[houses_implementation_RBs[n][0]] = houses_implementation_RBs[n][1:], pyswmm.LidGroups(sim)[houses_implementation_RBs[n][0]][0], pyswmm.LidControls(sim)[houses_implementation_RBs[n][3]]
            rainbarrels_control_states[houses_implementation_RBs[n][0]] = [0, 0, False, False, False, 0, 0]
            rainbarrels_results[houses_implementation_RBs[n][0]] = [0, 0, 0, 0, 0]
            water_demand_supply[houses_implementation_RBs[n][0]] = {}
            water_harvesting[houses_implementation_RBs[n][0]] = {}

        for step in sim:
            ct = sim.current_time # current SWMM simulation time

            future_rainfall = False
            start_irrigation = False
            #print(ct)

            #daily control rules
            if ct >= newday:
                irrigation = irrigation_start <= (newday.month,newday.day) <= irrigation_end  #check if actual day is in irrigation period
                newday_timestamp = newday #necessary for function irrigation_need and to find daily aggregated values in Temperature
                rain_day_beginning = system_stats.runoff_stats['rainfall'] #get rainfall amount at beginning of the day [mm]
                newday += pd.Timedelta(days = 1)
                #print(ct)

            #smart - get rain prediction for specific analysetime
            if smart and ct >= analysetime:
                weatherforecast_analysetime = weatherforecast.loc[analysetime,'900':str(weatherforecast_accumulationtime)] #get weatherforecast specific analysetime
                weatherforecast_sum = sum(weatherforecast_analysetime) #get rainsum of choosen analysetime
                if weatherforecast_sum > 0:
                    future_rainfall = True
                    future_rain_sum = weatherforecast_sum*runoff_coefficient #calculate effictive rainfall [mm]
                    previous_rain_sum = system_stats.runoff_stats['rainfall'] #get previous rainsum (rainsum is accumulated over simulation time)

                analysetime += pd.Timedelta(seconds=weatherforecast_updatesteps) #set new analysetime

            #calculate at irrigation demand at end of day - EN16941-1 (2018) EN 16941-1 On-site non-potable water systems.
            if ct > irrigation_time and irrigation: #set end of day for irrigation
                crop_evapotranspiration_ref = calculate_irrigation_demand.EH0(newday_timestamp, Temperature_max.loc[newday_timestamp,'degC'], Temperature_min.loc[newday_timestamp,'degC'], Temperature_mean.loc[newday_timestamp,'degC']) #get necessary irrigation demand based on daily temperature
                rain_day = system_stats.runoff_stats['rainfall'] - rain_day_beginning #get daily rainfall
                absolut_evapotranspiration = max(crop_evapotranspiration_ref-rain_day,0) /1000  #calculate irrigation demand [m3/m2]
                start_irrigation = True
                irrigation_time += pd.Timedelta(days=1)

            for subcatchment_name, ((House_area, green_area, RB_name, RainBarrel_volume, RainBarrel_hight, RainBarrel_area, Rain_Barrel_DrainageCoefficient), RainBarrel, RainBarrel_control) in houses_lid_parameters.items():
                RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time, water_age_old = rainbarrels_control_states[subcatchment_name]
                irrigation_demand_overall, water_saving, water_detention, number_operations, water_age = rainbarrels_results[subcatchment_name]

                RainBarrel_storage = RainBarrel.storage.depth/1000*RainBarrel_area #[m3] get actual storage volume
                RainBarrel_available_storage = (RainBarrel_volume - RainBarrel_storage) #[m3] calclate available storage volume

                #smart and future_rainfall -> open rainbarrel
                if smart and future_rainfall:
                    future_outflow_house = future_rain_sum/1000*House_area*10000
                    if future_outflow_house > RainBarrel_available_storage and future_outflow_house < RainBarrel_volume and RainBarrel_storage > 0.001: #if predicted rainfall is higher than storage volume but less than rainbarrel volume
                        RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient
                        rain_on = True #only open valve at analysetime
                        number_operations += 1 #count opening operations
                    if future_outflow_house > RainBarrel_volume:
                        max_intensity_lead_time =  weatherforecast_analysetime.idxmax() #get max intensity time
                        temp_time = max_intensity_lead_time
                        closing_time_RainBarrel = weatherforecast_analysetime.name + pd.Timedelta(seconds=int(temp_time)) - pd.Timedelta(seconds=900)

                        if RainBarrel_storage > 0.001 and not storm_on: #or not rain_sum_to_max_intensity == 0:
                            storm_on = True #only open valve at analysetime
                            number_operations += 1 #count opening operations
                            RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient

                #irrigation time -> open rainbarrel
                if start_irrigation:
                    irrigation_demand = absolut_evapotranspiration * green_area
                    if irrigation_demand < RainBarrel_storage and irrigation_demand > 0: #calcluate usable water for irrigation inside storage layer
                        water_usable = irrigation_demand
                        water_needed = 0
                        irrigation_on = True #start irrigation
                    elif irrigation_demand > RainBarrel_storage and irrigation_demand > 0 and RainBarrel_storage > 0.001:
                        water_usable = RainBarrel_storage
                        water_needed = irrigation_demand - water_usable
                        irrigation_on = True #start irrigation
                    else:
                        water_usable = 0
                        water_needed = irrigation_demand

                    if irrigation_on:    #start irrigation
                        RainBarrel.drain_node = 'Irrigation' #set outflow node
                        RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set draiange coefficient
                        RainBarrel_irrigation_goal = RainBarrel.water_balance.drain_flow + water_usable / RainBarrel_area * 1000 #calculate final outflow irrigation (RainBarrel_size is because of mm)
                        water_saving += water_usable #calculate total water savings
                        number_operations += 1 #count opening operations

                    irrigation_demand_overall += irrigation_demand #calculate total irrigation demand
                    water_demand_supply[subcatchment_name].update({str(newday_timestamp): water_needed}) #get water demand for water supply
                    water_harvesting[subcatchment_name].update({str(newday_timestamp): water_usable}) #get amout of water harvesting

                #calculate detention_volume during irrigation period
                if irrigation: #only when irrigation time (21. March to 23. September)
                    water_detention += max(RainBarrel_storage-RainBarrel_storage_old,0) #calculate total detention volume

                #calculate water_age
                if RainBarrel_storage > 0.001: #only if storage > 1l
                    time_delta = pd.Timedelta(ct - ct_old).seconds / 3600 #get time difference between routing time steps
                    water_age_actual = ((water_age_old + time_delta) * (RainBarrel_storage_old - RainBarrel.new_drain_flow*time_delta*3600/1000)) / RainBarrel_storage #calculate actual water age
                else:
                    water_age_actual = 0
                water_age = max(water_age, water_age_actual) #set max water age

                #control rules every SWMM Step
                if irrigation_on: #control rules for irrigation
                    if RainBarrel.water_balance.drain_flow >= RainBarrel_irrigation_goal or RainBarrel_storage < 0.001: #either irrigation demand or minimum water level reached
                        irrigation_on = False #stop irrigation process
                        RainBarrel_control.drain.coefficient = 0 #close valve - set drainage coefficient = 0
                        RainBarrel.drain_node = '-1' #set outflow node
                if not irrigation_on and rain_on: #control rules for rainfall lower than rain barrel volume
                    future_rain_storage = (max(future_rain_sum - (system_stats.runoff_stats['rainfall']-previous_rain_sum),0))/1000*House_area*10000 #calcute actuell rain storage volume
                    if future_rain_storage < RainBarrel_available_storage: #if enough volume is available
                        rain_on = False #stop emptying
                        RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0
                if not irrigation_on and storm_on:
                    if ct >= closing_time_RainBarrel:
                        storm_on = False #close valve
                        RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0      

                #set new list values
                RainBarrel_storage_old = RainBarrel_storage

                rainbarrels_control_states[subcatchment_name] = [RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time, water_age_actual]
                rainbarrels_results[subcatchment_name] = [irrigation_demand_overall, water_saving, water_detention, number_operations, water_age]

            #set old control step
            ct_old = ct

        #system states
        #flooding
        flooding_volume = 0
        number_nodes = 0
        flooding_nodes = {}
        for node in pyswmm.Nodes(sim):
            flooding_volume += node.statistics['flooding_volume']
            number_nodes +=1
            flooding_nodes.update({node.nodeid: node.statistics['flooding_volume']})

        #outflows
        outflow_irrigation = pyswmm.Nodes(sim)['Irrigation'].cumulative_inflow
        outflow_mixed_overflox = pyswmm.Nodes(sim)['CSO'].cumulative_inflow
        outflow_wastewater_treatmentplant = pyswmm.Nodes(sim)['treatment_plant'].cumulative_inflow

        system_results = [number_nodes, flooding_volume, outflow_irrigation, outflow_mixed_overflox, outflow_wastewater_treatmentplant]

    total_results = {}
    total_results['volume'] = [rain_barrel_total_volume]
    total_results['rainbarrels_results'] = [rainbarrels_results]
    total_results['water_demand_supply'] =  [water_demand_supply]
    total_results['water_harvesting'] =  [water_harvesting]
    total_results['system_results'] = [system_results]
    total_results['flooding_node'] = [flooding_nodes]


    results_json = json.dumps(total_results)
    f = open('results/{}'.format(json_file),"w")
    f.write(results_json)
    f.close()

    #print(dt.datetime.now()-startTime)

    os.remove(name + '.rpt') #delete report file
    os.remove(name + '.out') #delete out file
    os.remove(swmm_file) #delete swmm file
