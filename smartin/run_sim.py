#!/usr/bin/python3

import sys
import os

import sim_drainage
import sim_supply

#input parameter needed
year = 2015 #chosen year for simulation
weatherforecast = 'perfect' #type of weather forecast (perfect or real)
accumulation = 3600 #weather forecast period in seconds
update = accumulation/2 #update time step weather forecast in seconds
if update > accumulation:
    sys.exit('update larger than accumulation - no overlap')

penetration = 0.05 #penetration rate for micro storage in decimal
control = 'smart' #type of control (uncontrolled or smart)
variation = 1 #number needed for variation

swmm_file = 'ds.inp' #name of SWMM5 input file
epanet_file = 'ws.inp' #name of EPANET2 input file
irrigation_start = (6,2) #start date irrigation (or start date simulation for short-term simulations)
irrigation_end = (6,27) #end date irrigation (or end date simulation for short-term simulations)
classification = '_R_'

print('run drainage simulation')
sim_drainage.simulation_drainage(year, weatherforecast, accumulation, update, penetration, control, variation, swmm_file, irrigation_start, irrigation_end, classification)
print('\n run water supply simulation')
sim_supply.simulation_supply(year, weatherforecast, accumulation, penetration, control, variation, epanet_file, swmm_file, irrigation_start, irrigation_end)