#!/usr/bin/python3

import math
import pandas as pd

def read_in_temperature(path):
    weather_measurements = pd.read_csv(path, sep=';', header=None, skiprows=1, names=['Date','degC'])
    weather_measurements['Date'] = pd.to_datetime(weather_measurements['Date'], format='%d.%m.%Y %H:%M')
    weather_measurements.set_index('Date', inplace=True)
    weather_measurements['degC'] = weather_measurements['degC'].div(10)

    Temperature_mean = weather_measurements.resample('D').mean()
    Temperature_max = weather_measurements.resample('D').max()
    Temperature_min = weather_measurements.resample('D').min()

    return Temperature_mean, Temperature_max, Temperature_min

def crop_coefficient_calculate(area1):
    crop_coefficient = (area1*1.05)

    return crop_coefficient


def EH0(ct, Temperature_max, Temperature_min, Temperature_mean):
    #determining evapotranspiration as referenz value for irrigation demand
    #G. Allan R, Pereira L, Raes D, Smith M (1998) Crop evapotranspiration-Guidelines for computing crop water requirements-FAO Irrigation and drainage paper 56 vol 56. 
    #Hargreaves, G. H. and Samani, Z. A.: Reference crop evapotranspiration from temperature
    #Haslinger, Klaus, Bartsch, AnnettCreating long-term gridded fields of reference evapotranspiration in Alpine terrain based on a recalibrated Hargreaves method

    latitude = 47.26266 #latitude Innsbruck
    latitude_radians = math.pi/180*latitude #latitude Innsbruck radians
    dayofyear = ct.timetuple().tm_yday #get day of year
    relative_distance_Earth_Sun = 1+0.033*math.cos(2*math.pi*dayofyear/365) 
    solar_declination = 0.409*math.sin(2*math.pi/365*dayofyear-1.39) 
    sunset_hour_angle = math.acos(-math.tan(latitude_radians)*math.tan(solar_declination)) 
    extraterrestrial_radiation = 24*60/math.pi*0.0820*relative_distance_Earth_Sun*(sunset_hour_angle*math.sin(latitude_radians)*math.sin(solar_declination)+math.cos(latitude_radians)*math.cos(solar_declination)*math.sin(sunset_hour_angle)) 
    water_equivalent_extraterrestrial_radiation = extraterrestrial_radiation*0.408 
    k = [0.00348,0.00300,0.00252,0.00216,0.00200,0.00192,0.00192,0.00192,0.00200,0.00208,0.00228,0.00272,0.00332] 
    evapotranspiration = k[ct.month]*(Temperature_mean+17.8)*math.sqrt(Temperature_max-Temperature_min)*water_equivalent_extraterrestrial_radiation

    crop_coefficient = crop_coefficient_calculate(1.0)
    irrigation_demand_ref = crop_coefficient*evapotranspiration

    return irrigation_demand_ref