import pandas as pd
import random
from ondemand_vehsim import simulate_n_days
from ondemand_utils import calc_chg_time
import os
from datetime import datetime
import yaml
import time
from tqdm import tqdm, trange
import warnings
import sys


def retrieve_cbsa_inputs(global_inputs,
                         cbsa_mph,
                         cbsa_vmt,
                         cbsa_whmi_adjustments,
                         cbsa_hc_access,
                         cur_cbsa_id):
    
    avg_speed_mph = cbsa_mph[cbsa_mph.geoid == cur_cbsa_id].median_mph.values[0]
    pop_cbsa_vmt = cbsa_vmt[cbsa_vmt.cbsa_id == cur_cbsa_id].cbsa_dvmt.values[0]
    cbsa_tnc_vmt = pop_cbsa_vmt * global_inputs['tnc_share'] * (1 + global_inputs['deadhead_perc'])
    cbsa_hc_access = int(
        100 * cbsa_hc_access[cbsa_hc_access.cbsa_id == cur_cbsa_id][global_inputs['hc_scenario']].values[0])
    cur_cbsa_whmi = cbsa_whmi_adjustments[cbsa_whmi_adjustments.geoid==cur_cbsa_id].penalty_factor.values[0] * global_inputs['base_wh_mi']
        
    cbsa_inputs = {
        'avg_speed_mph': avg_speed_mph,
        'cbsa_tnc_vmt': cbsa_tnc_vmt,
        'cbsa_hc_access': cbsa_hc_access,
        'cbsa_whmi': cur_cbsa_whmi}

    return cbsa_inputs


def define_variable_frequencies(cbsa_inputs):
    cbsa_hc_access = cbsa_inputs['cbsa_hc_access']
    home_charging_access_dict = {0: 100 - cbsa_hc_access,
                                 1: cbsa_hc_access}  # percent, integer

    return home_charging_access_dict


def build_metric_distribution(frequency_dictionary):

    metric_categories = frequency_dictionary.keys()
    metric_dist = []
    for metric_category in metric_categories:
        cur_freq = frequency_dictionary[metric_category]
        metric_dist.extend([metric_category] * cur_freq)

    return metric_dist


def explode_veh_specific_variables(home_charging_access_dict,
                                   global_inputs):
    home_chg_dist = build_metric_distribution(home_charging_access_dict)
    shift_dist = build_metric_distribution(global_inputs['shift_length_dist'])
    kwh_dist = build_metric_distribution(global_inputs['veh_kwh_dict'])

    return home_chg_dist, shift_dist, kwh_dist


def scale_values_per_100(variable_dict):
    
    val_sum = 0
    for cur_key in variable_dict.keys():
        val_sum = val_sum + variable_dict[cur_key]
    
    scaled_dict = {}
    for cur_key in variable_dict.keys():
        scaled_dict[cur_key] = variable_dict[cur_key] / val_sum * 100
    
    return scaled_dict


