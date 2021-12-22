#!/usr/bin/python3

import pandas as pd
import numpy as np

def rate_of_collision(transmission_quality, packets_per_minute_total):
    packages_per_minute = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    Transmission_type = ['perfect', 'average', 'SF7', 'SF8', 'SF9', 'SF10', 'SF11', 'SF12']
    SF7 = [0.010, 0.015, 0.015, 0.018, 0.030, 0.037, 0.063, 0.070, 0.074, 0.074, 0.081]
    SF8 = [0.010, 0.015, 0.037, 0.055, 0.066, 0.077, 0.092, 0.100, 0.118, 0.122, 0.144]
    SF9 = [0.010, 0.030, 0.074, 0.096, 0.125, 0.133, 0.162, 0.210, 0.214, 0.232, 0.269]
    SF10 = [0.010, 0.059, 0.133, 0.185, 0.218, 0.269, 0.339, 0.343, 0.376, 0.432, 0.469]
    SF11 = [0.010, 0.170, 0.207, 0.284, 0.391, 0.494, 0.520, 0.572, 0.657, 0.675, 0.716]
    SF12 = [0.010, 0.199, 0.376, 0.502, 0.579, 0.664, 0.734, 0.790, 0.819, 0.871, 0.897]
    average = [0.010, 0.074, 0.140, 0.191, 0.232, 0.283, 0.320, 0.342, 0.368, 0.397, 0.419]
    perfect = [0] * 11

    collison_dataframe = pd.DataFrame([perfect, average, SF7, SF8, SF9, SF10, SF11, SF12], columns=packages_per_minute, index=Transmission_type)

    failure_transmission_quality = collison_dataframe.loc[transmission_quality,:]
    failure_transmission_quality.loc[packets_per_minute_total] = np.nan
    failure_transmission_quality = failure_transmission_quality.sort_index().interpolate(method='index')

    failure = failure_transmission_quality.loc[packets_per_minute_total]

    return failure

def calculate_failure(transmission_quality, packets_per_minute, number_SRB):
    packets_per_minute_total = packets_per_minute + number_SRB*3/10
    failure = rate_of_collision(transmission_quality, packets_per_minute_total)

    return failure
