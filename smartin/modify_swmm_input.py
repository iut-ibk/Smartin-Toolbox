#!/usr/bin/python3
import pandas as pd

def change_swmm_dates(val, start, end):
    start_swmm = start - pd.Timedelta(days=1)
    end_swmm = end + pd.Timedelta(days=1)
    val['OPTIONS'][7][1] = start_swmm.strftime('%m/%d/%Y') #START_DATE
    val['OPTIONS'][9][1] = start_swmm.strftime('%m/%d/%Y') #REPORT_START_DATE
    val['OPTIONS'][11][1] = end_swmm.strftime('%m/%d/%Y') #END_DATE

    return val


def change_raingages(val, path):
    val['RAINGAGES'][0][5] = path

    return val


def change_parameters(val, start, end, path):
    val = change_swmm_dates(val, start, end)
    val = change_raingages(val, path)

    return val