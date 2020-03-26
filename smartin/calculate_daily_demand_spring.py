#!/usr/bin/python3

import pandas as pd

def calculate_spring(temperature, rain):
    source_filling = -1.0e-04*temperature**2 + 3.5e-03*temperature + 0.01*rain + 1.00e+00

    return source_filling  

def calculate_demand(temperature, rain):
    temperature_irrigation_reference = 10
    
    demand_factor = 10e-04*temperature**2 - 5e-03*temperature - 0.01*rain + 1.00e+00
    
    irrigation_demand = 10e-04*temperature_irrigation_reference**2 - 5e-03*temperature_irrigation_reference - 0.01*rain + 1.00e+00
    irrigation = max(demand_factor-irrigation_demand,0)
    irrigation_demand_factor = irrigation/demand_factor

    return demand_factor, irrigation_demand_factor     