def simulate_driver_permutations(home_charging_access_dict,
                                 global_inputs,
                                 cbsa_inputs):
    home_chg_list = []
    shift_h_list = []
    veh_kwh_list = []
    comb_weight = []
    comb_dcfc_per_day = []
    comb_miles = []
    comb_seek_charge_kwh = []
    comb_l2_max_kw = []
    comb_sim_days = []
    comb_plug_in_time = []
    comb_plug_occupied_time = []
    comb_dcfc_kwh_per_day = []
    comb_l2_kwh_per_day = []
    
    vehicle_shift_length_dict = scale_values_per_100(global_inputs['shift_length_dist'])
    vehicle_kwh_dict = scale_values_per_100(global_inputs['veh_kwh_dict'])

    for cur_home_chg in home_charging_access_dict.keys():
        for cur_shift_time_h in vehicle_shift_length_dict.keys():
            for cur_veh_kwh in vehicle_kwh_dict.keys():
                seek_charge_kwh = global_inputs['soc_low'] * cur_veh_kwh
                
                permutation_weight = (int(home_charging_access_dict[cur_home_chg] *
                                          vehicle_shift_length_dict[cur_shift_time_h] *
                                          vehicle_kwh_dict[cur_veh_kwh] / (100 * 100 * 100) * 100))
                
                if global_inputs['charge_taper'] == 1:
                    dcfc_chg_time_h, chg_time_series, chg_power_series, chg_soc_series = calc_chg_time(cur_veh_kwh,
                                                                                                   global_inputs[
                                                                                                       'veh_max_kw'],
                                                                                                   global_inputs[
                                                                                                       'dcfc_max_kw'],
                                                                                                   global_inputs[
                                                                                                       'soc_low'],
                                                                                                   global_inputs[
                                                                                                       'soc_high'])
                else:
                    dcfc_chg_time_h = ((global_inputs['soc_high'] - global_inputs['soc_low']) * cur_veh_kwh) / global_inputs['dcfc_max_kw']
                
                total_recharge_time = dcfc_chg_time_h + global_inputs['plug_in_mins'] / 60.0 # Adding plug-in penalty
                
                veh_soc, time_absolute, dcfc_ct, total_mi, total_dcfc_kwh, total_l2_kwh = simulate_n_days(
                    cur_veh_kwh,
                    global_inputs['initial_soc'],
                    cur_home_chg,
                    cur_shift_time_h,
                    cbsa_inputs['avg_speed_mph'],
                    global_inputs['sim_days'],
                    seek_charge_kwh,
                    total_recharge_time,
                    global_inputs['l2_max_kw'],
                    cbsa_inputs['cbsa_whmi'],
                    global_inputs['soc_high'])

                permutation_dcfc_per_day = dcfc_ct / global_inputs['sim_days']
                permutation_miles_per_day = total_mi / global_inputs['sim_days']
                permutation_dcfc_kwh_per_day = total_dcfc_kwh / global_inputs['sim_days']
                permutation_l2_kwh_per_day = total_l2_kwh / global_inputs['sim_days']
                permutuation_l2_max_kw = global_inputs['l2_max_kw']
                
                home_chg_list.extend([cur_home_chg])
                shift_h_list.extend([cur_shift_time_h])
                veh_kwh_list.extend([cur_veh_kwh])
                comb_weight.extend([permutation_weight])
                comb_dcfc_per_day.extend([permutation_dcfc_per_day])
                comb_miles.extend([permutation_miles_per_day])
                comb_seek_charge_kwh.extend([seek_charge_kwh])
                comb_l2_max_kw.extend([permutuation_l2_max_kw])
                comb_sim_days.extend([global_inputs['sim_days']])
                comb_plug_in_time.extend([global_inputs['plug_in_mins']])
                comb_plug_occupied_time.extend([global_inputs['plug_in_mins']/60.0 + dcfc_chg_time_h])
                comb_dcfc_kwh_per_day.extend([permutation_dcfc_kwh_per_day])
                comb_l2_kwh_per_day.extend([permutation_l2_kwh_per_day])

    cbsa_permutation_results = pd.DataFrame({'home_chg': home_chg_list,
                                             'shift_h': shift_h_list,
                                             'veh_kwh': veh_kwh_list,
                                             'weight': comb_weight,
                                             'dcfc_per_day': comb_dcfc_per_day,
                                             'miles_per_day': comb_miles,
                                             'chg_time_per_dcfc': dcfc_chg_time_h,
                                             'seek_charge_kwh': comb_seek_charge_kwh,
                                             'l2_max_kw': comb_l2_max_kw,
                                             'sim_days': comb_sim_days,
                                             'plug_in_mins': comb_plug_in_time,
                                             'plug_occupied_time': comb_plug_occupied_time,
                                             'dcfc_kwh_per_day': comb_dcfc_kwh_per_day,
                                             'l2_kwh_per_day': comb_l2_kwh_per_day})

    cbsa_permutation_results['key'] = cbsa_permutation_results.home_chg.astype(str) + "_" + \
                                      cbsa_permutation_results.shift_h.astype(str) + "_" + \
                                      cbsa_permutation_results.veh_kwh.astype(str)

    return cbsa_permutation_results, total_recharge_time


