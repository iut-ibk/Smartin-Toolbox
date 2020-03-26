#!/usr/bin/python3
import random

#random.seed(423423)

def get_houses_implementation(Subcatchments, number, searchFor, *dedication):
    matching = []
    for arg in dedication:
        matching += [s for s in Subcatchments if not 'not_connected' in s and float(s[3]) > .0010 and searchFor in s[0] and arg in s[0]]
    houses_implement = [s[0] for s in matching]
    houses_implement = random.sample(houses_implement, k=int(round(number*len(houses_implement))))

    return houses_implement


def get_house_parameter(Subcatchments, searchFor, column):
    line = [s for s in Subcatchments if searchFor in s[0]]
    parameter = line[0][column]

    return parameter


def get_parameters(Subcatchments, selected_houses, max_garden):
    parameters = []
    rain_barrel_total_volume = 0
    for s in selected_houses:
        house_area = float(get_house_parameter(Subcatchments, s, 3))
        garden_name = s.replace('_H_','_G_')
        garden_area = max(float(get_house_parameter(Subcatchments, str(garden_name), 3)), max_garden)
        rain_barrel_name = 'RB_{}'.format(s.split('_')[0])
        house_parameter = [s, house_area, garden_area, rain_barrel_name]
        rain_barrel_parameter = get_rain_barrel_parameters(house_area)
        rain_barrel_total_volume += rain_barrel_parameter[0]
        house_parameter.extend(rain_barrel_parameter)
        parameters.append(house_parameter)

    return parameters, rain_barrel_total_volume


def get_rain_barrel_parameters(area):
    if area < 0.0050:
        rain_barrel_paramater = [0.2,0.73,0.2739,107.5]
    if area >= 0.0050 and area < 0.0080:
        rain_barrel_paramater = [0.3,0.97,0.3092,156.0]
    if area >= 0.0080:
        rain_barrel_paramater = [0.5,0.82,0.6098,123.7]

    return rain_barrel_paramater


def write_LID_rain_barrels(val, parameters):
    if not 'LID_CONTROLS' in val:
        val['LID_CONTROLS'] = []

    if not 'LID_USAGE' in val:
        val['LID_USAGE'] = []  

    for s in parameters:
        val['LID_CONTROLS'].append([s[3], 'RB'])
        val['LID_CONTROLS'].append([s[3], 'STORAGE', str(s[5]*1000), '0.75', '0.5', '0'])
        val['LID_CONTROLS'].append([s[3], 'DRAIN', '0', '0.5', '0', '0'])
        val["LID_USAGE"].append([s[0], s[3], '1', str(s[6]), '0', '0', '100', '0'])

    return val


def implementation(val,number, max_garden, searchFor, *dedication):
    selected_houses = get_houses_implementation(val['SUBCATCHMENTS'], number, searchFor, *dedication)
    parameters, rain_barrel_total_volume = get_parameters(val['SUBCATCHMENTS'], selected_houses, max_garden)
    val = write_LID_rain_barrels(val, parameters)

    return parameters, val, rain_barrel_total_volume





