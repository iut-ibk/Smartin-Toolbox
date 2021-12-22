#!/usr/bin/python3
import pandas as pd

def change_swmm_dates(val, start, end):
    val['OPTIONS'][7][1] = start.strftime('%m/%d/%Y') #START_DATE
    val['OPTIONS'][8][1] = start.strftime('%H:%M:%S') #START_TIME
    val['OPTIONS'][9][1] = start.strftime('%m/%d/%Y') #REPORT_START_DATE
    val['OPTIONS'][10][1] = start.strftime('%H:%M:%S') #REPORT_START_TIME
    val['OPTIONS'][11][1] = end.strftime('%m/%d/%Y') #END_DATE
    val['OPTIONS'][12][1] = end.strftime('%H:%M:%S') #END_TIME

    return val


def change_raingages(val, path):
    val['RAINGAGES'][0][5] = path

    return val


def change_parameters(val, start, end, path):
    val = change_swmm_dates(val, start, end)
    val = change_raingages(val, path)

    return val


def change_rain_series(val, rain_series_mpc):
    val['TIMESERIES'] = []
    for index, value in rain_series_mpc.items():
        val["TIMESERIES"].append(['Rain', index.strftime('%m/%d/%Y'), index.strftime('%H:%M'), str(value)])

    return val


def change_node_initial(val, actual_depth_CSO):
    val['STORAGE'][0][3] = str(actual_depth_CSO)

    return val