def explode_driver_permutations(cbsa_permutations):

    permutation_list = []
    home_chg_list = []
    mile_list = []
    dcfc_per_day_list = []
    time_per_dcfc_list = []
    tot_time_per_dcfc_list = []
    tot_dcfc_kwh_list = []
    tot_l2_kwh_list = []
    
    for ix, cur_row in cbsa_permutations.iterrows():
        permutation_list.extend([cur_row.key]*cur_row.weight)
        home_chg_list.extend([cur_row.home_chg]*cur_row.weight)
        mile_list.extend([cur_row.miles_per_day]*cur_row.weight)
        dcfc_per_day_list.extend([cur_row.dcfc_per_day]*cur_row.weight)
        time_per_dcfc_list.extend([cur_row.chg_time_per_dcfc]*cur_row.weight)
        tot_time_per_dcfc_list.extend([cur_row.plug_occupied_time]*cur_row.weight)
        tot_dcfc_kwh_list.extend([cur_row.dcfc_kwh_per_day]*cur_row.weight)
        tot_l2_kwh_list.extend([cur_row.l2_kwh_per_day]*cur_row.weight)
        
    return permutation_list, home_chg_list, mile_list, dcfc_per_day_list, time_per_dcfc_list, tot_time_per_dcfc_list, tot_dcfc_kwh_list, tot_l2_kwh_list


def sample_populations_to_reach_vmt(permutation_list,
                      home_chg_list,
                      mile_list,
                      dcfc_per_day_list,
                      time_per_dcfc,
                      tot_time_per_dcfc_list,
                      cbsa_tnc_vmt,
                      tot_dcfc_kwh_list,
                      tot_l2_kwh_list):

    fleet_miles = 0
    fleet_dcfc_h = 0
    ix = 0
    sampled_permutations = []
    sampled_miles = []
    sampled_dcfc_ct = [] # Number of DCFC events per day
    sampled_dcfc_h = [] # Hours of charging per DCFC event
    sampled_tot_plug_time_h = [] # Hours of plug use per DCFC event
    sampled_tot_dcfc_kwh_w_hc = []
    sampled_tot_dcfc_kwh_wo_hc = []
    sampled_tot_l2_kwh = []
    
    while fleet_miles < cbsa_tnc_vmt:

        cur_sample_ix = random.randint(0, len(permutation_list)-1)
        cur_permutation = permutation_list[cur_sample_ix]
        cur_miles = mile_list[cur_sample_ix]
        cur_dcfc_ct = dcfc_per_day_list[cur_sample_ix]
        cur_dcfc_h = time_per_dcfc[cur_sample_ix] * cur_dcfc_ct
        cur_tot_plug_time_h = tot_time_per_dcfc_list[cur_sample_ix] * cur_dcfc_ct
        cur_l2_kwh_per_day = tot_l2_kwh_list[cur_sample_ix]
        
        if home_chg_list[cur_sample_ix]==1:
            cur_dcfc_kwh_per_day_w_hc = tot_dcfc_kwh_list[cur_sample_ix]
            cur_dcfc_kwh_per_day_wo_hc = 0
        else:
            cur_dcfc_kwh_per_day_w_hc = 0
            cur_dcfc_kwh_per_day_wo_hc = tot_dcfc_kwh_list[cur_sample_ix]
        
        sampled_permutations.extend([cur_permutation])
        sampled_miles.extend([cur_miles])
        sampled_dcfc_ct.extend([cur_dcfc_ct])
        sampled_dcfc_h.extend([cur_dcfc_h])
        sampled_tot_plug_time_h.extend([cur_tot_plug_time_h])
        sampled_tot_dcfc_kwh_w_hc.extend([cur_dcfc_kwh_per_day_w_hc])
        sampled_tot_dcfc_kwh_wo_hc.extend([cur_dcfc_kwh_per_day_wo_hc])
        sampled_tot_l2_kwh.extend([cur_l2_kwh_per_day])
        
        fleet_miles = fleet_miles + cur_miles

    return len(sampled_permutations), sum(sampled_dcfc_ct), sum(sampled_dcfc_h), sum(sampled_tot_plug_time_h), sum(sampled_tot_dcfc_kwh_w_hc), sum(sampled_tot_dcfc_kwh_wo_hc), sum(sampled_tot_l2_kwh)


