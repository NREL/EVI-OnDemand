import pandas as pd

def simulate_day(veh_soc,
                 time_absolute,
                 dcfc_ct,
                 shift_length_h,
                 veh_kwh,
                 avg_speed_mph,
                 climate_wh_mi,
                 seek_charge_kwh,
                 chg_time,
                 day_start_time,
                 dcfc_soc_high):
    
    shift_remain_time = shift_length_h
    cur_time_shift = 0
    cur_kwh = veh_soc[-1] * veh_kwh
    cum_mi = 0

    while shift_remain_time > 0:

        shift_remain_mi = shift_remain_time * avg_speed_mph
        shift_remain_kwh = shift_remain_mi * climate_wh_mi / 1000  # energy to complete remainder of shift
        avail_kwh = cur_kwh - seek_charge_kwh

        if avail_kwh > shift_remain_kwh:  # no charging needed for the remainder of the shift
            cur_kwh = cur_kwh - shift_remain_kwh
            cur_time_shift = cur_time_shift + shift_remain_time
            cum_mi = cum_mi + avg_speed_mph*shift_remain_time
            shift_remain_time = 0
            time_absolute.extend([day_start_time + cur_time_shift])
            veh_soc.extend([cur_kwh / veh_kwh])

        else:  # charging event needed
            # Elapsed time is the time before charging
            # If this is the first charge event of the shift, this is the elapsed time since the start of the shift
            # If this is not the first charge event of the shift, this is the elapsed time since the end of the previous charge
            elapsed_time = avail_kwh / (avg_speed_mph * climate_wh_mi) * 1000
            
            cum_mi = cum_mi + avg_speed_mph*elapsed_time
            time_absolute.extend([time_absolute[-1] + elapsed_time])
            veh_soc.extend([seek_charge_kwh / veh_kwh])
            cur_kwh = veh_kwh * dcfc_soc_high
            veh_soc.extend([cur_kwh / veh_kwh])
            time_absolute.extend([time_absolute[-1] + chg_time])
            cur_time_shift = cur_time_shift + elapsed_time + chg_time
            shift_remain_time = shift_length_h - cur_time_shift
            dcfc_ct = dcfc_ct + 1
            
            
    # If a charge event is occurring as a shift ends, it is assumed to continue to completion
    # This can lead to extra time until the vehicle unplugs. Accounting for that here to use later
    # when aligning the shift start
    shift_spillover = cur_time_shift - shift_length_h
    # time_absolute.extend([day_start_time + cur_time_shift])
    # veh_soc.extend([cur_kwh / veh_kwh])

    return veh_soc, time_absolute, dcfc_ct, shift_spillover, cum_mi


def simulate_night(veh_soc,
                   time_absolute,
                   home_charging,
                   shift_length_h,
                   shift_spillover,
                   veh_kwh,
                   l2_max_kw):
    elapsed_time_overnight_h = 24 - shift_length_h - shift_spillover
    end_shift_time = time_absolute[-1]
    
    end_of_shift_soc = veh_soc[-1]
    
    if home_charging == 1:
        cur_kwh = veh_kwh * veh_soc[-1]
        kwh_to_charge_l2 = veh_kwh - cur_kwh
        chg_time_to_full = kwh_to_charge_l2 / (l2_max_kw * 0.9)
        elapsed_time_overnight_h = 24 - shift_length_h - shift_spillover

        # Checking if enough time to L2 to 100%, or if the charge will be incomplete
        if chg_time_to_full <= elapsed_time_overnight_h:
            end_of_chg_soc = 1
            end_of_chg_time = time_absolute[-1] + chg_time_to_full            
            veh_soc.extend([end_of_chg_soc])
            time_absolute.extend([end_of_chg_time])
            
            
        else:
            cur_kwh = cur_kwh + elapsed_time_overnight_h * (l2_max_kw * 0.9)
            end_of_chg_soc = cur_kwh / veh_kwh
            end_of_chg_time = [time_absolute[-1] + elapsed_time_overnight_h]

        veh_soc.extend([end_of_chg_soc])
        time_absolute.extend([end_shift_time + elapsed_time_overnight_h])
        day_start_time = time_absolute[-1]
        
        end_of_night_soc = veh_soc[-1]
        l2_kwh = (end_of_night_soc - end_of_shift_soc) * veh_kwh

    else:
        day_start_soc = veh_soc[-1]
        veh_soc.extend([day_start_soc])
        time_absolute.extend([end_shift_time + elapsed_time_overnight_h])
        day_start_time = time_absolute[-1]
        l2_kwh = 0

    return veh_soc, time_absolute, day_start_time, l2_kwh


def simulate_n_days(
        veh_kwh,
        initial_soc,
        home_charging,
        shift_length_h,
        avg_speed_mph,
        sim_days,
        seek_charge_kwh,
        chg_time_h,
        l2_max_kw,
        climate_wh_mi,
        dcfc_soc_high):
    
    
    dcfc_ct = 0
    time_absolute = [0]
    veh_soc = [initial_soc]
    day_start_time = 0
    total_mi = 0
    total_l2_kwh = 0
    
    # Simulation of ay 1
    veh_soc, time_absolute, dcfc_ct, shift_spillover, shift_mi = simulate_day(veh_soc,
                                                                    time_absolute,
                                                                    dcfc_ct,
                                                                    shift_length_h,
                                                                    veh_kwh,
                                                                    avg_speed_mph,
                                                                    climate_wh_mi,
                                                                    seek_charge_kwh,
                                                                    chg_time_h,
                                                                    day_start_time,
                                                                    dcfc_soc_high)
    total_mi = total_mi + shift_mi
    
    # Simulation of remainder days
    for day in range(sim_days - 1):
        veh_soc, time_absolute, day_start_time, l2_kwh = simulate_night(veh_soc,
                                                                time_absolute,
                                                                home_charging,
                                                                shift_length_h,
                                                                shift_spillover,
                                                                veh_kwh,
                                                                l2_max_kw)

        veh_soc, time_absolute, dcfc_ct, shift_spillover, shift_mi = simulate_day(veh_soc,
                                                                        time_absolute,
                                                                        dcfc_ct,
                                                                        shift_length_h,
                                                                        veh_kwh,
                                                                        avg_speed_mph,
                                                                        climate_wh_mi,
                                                                        seek_charge_kwh,
                                                                        chg_time_h,
                                                                        day_start_time,
                                                                        dcfc_soc_high)
        total_mi = total_mi + shift_mi
        total_l2_kwh = total_l2_kwh + l2_kwh
        
    veh_soc, time_absolute, day_start_time, l2_kwh = simulate_night(veh_soc,
                                                            time_absolute,
                                                            home_charging,
                                                            shift_length_h,
                                                            shift_spillover,
                                                            veh_kwh,
                                                            l2_max_kw)
    
    total_l2_kwh = total_l2_kwh + l2_kwh
    total_dcfc_kwh = dcfc_ct * (veh_kwh*dcfc_soc_high - seek_charge_kwh)

    return veh_soc, time_absolute, dcfc_ct, total_mi, total_dcfc_kwh, total_l2_kwh