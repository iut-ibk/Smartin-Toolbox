#!/usr/bin/python3
import pandas as pd
import datetime as dt
import json
import os
import random
import sys

import pyswmm

import calculate_irrigation_demand
import implement_LIDs
import modify_swmm_input
import mpc
import read_write_swmm
import transmission_probabilty
import weather_forecast

def simulation_drainage(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation):

    startTime = dt.datetime.now()

    #set simulation time
    start_date = pd.to_datetime('02.06.2015 00:00:00', format='%d.%m.%Y %H:%M:%S')
    end_date = pd.to_datetime('28.06.2015 23:59:59', format='%d.%m.%Y %H:%M:%S')
    if start_date.year != end_date.year:
        print('start and end date has to be in the same year')
        sys.exit(1)
    elif start_date > end_date:
        print('start date has to be lower than end date ')
        sys.exit(1)

    year = start_date.year #get year of simulation for rain simulation
    
    #control input plausibility
    # file_name = sys.argv[1] #define file name for different rain events
    # weatherforecast_kind = sys.argv[2] #perfect or real
    # weatherforecast_accumulationtime = int(sys.argv[3]) #period of weather forecast
    # penetration_rate = float(sys.argv[4]) #penetration rate of SRBs
    # control_type = sys.argv[5] #control type

    control_groups = 1
    control_depth = 2.75
    groups = smart = model_predictive_control = False

    if control_type == 'uncontrolled':
        RTC = False
    elif control_type == 'RTC_all':
        RTC = smart = True
    elif control_type == 'RTC_group':
        RTC = smart = groups = True
        control_groups = 4
    elif control_type == 'RTC_depth':
        RTC = smart = True
        control_depth = 1.0
    elif control_type == 'model_prodectic_control':
        RTC = model_predictive_control = True
    else:
        print('usage control type: "uncontrolled", "RTC_all", "RTC_group", "RTC_depth" or "model_prodectic_control"')
        sys.exit(1)

    # error_forecast = float(sys.argv[6])
    if error_forecast < -1 or error_forecast > 1:
        print('usage error forecast: reduction and increase between -1 and 1 for no error')
        sys.exit(1)

    # transmission_type = sys.argv[7]
    if transmission_type == 'perfect' or transmission_type == 'average' or transmission_type == 'SF7' or transmission_type == 'SF8' or transmission_type == 'SF9' or transmission_type == 'SF10' or transmission_type == 'SF11' or transmission_type == 'SF12':
        pass
    else:
        print('usage transmission type: perfect (=without package losses) or average, SF7, SF8, SF9, SF10, SF11 or SF12 for LoRaWAN transmission')
        sys.exit(1)
    #  background_packages = int(sys.argv[8])
    if background_packages > 1000:
        print('usage number between 0 and 1000 in hundred-steps')

    # irrigation_failure = float(sys.argv[9])

    # number_RB = int(sys.argv[10]) #define numbers of SRBs per subcatchment
    # number_simulation = int(sys.argv[11]) #define number of simulation for randomly implemented SRBs

    #set input variable irrigation
    irrigation_start = (3,21) #start summerhalf year
    irrigation_end = (9,23) #end summerhalf year
    irrigation_hour = (23,00) #irrigation time h:m

    #input variable runoff coefficient
    runoff_coefficient=0.95

    #input variable swmm file
    original_swmm_file = 'udn.inp'
    original_mpc_swmm_file = 'udn_simplified.inp'

    #created variables
    analysetime = start_date
    weatherforecast_updatesteps = weatherforecast_accumulationtime/2/control_groups

    #created file names
    name = original_swmm_file[:-4] + '_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}'.format(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, control_groups, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)
    mpc_name = original_mpc_swmm_file[:-4] + '_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}'.format(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, control_groups, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)
    swmm_file = name + '.inp'
    json_file = name + '.json'

    #create swmm input file
    f = open(original_swmm_file) #read in
    success, val = read_write_swmm.swmm_input_read(f)

    if not success:
        print(val)
        sys.exit(1)

    houses_implementation_RBs, val, rain_barrel_total_volume, rain_barrel_total_area, roof_total_area = implement_LIDs.implementation(val, penetration_rate, control_groups, number_RB, 25, '_H_','_R_') #implementation of SRBs
    val = modify_swmm_input.change_parameters(val, start_date, end_date, 'rain{}.dat'.format(year))

    #print((houses_implementation_RBs))

    f = open(swmm_file,'w')
    read_write_swmm.swmm_input_write(f,val)
    f.close()

    #set initial values - needed for simulation
    newday = analysetime
    time_timeseries = analysetime
    irrigation_time = pd.to_datetime('{}.{}.{} {}:{}:00'.format(start_date.day, start_date.month, start_date.year, irrigation_hour[0], irrigation_hour[1]), format='%d.%m.%Y %H:%M:%S')
    ct_old = analysetime - pd.Timedelta(seconds = 60)
    ref_control_group = 1
    mpc_ref_control_group = 1
    mpc_initial_analysetime = analysetime + pd.Timedelta(seconds=weatherforecast_updatesteps) - pd.Timedelta(seconds=1800)
    mpc_intitial_condition_CSO = 0

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

    #read in rain
    if os.name == 'nt':
        rain_path = 'weather\\rain_1min_{}.csv'.format(year)
    else:
        rain_path = 'weather/rain_1min_{}.csv'.format(year)
    rain = mpc.read_in_historical_rain(rain_path)

    #calculate probabilty of transmission success
    transmission_failure_propability = transmission_probabilty.calculate_failure(transmission_type, background_packages, number_rain_barrels)

    with pyswmm.Simulation(swmm_file) as sim:
        system_stats = pyswmm.SystemStats(sim) #get system stats (rainfall)
        Nodes = pyswmm.Nodes(sim)

        for n in range(number_rain_barrels):
            houses_lid_parameters[houses_implementation_RBs[n][0]] = houses_implementation_RBs[n][1:], pyswmm.LidGroups(sim)[houses_implementation_RBs[n][0]][0], pyswmm.LidControls(sim)[houses_implementation_RBs[n][4]]
            rainbarrels_control_states[houses_implementation_RBs[n][0]] = [0, 0, False, False, False, analysetime, 0, 0]
            rainbarrels_results[houses_implementation_RBs[n][0]] = [0, 0, 0, 0, 0]
            water_demand_supply[houses_implementation_RBs[n][0]] = {}
            water_harvesting[houses_implementation_RBs[n][0]] = {}

        for step in sim:
            ct = sim.current_time # current SWMM simulation time

            future_rainfall = start_irrigation = transmission = False
            #print(ct)

            #daily control rules
            if ct >= newday:
                irrigation = irrigation_start <= (newday.month,newday.day) <= irrigation_end  #check if actual day is in irrigation period
                newday_timestamp = newday #necessary for function irrigation_need and to find daily aggregated values in Temperature
                rain_day_beginning = system_stats.runoff_stats['rainfall'] #get rainfall amount at beginning of the day [mm]
                newday += pd.Timedelta(days = 1)
                print(ct)

            #Real time control - get rain prediction for specific analysetime
            if RTC and ct >= analysetime:
                weatherforecast_analysetime = weatherforecast.loc[analysetime,'900':str(weatherforecast_accumulationtime)] #get weatherforecast specific analysetime
                weatherforecast_analysetime_corrected = weatherforecast_analysetime.copy(deep=True)
                weatherforecast_analysetime_corrected = weatherforecast_analysetime_corrected * (1 + error_forecast) 

                weatherforecast_sum = sum(weatherforecast_analysetime_corrected) #get rainsum of choosen analysetime

                if analysetime + pd.Timedelta(seconds=weatherforecast_accumulationtime) >= irrigation_time:
                    estimated_crop_evapotranspiration_ref = calculate_irrigation_demand.EH0(newday_timestamp, Temperature_max.loc[newday_timestamp,'degC'], Temperature_min.loc[newday_timestamp,'degC'], Temperature_mean.loc[newday_timestamp,'degC']) #get necessary irrigation demand based on daily temperature
                    daily_rain_to_analysetime = system_stats.runoff_stats['rainfall'] - rain_day_beginning #get daily rainfall
                    weatherforecast_rain_until_irrigation_time = weatherforecast_analysetime_corrected.loc['900':str(max(pd.Timedelta(irrigation_time - analysetime).seconds,900))]
                    weatherforecast_sum_until_irrigation_time = sum(weatherforecast_rain_until_irrigation_time)
                    estimation_irrigation_demand = max(estimated_crop_evapotranspiration_ref-daily_rain_to_analysetime-weatherforecast_sum_until_irrigation_time,0)

                if weatherforecast_analysetime_corrected.values.reshape(-1, 4).sum(1).max() > 0.25:
                    future_rainfall = True
                    future_rain_sum = weatherforecast_sum*runoff_coefficient #calculate effictive rainfall [mm]
                    previous_rain_sum = system_stats.runoff_stats['rainfall'] #get previous rainsum (rainsum is accumulated over simulation time)

                    #change group of opened SRBs
                    if groups:
                        if ref_control_group == control_groups:
                            ref_control_group = 1
                        else:
                            ref_control_group += 1

                    #check control depth for opening SRBs
                    actual_depth_CSO = pyswmm.Nodes(sim)['CSO_building'].depth
                    if actual_depth_CSO <= control_depth:
                        depth_control = True
                    else:
                        depth_control = False

                    #mpc
                    if model_predictive_control:
                        rainbarrels_control_states = mpc.mpc_SRBs(rainbarrels_control_states, rain_barrel_total_area, rain_barrel_total_volume, roof_total_area,  analysetime, weatherforecast_analysetime_corrected, weatherforecast_updatesteps, rain, mpc_intitial_condition_CSO, original_mpc_swmm_file, mpc_name, forecast_path)

                analysetime += pd.Timedelta(seconds=weatherforecast_updatesteps) #set new analysetime

            if ct > mpc_initial_analysetime:
                mpc_intitial_condition_CSO = pyswmm.Nodes(sim)['CSO_building'].depth
                mpc_initial_analysetime += pd.Timedelta(seconds=weatherforecast_updatesteps) #set new analysetime

            #calculate at irrigation demand at end of day - EN16941-1 (2018) EN 16941-1 On-site non-potable water systems.
            if ct > irrigation_time and irrigation: #set end of day for irrigation
                crop_evapotranspiration_ref = calculate_irrigation_demand.EH0(newday_timestamp, Temperature_max.loc[newday_timestamp,'degC'], Temperature_min.loc[newday_timestamp,'degC'], Temperature_mean.loc[newday_timestamp,'degC']) #get necessary irrigation demand based on daily temperature
                rain_day = system_stats.runoff_stats['rainfall'] - rain_day_beginning #get daily rainfall
                absolut_evapotranspiration = max(crop_evapotranspiration_ref-rain_day,0) /1000  #calculate irrigation demand [m3/m2]
                start_irrigation = True
                irrigation_time += pd.Timedelta(days=1)

            for subcatchment_name, ((House_area, green_area, control_group, RB_name, RainBarrel_volume, RainBarrel_hight, RainBarrel_area, Rain_Barrel_DrainageCoefficient), RainBarrel, RainBarrel_control) in houses_lid_parameters.items():
                RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time_RainBarrel, mpc_control_group, water_age_old = rainbarrels_control_states[subcatchment_name]
                irrigation_demand_overall, water_saving, water_detention, number_operations, water_age = rainbarrels_results[subcatchment_name]

                RainBarrel_storage = RainBarrel.storage.depth/1000*RainBarrel_area #[m3] get actual storage volume
                RainBarrel_available_storage = (RainBarrel_volume - RainBarrel_storage) #[m3] calclate available storage volume

                #control rules for RTC_all, RTC_group and RTC_depth -> open rainbarrel
                if future_rainfall: #estimate future inflow to house required for all control strategies
                    if analysetime - pd.Timedelta(seconds=weatherforecast_updatesteps) + pd.Timedelta(seconds=weatherforecast_accumulationtime) >= irrigation_time and estimation_irrigation_demand > 0:
                        estimated_irrigation = estimation_irrigation_demand/1000 * green_area
                        future_outflow_house_total = future_rain_sum/1000*House_area*10000 #calculate future inflow SRB
                        future_outflow_house_until_irrigation_time = (weatherforecast_sum_until_irrigation_time*runoff_coefficient)/1000*House_area*10000
                        future_outflow_house_after_irrigation_time = future_outflow_house_total - future_outflow_house_until_irrigation_time
                        if future_outflow_house_total > RainBarrel_volume:
                            if future_outflow_house_until_irrigation_time > RainBarrel_volume:
                                future_outflow_house = future_outflow_house_until_irrigation_time
                            else:
                                future_outflow_house = max(RainBarrel_volume - estimated_irrigation, 0)
                        else:
                            future_outflow_house = max(future_outflow_house_total - estimated_irrigation, 0)
                    else:
                        future_outflow_house = future_rain_sum/1000*House_area*10000 #calculate future inflow SRB
                        max_intensity_lead_time =  weatherforecast_analysetime_corrected.idxmax() #get time of max intensity

                    #implement collison probability
                    collison = random.uniform(0,1)
                    # print(collison)
                    if collison > transmission_failure_propability:
                        transmission = True
                    else:
                        transmission = False

                if smart and transmission: #if smart and future rainfall -> only at analysetime
                    if control_group == ref_control_group and depth_control: #check SRB's control group and control depth allowing opening of SRB
                        if future_outflow_house > RainBarrel_available_storage and future_outflow_house < RainBarrel_volume: #if predicted rainfall is higher than storage volume but less than rainbarrel volume
                            if RainBarrel_storage > 0.001: #open SRB only when storage is (partly) filled
                                RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient
                                rain_on = True #only open valve at analysetime
                                number_operations += 1 #count opening operations
                        if future_outflow_house > RainBarrel_volume:
                            closing_time_RainBarrel = weatherforecast_analysetime_corrected.name + pd.Timedelta(seconds=int(max_intensity_lead_time)) - pd.Timedelta(seconds=900)

                            if not storm_on and closing_time_RainBarrel > ct: #or not rain_sum_to_max_intensity == 0:
                                storm_on = True #only open valve at analysetime
                                number_operations += 1 #count opening operations
                                RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient

                #control rules for mpc -> open rainbarrel (currently same as smart)
                if model_predictive_control and transmission: #if mpc and future rainfall -> only at analysetime
                    if mpc_control_group == mpc_ref_control_group: #check SRB's mpc control group
                        if future_outflow_house > RainBarrel_available_storage and future_outflow_house < RainBarrel_volume: #if predicted rainfall is higher than storage volume but less than rainbarrel volume
                            if RainBarrel_storage > 0.001: #open SRB only when storage is (partly) filled
                                RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient
                                rain_on = True #only open valve at analysetime
                                number_operations += 1 #count opening operations
                        if future_outflow_house > RainBarrel_volume:
                            closing_time_RainBarrel = weatherforecast_analysetime_corrected.name + pd.Timedelta(seconds=int(max_intensity_lead_time)) - pd.Timedelta(seconds=900)

                            if not storm_on and closing_time_RainBarrel > ct: #or not rain_sum_to_max_intensity == 0:
                                storm_on = True #only open valve at analysetime
                                number_operations += 1 #count opening operations
                                RainBarrel_control.drain.coefficient = Rain_Barrel_DrainageCoefficient #open valve = set drainage coefficient

                #irrigation time -> open rainbarrel
                if start_irrigation:
                    #irrigation behaviour:
                    if not RTC:
                        irrigation_people = random.uniform(0,1)
                        if irrigation_people > irrigation_failure:
                            irrigation_behaviour = True
                        else:
                            irrigation_behaviour = False
                    else:
                        irrigation_behaviour = True
                    irrigation_demand = absolut_evapotranspiration * green_area
                    if irrigation_behaviour:
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
                        RainBarrel.drain_node = -1 #set outflow node
                if not irrigation_on and rain_on: #control rules for rainfall lower than rain barrel volume
                    future_rain_storage = (max(future_rain_sum - (system_stats.runoff_stats['rainfall']-previous_rain_sum),0))/1000*House_area*10000 #calcute actuell rain storage volume
                    if future_rain_storage < RainBarrel_available_storage: #if enough volume is available
                        rain_on = False #stop emptying
                        RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0
                if not irrigation_on and storm_on: #control rules for rainfall higher than rain barrel volume
                    if ct >= closing_time_RainBarrel:
                        storm_on = False #close valve
                        RainBarrel_control.drain.coefficient = 0 #close valve = set drainage coefficient = 0

                #set new list values
                RainBarrel_storage_old = RainBarrel_storage

                rainbarrels_control_states[subcatchment_name] = [RainBarrel_storage_old, RainBarrel_irrigation_goal, irrigation_on, rain_on, storm_on, closing_time_RainBarrel, mpc_control_group, water_age_actual]
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
        outflow_mixed_overflow = pyswmm.Nodes(sim)['CSO'].cumulative_inflow
        mass_mixed_overflow = pyswmm.Nodes(sim)['CSO'].outfall_statistics['pollutant_loading']
        dry_weather_flow = system_stats.routing_stats['dry_weather_inflow']
        outflow_wastewater_treatmentplant = pyswmm.Nodes(sim)['treatment_plant'].cumulative_inflow

        system_results = [number_nodes, flooding_volume, outflow_irrigation, outflow_mixed_overflow, mass_mixed_overflow, dry_weather_flow, outflow_wastewater_treatmentplant]

    total_results = {}
    total_results['volume'] = [rain_barrel_total_volume]
    total_results['rainbarrels_results'] = [rainbarrels_results]
    total_results['water_demand_supply'] =  [water_demand_supply]
    total_results['water_harvesting'] =  [water_harvesting]
    total_results['system_results'] = [system_results]
    total_results['flooding_node'] = [flooding_nodes]


    json_write = json.dumps(total_results)
    f = open('results/{}'.format(json_file),"w")
    f.write(json_write)
    f.close()

    print(dt.datetime.now()-startTime)

    os.remove(name + '.rpt') #delete report file
    os.remove(name + '.out') #delete report file
    os.remove(swmm_file) #delete swmm file