def import_scenario_vars(scenario):

    with open(scenario, 'r') as stream:
        input_dict = yaml.safe_load(stream)

    return input_dict


def write_scenario_trace(output_dir, scenario):
    with open(output_dir + '/' + '%s_sim_inputs.yaml' % scenario, 'w') as outfile:
        yaml.dump(global_inputs, outfile, default_flow_style=False)

    return


def directory_handling(global_inputs, scenario):
    now = datetime.now()
    dt_string = now.strftime("%m_%d_%Y_%H_%M")

    print(global_inputs['output_dir'])
    # Parent output folder, useful for novel sensitivities
    if not os.path.exists(global_inputs['output_dir']):
        os.makedirs(global_inputs['output_dir'])

    output_dir = global_inputs['output_dir'] +  scenario + '--' + dt_string
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(output_dir)   
    
    return output_dir


def import_cbsa_inputs():
    cbsa_vmt = pd.read_csv('../data/vmt_by_cbsa.csv')
    cbsa_mph = pd.read_csv('../data/median_mph_by_cbsa.csv')
    cbsa_whmi_adjustments = pd.read_csv('../data/whmi_by_cbsa.csv')
    cbsa_hc_access = pd.read_csv('../data/overnight_chg_access_by_cbsa.csv')

    cbsa_ids = list(cbsa_vmt.cbsa_id.unique())

    return cbsa_vmt, cbsa_mph, cbsa_whmi_adjustments, cbsa_hc_access, cbsa_ids


def print_header(scenario, global_inputs):

    header_text = """
\nEVI-OnDemand: Infrastructure Projections for All-Electric Ridehailing Fleets\n\n
Variables:"""

    print(header_text)

    for cur_key in global_inputs.keys():

        print("\t%s: %s" % (cur_key, global_inputs[cur_key]))

    print("\nBeginning simulation...\n")

    return


