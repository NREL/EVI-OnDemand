import yaml
import pandas as pd


def calc_chg_time(veh_kwh,
                  veh_max_kw,
                  dcfc_max_kw,
                  soc_low,
                  soc_high):
    veh_power_curve = pd.read_csv('/home/mmoniot/github/EVI-OnDemand/data/normalized_power_curve.csv')
    veh_power_curve['chg_acceptance'] = veh_power_curve.rel_power * veh_max_kw

    cur_soc = soc_low
    cur_kwh = cur_soc * veh_kwh
    timestep_duration = 60  # seconds
    running_time = [0]
    running_soc = [cur_soc]
    running_power = [0]

    while cur_soc <= soc_high:
        # Linear interpolation
        nearest_soc_low = veh_power_curve[veh_power_curve.soc <= cur_soc].soc.iloc[-1]
        nearest_soc_high = veh_power_curve[veh_power_curve.soc > cur_soc].soc.iloc[0]
        interp_perc = (cur_soc - nearest_soc_low) / (nearest_soc_high - nearest_soc_low)

        nearest_power_low = veh_power_curve[veh_power_curve.soc <= cur_soc].chg_acceptance.iloc[-1]
        nearest_power_high = veh_power_curve[veh_power_curve.soc >= cur_soc].chg_acceptance.iloc[0]
        veh_acceptance_power = nearest_power_low + interp_perc * (nearest_power_high - nearest_power_low)

        # Charging may be limited by the battery or the charger. Finding bottleneck
        cur_timestep_power = min(veh_acceptance_power, dcfc_max_kw)

        cur_timestep_kwh = cur_timestep_power * timestep_duration / 3600
        cur_kwh = cur_kwh + cur_timestep_kwh
        cur_soc = cur_kwh / veh_kwh

        running_time.extend([running_time[-1] + timestep_duration])
        running_soc.extend([cur_soc])
        running_power.extend([cur_timestep_power])

    dcfc_chg_time_h = running_time[-1] / 3600

    return dcfc_chg_time_h, running_time, running_power, running_soc
