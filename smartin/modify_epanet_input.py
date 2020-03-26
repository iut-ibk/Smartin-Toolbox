#!/usr/bin/python3

import pandas as pd

def change_duration(val, hours):
    val['TIMES'][0][1] = str('{}:00'.format(hours))

    return val

def implement_irrigation_to_node(val, data_houses_water, classification, hours):
    keys = data_houses_water.keys()
    house_to_node = {}
    for key in keys:
        house = key.split('_')[0]
        junction = classification.loc[house][0]

        if not junction in house_to_node.values():
            existing = any(junction in i for i in val['DEMANDS'])
            if existing:
                for i in range(len(val['DEMANDS'])):
                    if val['DEMANDS'][i][0] == junction and val['DEMANDS'][i][2] == 'Demand':
                        val['DEMANDS'][i][2] = 'Demand_{}'.format(junction)
            else:
                val['DEMANDS'].append([junction, str(0), 'Demand_{}'.format(junction)])            
                    
            val['PATTERNS'].append(['Demand_{}'.format(junction), str(1), str(1), str(1), str(1), str(1), str(1)])
            val['PATTERNS'].append(['Demand_{}'.format(junction), str(1), str(1), str(1), str(1), str(1), str(1)])
            val['PATTERNS'].append(['Demand_{}'.format(junction), str(1), str(1), str(1), str(1), str(1), str(1)])
            val['PATTERNS'].append(['Demand_{}'.format(junction), str(1), str(1), str(1), str(1), str(1), str(1)])       

            # val['DEMANDS'].append([junction, str(1), 'Irrigation_{}'.format(junction), 'Irrigation'])
            # val['PATTERNS'].append(['Irrigation_{}'.format(junction), str(0), str(0), str(0), str(0), str(0), str(0)])
            # val['PATTERNS'].append(['Irrigation_{}'.format(junction), str(0), str(0), str(0), str(0), str(0), str(0)])
            # val['PATTERNS'].append(['Irrigation_{}'.format(junction), str(0), str(0), str(0), str(0), str(0), str(0)])
            # val['PATTERNS'].append(['Irrigation_{}'.format(junction), str(0), str(0), str(0), str(0), str(0), str(0)])

        house_to_node.update({key:junction})
    #print(house_to_node)

    val = change_duration(val, hours)

    return val, house_to_node

