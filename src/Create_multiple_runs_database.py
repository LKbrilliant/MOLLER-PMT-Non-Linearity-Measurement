import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import sys
import Multiple_runs_analysis
import pprint
from pathlib import Path
import time

gain = 200 #kilo-ohms
debug = False
def progressbar(it, prefix="[Computing]", size=50, out=sys.stdout):
    count = len(it)
    start_time = time.time()  # Record the start time
    def show(j):
        elapsed_time = time.time() - start_time
        progress = j / count
        if j > 0:
            avg_time_per_item = elapsed_time / j
            eta = avg_time_per_item * (count - j)
        else:
            eta = 0  # To avoid division by zero at the start
        
        eta_str = time.strftime('%H:%M', time.gmtime(eta))
        x = int(size * progress)
        print(f"{prefix}[{'■' * x}{'.' * (size - x)}] "
              f"{progress * 100:.0f}% "
              f"ETA:{eta_str}m", end='\r', file=out, flush=True)

    show(0)
    for i, item in enumerate(it):
        yield item
        show(i + 1)
    print("\n[Done]", flush=True, file=out)

def get_subdirectories(directory, depth):
    if depth < 0:
        raise ValueError("depth must be non-negative.")
    result = []
    for root, dirs, files in os.walk(directory):
        current_depth = root.count(os.sep) - directory.count(os.sep)
        if current_depth == depth:
            result.extend(os.path.join(root, d) for d in dirs)
    return result

def main():
    parser = argparse.ArgumentParser(prog='MOLLER Experiment: Linearity uncertainty test',
                                     description='Compare linearity data of one PMT. \nCode by: Anuradha Gunawardhana')
    
    parser.add_argument("-d", "--dir", required=True, help="Multiple runs data directory")

    args = parser.parse_args()
    mypath = os.path.normpath(args.dir) # remove trailing slashes
    
    all_dirs = get_subdirectories(mypath,1)
    if len(all_dirs)==0: 
        print("[ERROR]: No data directories found")
        return
    if debug: print('All selected Dirs: ', all_dirs)
    
    pmt_list = list(set([i.split('/')[-2] for i in all_dirs]))
    if debug: print('All selected PMTs: ', pmt_list)

    dirs = []
    # Only take the test runs
    for dir in all_dirs:
        with open(f"{dir}/Experiment_data.txt", 'r') as Exp_data:
                expLines = Exp_data.readlines()
                for i in expLines:
                    id = i.split('=')[0]
                    value = i.split('=')[1].strip() 
                    if id == "Test_Run" : testRun = value
        if testRun=='true': dirs.append(dir)

    print("************* Please do not interrupt the process *************")
    print(f'Number of PMTs: {len(pmt_list)}')
    print(f"Total number of runs: {len(dirs)}")
    json_data = []
    missingTempData = 0
    # Fill the database
    for pmt in progressbar(pmt_list):
        singlePMT_dirs = list(filter(lambda x: pmt in x, dirs))
        runs = [] # runs start empty 
        for dir in singlePMT_dirs:
            recordTime = int(dir.split('/')[-1])
            with open(f"{dir}/Experiment_data.txt", 'r') as Exp_data:
                expLines = Exp_data.readlines()
                for i in expLines:
                    id = i.split('=')[0]
                    value = i.split('=')[1].strip()
                    if id == "PMT_Serial" : serial = value
                    elif id == "Chopper_Frequency(Hz)" : frq = int(value)
                    elif id == "PMT_high_voltage(V)" : hv = -int(value)
                    elif id == "Cathode_Current_at_max_brightness(nA)" : I_cathode = int(value)
                    elif id == "PMT_Base_Stages" : baseStages = int(value)
                    elif id == "Pedestal_Means[pre,post](V)" : pedestalMeans = value
                    elif id == "Pedestal_STD[pre,post](V)" : PrePedestalSTD = float(value.split(',')[0].strip('[]'))
                    elif id == "Constant_LED(V)" : VC = float(value)
                    elif id == "Flashing_LED(V)" : VB = float(value)
                    elif id == "PMT_Power_On_Timestamp(DateTime)" : poweredOnTime = int(value)
                    elif id == "Record_Time(s)" : TotalRecordTime = int(value)

            LEDTemp = []
            boxTemp = []
            
            with open(f"{dir}/Temp_data.txt", 'r') as Exp_data:
                expLines = Exp_data.readlines()
                for i in expLines:
                    temp = i.split('=')[1].strip()
                    LEDTemp.append(float(temp.split(',')[0]))
                    boxTemp.append(float(temp.split(',')[1]))

                if serial != pmt: print('\nError: Serial number does not match!', pmt, serial)

            x, y, x_err, y_err, H, L = Multiple_runs_analysis.analysis(dir, plotting=False)  # y:(H-L)/(H+L) , x:(H+L)/2
            
            if len(x)!=len(LEDTemp) or len(x)!=len(boxTemp):missingTempData+=1

            LED_voltages={"constant": VC, "flashing": VB}
            method= 'Quartet' if frq==960 else 'Pairwise'
            Temp={'LEDs':LEDTemp, "PMTbox":boxTemp}

            runs.append({"Record_timestamp": recordTime,
                        "Powered_on_timestamp": poweredOnTime,
                        "Total_record_time(s)": TotalRecordTime,
                        "HV(V)": hv, 
                        "Max_cathode_current(nA)": I_cathode,
                        "LED_flashing_frequency(Hz)": frq,
                        "Asymmetry_calculation_method": method,
                        "PMT_base_stages": baseStages, 
                        "LED_voltages(V)": LED_voltages,
                        "Temperature(C)": Temp,
                        "Average_H(V)": H.tolist(),
                        "Average_L(V)":L.tolist(),
                        "Anode_current(uA)": x.tolist(),
                        "Anode_current_err(uA)": x_err.tolist(),
                        "Asymmetry": y.tolist(),
                        "Asymmetry_err": y_err.tolist()
                        })

        json_data.append({"PMT": pmt, "runs": runs})

    formatted_data = pprint.pformat(json_data, indent=1, width=100, compact=True) # make 
    formatted_data = str(formatted_data).replace("'", '"')

    with open('Consecutive_runs_database.json', 'w') as f:
        f.write(formatted_data)
    print(f"[Info]: Database created successfully!")
    if missingTempData:print(f"[Info]: Potential temperature data losses detected in {missingTempData} runs")

if __name__ == "__main__":
    main()