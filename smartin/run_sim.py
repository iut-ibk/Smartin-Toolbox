#!/usr/bin/python3

import sys
import os

import sim_drainage
import sim_supply

#input parameter needed
year = 2015 #chosen year for simulation
weatherforecast_kind = 'perfect' #type of weather forecast (perfect or real)
weatherforecast_accumulationtime = 14400 #weather forecast period in seconds
penetration_rate = 0.05 #penetration rate for micro storage in decimal

control_type = 'RTC_group' #type of control (uncontrolled, RTC_group, RTC_all, RTC_depth or model_prodectic_control)
error_forecast = 0.25 #error weather forecast
transmission_type = 'SF7' #spreading factor for LoRaWAN
background_packages = 700 #network load for a LoRaWAN network

irrigation_failure = 0.5 #simulate user's behaviour at uncontrolled RBs 
number_RB = 1 #number of installed RBs per property 
number_simulation = 1 #number needed for variation

swmm_file = 'udn.inp' #name of SWMM5 input file
epanet_file = 'wdn.inp' #name of EPANET2 input file
irrigation_start = (6,2) #start date irrigation (or start date simulation for short-term simulations)
irrigation_end = (6,27) #end date irrigation (or end date simulation for short-term simulations)
classification = '_R_'

print('run drainage simulation')
#swmm_file, start and end of simulation time, irrigation period and chosen land classification should be specified in sim_drainage
sim_drainage.simulation_drainage(year, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)
print('\n run water supply simulation')
#epanet_file, start and end of simulation time and irrigation period should be specified in sim_supply
sim_supply.simulation_supply(year, weatherforecast_kind, weatherforecast_accumulationtime, penetration_rate, control_type, error_forecast, transmission_type, background_packages, irrigation_failure, number_RB, number_simulation)