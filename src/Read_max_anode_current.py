# Code by:      Anuradha Gunawardhana
# Date:         2024.07.11
# Description:  Use the recorded open and closed PMT readings to calculate the max anode current

import numpy as np
import uproot
import os
import sys
import logging
import argparse

anode_current_max = 10 #(Units:μA) The program will return the error code 2 if the max anode current passed this threshold
anode_current_min = 8

ADC_rate = 14705883         # Samples/sec
debug = False

def main():               
    parser = argparse.ArgumentParser(prog='MOLLER Experiment PMT Linearity Calculation',
                                     description='Calculate the PMT linearity for the MOLLER experiment. \nCode by: Anuradha Gunawardhana')
    
    parser.add_argument("dir", help=",<dir> .root file directory for single run ")
    args = parser.parse_args()
    data_path = os.path.normpath(args.dir) # remove trailing slashes
    #----------------------File count Test--------------------------#
    expected_file_list = ['1.root','12.root']
    if debug: print(f"[Test begin]: Checking the root files - \"{data_path}\"")
    
    dir_files = []
    for path in os.listdir(data_path):
        if os.path.isfile(os.path.join(data_path, path)):
            dir_files.append(path)
    # if debug: print(f"Actual files = {dir_files}")
    
    check =  all(file in dir_files for file in expected_file_list)

    if check: 
        if debug: print(" ✅ [Test Passed]: All the necessary files are in order")
        fileTestPassed =True
    else: 
        logging.info(" 🚨 [Test Failed]: File list does not match with the filter count")
    #---------------------Data files length test--------------------#
    with open(f"{data_path}/CMDataSettings.txt", 'r') as CMData_settings:
        lines = CMData_settings.readlines()
        prescale = int(lines[4].split(" ")[1])                  # Get the prescale value used for down-sampling the data while recording
        record_length = float(lines[5].split(" ")[1])
    dataArr_limit = int((ADC_rate/prescale)*record_length*0.9)  # Trim the data equally at 90%
    if debug: print(f'prescale={prescale}, record_length={record_length:.2f}, data_limit:{dataArr_limit}')

    if debug: print(f"[Test begin]: Preprocessing \"{data_path}\"")
    length_passed = np.empty([len(expected_file_list)])
    data = np.empty([len(expected_file_list),dataArr_limit])
    diode_data = np.empty([len(expected_file_list),dataArr_limit])
    if debug: print(f"Data size= {data.shape}")

    data = np.empty((2))
    for f,rootFile in enumerate(expected_file_list):
        file = uproot.open(f'{data_path}/{rootFile}')
        tree = file['DataTree']
        branches = tree.arrays()  
        data[f] = np.mean(branches['ch1_data'].to_numpy())   # Photomultiplier(PMT) data

    with open(f"{data_path}/Experiment_data.txt", 'r') as Exp_data:
        expLines = Exp_data.readlines()
        for i in expLines:
            id = i.split('=')[0]
            value = i.split('=')[1].strip()
            if id == "Preamp_gain(Ohm)" : preamp = value
            elif id == "PMT_Serial" : serial = value

    if (preamp == "1M"): gain = 1000
    else: gain = int(preamp[0:-1])

    A_max = ((data[0] - data[1])/gain)*1000 # pedestal corrected by subtracting the dark filter mean
    print(f'Max Anode Current = {A_max:.2f}μA')
    if A_max > anode_current_max:
        logging.warning(f"🟡 {serial}: High anode current detected: max(I_anode)={A_max:.2f} μA is higher than {anode_current_max} μA")
        sys.exit(2)
    elif A_max < anode_current_min:
        logging.warning(f"🟡 {serial}: Low anode current detected max(I_anode)={A_max:.2f} μA is lower than {anode_current_min} μA")
        sys.exit(3)
    else:
        logging.info("Analysis successful")
        sys.exit(0) 

if __name__ == "__main__":
    main()
