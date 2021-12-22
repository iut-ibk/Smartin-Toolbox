#!/usr/bin/python3
import random

random.seed(423420)

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


def get_parameters(Subcatchments, selected_houses, max_garden, control_groups, number_RB):
    parameters = []
    rain_barrel_total_volume = 0
    rain_barrel_total_area = 0
    roof_total_area = 0
    for s in selected_houses:
        house_area = float(get_house_parameter(Subcatchments, s, 3))
        roof_total_area += house_area
        garden_name = s.replace('_H_','_G_')
        garden_area = max(float(get_house_parameter(Subcatchments, str(garden_name), 3)), max_garden)
        rain_barrel_name = 'RB_{}'.format(s.split('_')[0])
        control_group = random.randint(1,control_groups)
        house_parameter = [s, house_area, garden_area, control_group, rain_barrel_name]
        rain_barrel_parameter = get_rain_barrel_parameters(house_area, number_RB)
        rain_barrel_total_volume += rain_barrel_parameter[0]
        rain_barrel_total_area += rain_barrel_parameter[2]
        house_parameter.extend(rain_barrel_parameter)
        parameters.append(house_parameter)

    return parameters, rain_barrel_total_volume, rain_barrel_total_area, roof_total_area


def get_rain_barrel_parameters(area, number_RB):
    if area < 0.0050:
        rain_barrel_paramater = [0.2*number_RB,0.73,0.2739*number_RB,107.5]
    if area >= 0.0050 and area < 0.0080:
        rain_barrel_paramater = [0.3*number_RB,0.97,0.3092*number_RB,156.0]
    if area >= 0.0080:
        rain_barrel_paramater = [0.5*number_RB,0.82,0.6098*number_RB,123.7]

    return rain_barrel_paramater


def write_LID_rain_barrels(val, parameters):
    if not 'LID_CONTROLS' in val:
        val['LID_CONTROLS'] = []

    if not 'LID_USAGE' in val:
        val['LID_USAGE'] = []  

    rain_barrel_beginning_storage_volume = 0
    for s in parameters:
        rain_barrel_filling = round(random.uniform(0.5, 1.0),2)*100
        val['LID_CONTROLS'].append([s[4], 'RB'])
        val['LID_CONTROLS'].append([s[4], 'STORAGE', str(s[6]*1000), '0.75', '0.5', '0'])
        val['LID_CONTROLS'].append([s[4], 'DRAIN', '0', '0.5', '0', '0'])
        val["LID_USAGE"].append([s[0], s[4], '1', str(s[7]), '0', str(rain_barrel_filling), '100', '0'])
        rain_barrel_beginning_storage_volume += rain_barrel_filling/100*s[6]*s[7]
    return val


def implementation(val, number, control_groups, number_RB, max_garden, searchFor, *dedication):
    selected_houses = get_houses_implementation(val['SUBCATCHMENTS'], number, searchFor, *dedication)
    parameters, rain_barrel_total_volume, rain_barrel_total_area, roof_total_area = get_parameters(val['SUBCATCHMENTS'], selected_houses, max_garden, control_groups, number_RB)
    val = write_LID_rain_barrels(val, parameters)

    return parameters, val, rain_barrel_total_volume, rain_barrel_total_area, roof_total_area





