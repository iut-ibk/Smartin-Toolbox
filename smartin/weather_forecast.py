#!/usr/bin/python3

import pandas as pd
import datetime as dt

def read_in_weather_forecast(path):
    weatherforecast = pd.read_csv(path, sep=';', header=None, names=['Date','900','1800','2700','3600','4500','5400','6300','7200','8100','9000','9900','10800','11700','12600','13500','14400','15300','16200','17100','18000','18900','19800','20700','21600','22500','23400','24300','25200','26100','27000','27900','28800','29700','30600','31500','32400','33300','34200','35100','36000','36900','37800','38700','39600','40500','41400','42300','43200','44100','45000','45900','46800','47700','48600','49500','50400','51300','52200','53100','54000','54900','55800','56700','57600','58500','59400','60300','61200','62100','63000','63900','64800','65700','66600','67500','68400','69300','70200','71100','72000','72900','73800','74700','75600','76500','77400','78300','79200','80100','81000','81900','82800','83700','84600','85500','86400'])
    weatherforecast['Date'] = pd.to_datetime(weatherforecast['Date'], format='%Y-%m-%d %H:%M:%S')
    weatherforecast.set_index('Date', inplace=True)

    return weatherforecast


def read_in_swmm_file(path):
    Timestamp = []
    Rainvalue =[]
    f = open(path,'r')
    for line in f.readlines():
        Timestamp.append(dt.datetime.strptime(line[6:22], '%Y %m %d %H %M'))
        Rainvalue.append(float(line[23:]))
    rainpred_perfect = pd.Series(Rainvalue, index=Timestamp)

    return rainpred_perfect


def create_perfect_weather_forecast(path1, path2):
    real_rain = read_in_swmm_file(path1)
    dates = pd.date_range(start='2018-01-01 00:00:00', end='2018-12-31 23:45:00', freq='15T')
    data = []
    for i in range(len(dates)):
        day = [dates[i]]
        for j in range(0,86400,900):
            precipitation = round(sum(real_rain[dates[i] + pd.Timedelta(seconds=j):dates[i] + pd.Timedelta(seconds=j+899)]),2)
            day.append(precipitation)
        if i == 0:
            data = [day]
        else:
            data.append(day)

    data = pd.DataFrame(data)
    data['Date']=dates
    data.set_index('Date', inplace=True)
    data.to_csv(path2, sep=';', header=None, index=False)