if __name__ == "__main__":

    warnings.filterwarnings("ignore")
    random.seed(666)
    scenario = sys.argv[1]

    global_inputs = import_scenario_vars(scenario)
    global_inputs['veh_max_kw'] = global_inputs['dcfc_max_kw']
    
    scenario = global_inputs['scenario_name']
    
    output_dir = directory_handling(global_inputs, scenario)

    write_scenario_trace(output_dir, scenario)

    print_header(scenario, global_inputs)

    cbsa_vmt, cbsa_mph, cbsa_whmi_adjustments, cbsa_hc_access, cbsa_ids =  import_cbsa_inputs()

    permutation_results = pd.DataFrame()
    tnc_population_results = pd.DataFrame()

    with trange(len(cbsa_ids)) as t:

        ix = 0
        for cur_t, cur_cbsa_id in zip(t, cbsa_ids):

            t.set_description('CBSA %i' % cur_t)

            cbsa_inputs = retrieve_cbsa_inputs(global_inputs,
                                               cbsa_mph,
                                               cbsa_vmt,
                                               cbsa_whmi_adjustments,
                                               cbsa_hc_access,
                                               cur_cbsa_id)

            home_charging_access_dict = define_variable_frequencies(cbsa_inputs)
            
            cbsa_permutation_results, total_recharge_time = simulate_driver_permutations(home_charging_access_dict,
                                                                    global_inputs,
                                                                    cbsa_inputs)

            cbsa_permutation_results['cbsa_id'] = cur_cbsa_id
            cbsa_permutation_results['cbsa_whmi'] = cbsa_inputs['cbsa_whmi']
            cbsa_permutation_results['avg_speed_mph'] = cbsa_inputs['avg_speed_mph']
            
            # Fehr and Peers report gave VMT for 6 CBSAs, using those here if inputs allow for it, "overriding" globally assumed 1%
            if global_inputs['vmt_override_flag'] == 1:
                fehr_and_peers_values = {31080: 1.5/100.0, # la
                                    42660: 1.9/100.0, # seattle
                                    41860: 2.7/100.0, # sf
                                    47900: 1.9/100.0, # DC
                                    14460: 1.9/100.0, # boston
                                    16980: 2.1/100.0} # CHICAGO
                
                if cur_cbsa_id in fehr_and_peers_values.keys():
                    miles_to_electrify = cbsa_inputs['cbsa_tnc_vmt'] / global_inputs['tnc_share'] * fehr_and_peers_values[cur_cbsa_id]

                else:
                    miles_to_electrify = cbsa_inputs['cbsa_tnc_vmt']
            
            else:
                miles_to_electrify = cbsa_inputs['cbsa_tnc_vmt']

            permutation_list, home_chg_list, mile_list, dcfc_per_day, time_per_dcfc, tot_time_per_dcfc_list, tot_dcfc_kwh_list, tot_l2_kwh_list = explode_driver_permutations(cbsa_permutation_results)

            num_vehs, num_dcfc_events, tot_dcfc_hours, tot_plug_time_h, tot_dcfc_kwh_w_hc, tot_dcfc_kwh_wo_hc, tot_l2_kwh = sample_populations_to_reach_vmt(permutation_list, home_chg_list,
                                                                        mile_list,
                                                                        dcfc_per_day,
                                                                        time_per_dcfc,
                                                                        tot_time_per_dcfc_list,
                                                                        miles_to_electrify,
                                                                        tot_dcfc_kwh_list,
                                                                        tot_l2_kwh_list)

            permutation_results = permutation_results.append(cbsa_permutation_results)

            cur_tnc_population_results = pd.DataFrame({
                'cbsa_id': [cur_cbsa_id],
                'num_vehs': [num_vehs],
                'num_dcfc_events': [num_dcfc_events],
                'cbsa_dcfc_hours': [tot_dcfc_hours],
                'cbsa_dcfc_plug_time': [tot_plug_time_h],
                'cbsa_tnc_vmt': [miles_to_electrify],
                'cbsa_hc_access': [cbsa_inputs['cbsa_hc_access']],
                'cbsa_avg_speed': [cbsa_inputs['avg_speed_mph']],
                'cbsa_whmi': [cbsa_inputs['cbsa_whmi']],
                'cbsa_dcfc_kwh_w_hc': [tot_dcfc_kwh_w_hc],
                'cbsa_dcfc_kwh_wo_hc': [tot_dcfc_kwh_wo_hc],
                'cbsa_l2_kwh': [tot_l2_kwh]})

            tnc_population_results = tnc_population_results.append(cur_tnc_population_results)
            ix = ix + 1

    hours_per_charger = 24 * global_inputs['utilization_perc']
    tnc_population_results['plugs'] = tnc_population_results.cbsa_dcfc_hours / hours_per_charger

    
    permutation_results.to_csv('%s/permutation_results.csv' % output_dir, index=False)
    tnc_population_results.to_csv('%s/population_results.csv' % output_dir, index=False)

    print('\n\nSimulation finished!')
    print('Number of plugs: %s' % int(tnc_population_results.plugs.sum()))
    print('Number of vehicles: %s' % int(tnc_population_results.num_vehs.sum()))
    print('Vehicles per plug: %s' % round(int(tnc_population_results.num_vehs.sum()) /
          int(tnc_population_results.plugs.sum()), 2))