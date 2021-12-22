#!/usr/bin/python3
import pandas as pd
import datetime as dt
import json
import os
import copy

import sys
if os.name =='nt':
    sys.path = ['..\epanet-module'] + sys.path
else:
    sys.path = ['../epanet-module'] + sys.path

import epamodule as en

import read_write_swmm
import modify_epanet_input
import calculate_daily_demand_spring

def simulation_supply(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation):

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
    # background_packages = int(sys.argv[8])
    if background_packages > 1000:
        print('usage number between 0 and 1000 in hundred-steps')

    # irrigation_failure = float(sys.argv[9])
    # number_RB = int(sys.argv[10]) #define numbers of SRBs per subcatchment
    # number_simulation = int(sys.argv[11]) #define number of simulation for randomly implemented SRBs

    #input variables file
    original_epanet_file = 'wdn.inp'
    original_swmm_file = 'udn.inp'

    #created file names
    name = original_epanet_file[:-4] + '_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}'.format(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, control_groups, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)
    epanet_file = name + '.inp'
    epanet_report_file = name + '.rpt'
    epanet_bin_file = name + '.bin'
    json_file_drainage = original_swmm_file[:-4] + '_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}.json'.format(file_name, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, control_groups, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)
    json_file = name + '.json'

    #read in results from urban drainage simulation
    with open('results/{}'.format(json_file_drainage)) as myfile:
        data = json.load(myfile)
    water_demand_supply = data['water_demand_supply'][0]
    water_harvesting = data['water_harvesting'][0]

    #read in classifcation houses to junctions
    if os.name == 'nt':
        classification_path = 'water\\Classification_Houses_Junctions.csv'
    else:
        classification_path = 'water/Classification_Houses_Junctions.csv'
    classification = pd.read_csv(classification_path, sep=';', header=None, names=['PropertyID','JunctionID'])
    classification.set_index('PropertyID',inplace=True)

    #read in daily weather data
    if os.name == 'nt':
        daily_weather_path = 'weather\\weather_daily_2015.csv'
    else:
        daily_weather_path = 'weather/weather_daily_2015.csv'
    daily_weather = pd.read_csv(daily_weather_path, sep=';', header=0)
    daily_weather['Date'] = pd.to_datetime(daily_weather['Date'], format='%d.%m.%Y')
    daily_weather.set_index('Date', inplace=True)

    #set irrigation period
    start_irrigation = pd.to_datetime('0206{}'.format(year), format='%d%m%Y')
    end_irrigation = pd.to_datetime('2806{}'.format(year), format='%d%m%Y') + pd.Timedelta(hours = 23)
    #start_irrigation = pd.to_datetime('0408{}'.format(year), format='%d%m%Y')
    #end_irrigation = pd.to_datetime('0908{}'.format(year), format='%d%m%Y') + pd.Timedelta(hours = 23)
    duration = end_irrigation - start_irrigation
    hours = int(duration.days * 24 + (duration.seconds/3600))

    #set daily demand pattern
    patterns = {}
    patterns['March'] = [0.40, 0.30, 0.15, 0.10, 0.15, 0.50, 1.00, 1.50, 1.60, 1.50, 1.30, 1.20, 1.30, 1.20, 1.15, 1.20, 1.20, 1.40, 1.60, 1.50, 1.20, 1.05, 0.90, 0.60]
    patterns['April'] = [0.35, 0.20, 0.20, 0.20, 0.35, 0.70, 1.20, 1.40, 1.40, 1.30, 1.25, 1.20, 1.30, 1.20, 1.25, 1.25, 1.45, 1.70, 1.60, 1.30, 1.10, 0.95, 0.70, 0.45]
    patterns['May'] = [0.40, 0.30, 0.30, 0.30, 0.40, 0.85, 1.25, 1.35, 1.30, 1.25, 1.20, 1.15, 1.25, 1.20, 1.15, 1.25, 1.40, 1.65, 1.50, 1.30, 1.15, 0.95, 0.70, 0.45]
    patterns['June'] = [0.45, 0.45, 0.40, 0.40, 0.40, 0.80, 1.25, 1.40, 1.30, 1.25, 1.15, 1.15, 1.20, 1.20, 1.15, 1.15, 1.30, 1.60, 1.55, 1.30, 1.10, 0.90, 0.70, 0.45]
    patterns['July'] = [0.40, 0.40, 0.30, 0.30, 0.40, 0.80, 1.20, 1.45, 1.35, 1.25, 1.20, 1.25, 1.20, 1.15, 1.05, 1.15, 1.30, 1.60, 1.50, 1.30, 1.15, 1.05, 0.80, 0.45]
    patterns['August'] = [0.30, 0.20, 0.15, 0.20, 0.35, 0.70, 1.30, 1.50, 1.45, 1.40, 1.25, 1.25, 1.20, 1.15, 1.05, 1.15, 1.40, 1.70, 1.60, 1.35, 1.15, 1.00, 0.75, 0.45]
    patterns['September'] = [0.30, 0.20, 0.15, 0.15, 0.30, 0.75, 1.35, 1.55, 1.50, 1.35, 1.25, 1.20, 1.25, 1.25, 1.10, 1.15, 1.40, 1.65, 1.55, 1.30, 1.15, 1.00, 0.75, 0.40]

    #set monthly demand variation factor
    month_demand = {}
    month_demand['January'] = 0.85
    month_demand['February'] = 0.95
    month_demand['March'] = 1.00
    month_demand['April'] = 1.05
    month_demand['May'] = 1.20
    month_demand['June'] = 1.10
    month_demand['July'] = 1.05
    month_demand['August'] = 1.00
    month_demand['September'] = 1.00
    month_demand['October'] = 0.95
    month_demand['November'] = 0.95
    month_demand['December'] = 0.90

    #set monthly spring variation factor
    month_source = {}
    month_source['January'] = 0.80
    month_source['February'] = 0.75
    month_source['March'] = 0.70
    month_source['April'] = 0.90
    month_source['May'] = 1.15
    month_source['June'] = 1.20
    month_source['July'] = 1.15
    month_source['August'] = 1.15
    month_source['September'] = 1.20
    month_source['October'] = 1.10
    month_source['November'] = 1.00
    month_source['December'] = 0.90

    #add rainbarrels to epanet file and change year:
    f = open(original_epanet_file) #read in
    success, val = read_write_swmm.swmm_input_read(f)

    if not success:
        print(val)
        sys.exit(1)

    val, house_to_node = modify_epanet_input.implement_irrigation_to_node(val, water_demand_supply, classification, hours)

    f = open(epanet_file,'w')
    read_write_swmm.swmm_input_write(f,val)
    f.close()

    #set initial values
    node_with_rainbarrel = {} #for node with rainbarrels
    demand_pattern_name = 'Demand' #pattern for water demand
    water_source_name = 'spring' #node name for water source

    #open Epanet Toolkit
    en.ENopen(epanet_file, epanet_report_file) #, epanet_bin_file) #open Epanet Toolkit with files

    #initiate epanet simulation
    en.ENopenH() #open hydraulic solver
    en.ENinitH(en.EN_SAVE) #save hydraulic results to bin file
    t = start_irrigation #set start time

    #set rainbarrel patterns
    peak_demand_hour = 17

    #get rain barrel control parameters
    for key, (junction) in house_to_node.items():
        patternid_node = en.ENgetpatternindex('Demand_{}'.format(junction))
        node_id = en.ENgetnodeindex(junction)
        node_with_rainbarrel[key] = patternid_node, node_id

    #get water source index
    water_source = en.ENgetnodeindex(water_source_name) #node index
    water_source_abstraction = en.ENgetnodevalue(water_source, en.EN_BASEDEMAND) # get base demand

    #get Demand pattern index
    demand = en.ENgetpatternindex(demand_pattern_name)
    sum_demand_factor = 0
    sum_irrigation_factor = 0

    #create dictonaries for results
    number_nodes = en.ENgetcount(en.EN_NODECOUNT)
    water_age = {}

    for index in range(1, number_nodes+1):
        key = en.ENgetnodeid(index).decode('utf-8')
        water_age[key] = {}

    pressure_nodes = copy.deepcopy(water_age)
    pressure_nodes_peak = copy.deepcopy(water_age)

    while t < end_irrigation: #important that t is as long as duration to read hydraulic results file
        en.ENrunH() #run time step
        timedelta = en.ENsimtime() #get current simulation time
        #timedelta = en._current_simulation_time.value
        t = start_irrigation + pd.Timedelta(days = timedelta.days, seconds = timedelta.seconds) #combine it with real date

        if t.hour == 23 and t.minute == 0 and t.day < end_irrigation.day: #check if new day, 23 because changes will be updated next time step at 0:00
            date = t + pd.Timedelta(seconds = 3600) #to get beginning of day
            month_name = date.month_name() #get month name
            print(date)

            #get daily demand factors
            month_factor_demand = month_demand[month_name] #get monthly factor
            daily_factor_demand, daily_factor_irrigation = calculate_daily_demand_spring.calculate_demand(daily_weather.loc[date,'Tmean'], daily_weather.loc[date,'Rain']) #calculate daily demand factor based on temperature
            demand_factor = month_factor_demand * daily_factor_demand #calculate demand factor for changing pattern
            irrigation_factor = month_factor_demand * daily_factor_irrigation #calculate irrigation factor for changing pattern
            sum_demand_factor += demand_factor
            sum_irrigation_factor += irrigation_factor


            #get daily source factors
            month_factor_source = month_source[month_name] #get monthly factor
            daily_factor_source = calculate_daily_demand_spring.calculate_spring(daily_weather.loc[date,'Tmean'], daily_weather.loc[date,'Rain']) #calculate daily source factor based on temperature
            source_factor = month_factor_source * daily_factor_source #calculate month factor for changing base source

            #set daily demand pattern
            demand_pattern = patterns[t.month_name()] #get daily pattern depending on month
            daily_demand_pattern = [i * demand_factor for i in demand_pattern] #change pattern
            en.ENsetpattern(demand, daily_demand_pattern) #set pattern

            #set daily water source pouring
            daily_source_abstraction = source_factor * water_source_abstraction #change -demand
            en.ENsetnodevalue(water_source, 1, daily_source_abstraction) #set demand

            # #reset rain barrel patterns - necessary for multiple rain barrels at one node
            # for house, (pattern_rainbarrel_id) in rainbarrel_control_parameters.items():
            #     en.ENsetpattern(pattern_rainbarrel_id, rainbarrel_pattern)

            #reset demand patterns for node with rain barrel - necessary for multiple rain barrels at one node
            for key, (pattern_node_id, node_id) in node_with_rainbarrel.items():
                en.ENsetpattern(pattern_node_id, daily_demand_pattern)

            #set individual rain barrel pattern
            for key, (pattern_node_id, node_id) in node_with_rainbarrel.items():

                water_demand = water_demand_supply[key][str(date)] #get irrigation demand for rain barrels m3
                water_harvested = water_harvesting[key][str(date)] #get saved water m3

                #set filling time rain barrel
                pattern_time = 23
                #pattern_time = random.sample(filling_time_rain_barrel,1)[0] #for random filling time        
                
                #get base demand for node
                base_demand = en.ENgetnodevalue(node_id,en.EN_BASEDEMAND) 

                #get actual pattern for node with rain barrel
                actual_pattern_value_filling = en.ENgetpatternvalue(pattern_node_id, pattern_time)
                actual_pattern_value_peak = en.ENgetpatternvalue(pattern_node_id, peak_demand_hour+1)

                #set filling of rain barrel
                if control_type != 'uncontrolled':
                    water_abstraction_filling = actual_pattern_value_filling * base_demand
                    water_abstraction_filling_new = water_abstraction_filling + water_demand / (60*60) * 1000 #calculate l/s
                    water_abstraction_filling_new_pattern = water_abstraction_filling_new / base_demand
                    en.ENsetpatternvalue(pattern_node_id, pattern_time, water_abstraction_filling_new_pattern) #change pattern

                #set reduction at peak hour
                water_abstraction_peak = actual_pattern_value_peak * base_demand * 3600
                water_abstraction_peak_without = daily_demand_pattern[peak_demand_hour] * base_demand * 3600

                water_abstraction_irrigation_total = sum([i*base_demand for i in daily_demand_pattern]) * 3600 * irrigation_factor
                if control_type == 'uncontrolled':
                    water_reduction_irrigation_poss = (water_harvested) * 1000
                else:    
                    water_reduction_irrigation_poss = (water_demand + water_harvested) * 1000 #calculate l/s
                water_reduction_irrigation = min(water_reduction_irrigation_poss, 0.4*water_abstraction_irrigation_total)

                water_reduction_total = max(water_abstraction_peak - water_reduction_irrigation, water_abstraction_peak_without * 0.6) / 3600

                water_redcution_new_pattern = water_reduction_total / base_demand
                en.ENsetpatternvalue(pattern_node_id, peak_demand_hour+1, water_redcution_new_pattern) #change pattern

        #get pressure results at peak demand (17h -> reducing irrigation demand)
        if t.hour == 17:
            for index in range(1, number_nodes+1):
                key = en.ENgetnodeid(index).decode('utf-8') #get key (nodeid)
                pressure_nodes_peak[key].update({str(t): en.ENgetnodevalue(index, en.EN_PRESSURE)}) #get pressure for node

        #get pressure results at filling time rainbarrels (22-23h -> because at 23 irrigation starts)
        if t.hour == 22:
            for index in range(1, number_nodes+1):
                key = en.ENgetnodeid(index).decode('utf-8') #get key (nodeid)
                pressure_nodes[key].update({str(t): en.ENgetnodevalue(index, en.EN_PRESSURE)}) #get pressure for node

        #print(t)
        #print(en.ENgetnodevalue(105,en.EN_DEMAND))

        en.ENnextH() #next time step

    en.ENcloseH() #close hydraulic solver

    en.ENopenQ() #open quality solver

    en.ENinitQ(en.EN_SAVE) #save quality results to bin file
    t = start_irrigation #set start time

    while t < end_irrigation: #t should be lower than from hydraulic results (< instead of <=)
        en.ENrunQ() #run quality time step
        timedelta = en.ENsimtime() #get current simulation time
        t = start_irrigation + pd.Timedelta(days = timedelta.days, seconds = timedelta.seconds) #combine it with real date

        #get water age results at end of the day
        if t.hour == 23:
            for index in range(1, number_nodes+1):
                key = en.ENgetnodeid(index).decode('utf-8') #get key (nodeid)
                water_age[key].update({str(t): en.ENgetnodevalue(index, en.EN_QUALITY)}) #get pressure for node

        #print(t)
        #print(en.ENgetnodevalue(105, en.EN_QUALITY))
        en.ENstepQ() #next quality time step

    en.ENcloseQ() #close quality solver
    en.ENclose() #close epanet toolkit and delete files

    total_water_results = {}
    total_water_results['pressure'] = [pressure_nodes]
    total_water_results['pressure_peak'] = [pressure_nodes_peak]
    total_water_results['water_age'] = [water_age]

    json_write = json.dumps(total_water_results)
    f = open('results/{}'.format(json_file),"w")
    f.write(json_write)
    f.close()

    os.remove(epanet_report_file) #delete report file
    os.remove(epanet_file) #delete epanet file
