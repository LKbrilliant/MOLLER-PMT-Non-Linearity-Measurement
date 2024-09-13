# Code by:    Anuradha Gunawardhana
# Date:       2024.09.10
# Description: Generate the final database (a .json file) that contain analysis data of all the performed run.

import numpy as np
import matplotlib.pyplot as plt
import argparse
from scipy.optimize import curve_fit
import os
import sys
import Calculate_Asymmetry
import pprint
from pathlib import Path
import time

dirDepth = 4
gain = 200 #kilo-ohms

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

def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)
        
def allDirsPassed(path):
    all_base_dirs = [i[0] for i in os.walk(path) if len(Path(i[0]).parents)==dirDepth-1]
    need_to_remove=[]
    e=True
    for directory in all_base_dirs:
        try:
            subdir_count = len(next(os.walk(directory))[1])
            if subdir_count < 11:
                need_to_remove.append(directory)
                e=False
        except OSError:
            continue
    print("[ERROR]: Check the run count of following directories and try again!")
    for d in need_to_remove:
        print(d)
    return e

def division_with_uncertainty(n,nr,d,dr):
    return n/d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n/d)) # taking absolute of the uncertainty

def multiplication_with_uncertainty(n,nr,d,dr):
    return n*d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n*d)) # taking absolute of the uncertainty

def linearFunc(x,intercept,slope):
    return intercept + slope * x

def constFunc(x,c):
    return c

def ComputeLinearity(path):
    res, y, y_err, x, x_err, diodeMean, diodeMean_err = Calculate_Asymmetry.calculateAsymmetry(path , filter_count=9, plotting=False)  # y:(H-L)/(H+L) , x:(H+L)/2
    if res==0:
        x = (x/gain)*1000 # Convert voltages to current
        x_err = (x_err/gain)*1000
        params,cov = curve_fit(linearFunc,x,y, sigma=y_err, p0=[np.mean(y), 0], absolute_sigma=True) # set initial guesses of intercept to mean of the asymmetries and 0 for slope
        inter = params[0]
        slope = params[1]
        sigma = np.sqrt(np.diag(cov)) #  fit error

        inter_err = sigma[0]
        slope_err = sigma[1]

        y_fit_linear = linearFunc(x,*params)

        chisqr = np.sum(((y-y_fit_linear)/y_err)**2) # reduced chi-square
        ndf = len(y) - 2 # (#observations -  #fitted parameters) since linear fit, only two parameters
        
        # To be linear: (m/c)*max[x]=0 condition needs to be satisfied
        b, b_err = division_with_uncertainty(slope,slope_err,inter,inter_err)
        lin, lin_err = multiplication_with_uncertainty(b,b_err,np.max(x),x_err[np.argmax(x)])
        lin *= 100 # get percentage value
        lin_err *= 100

        return x, x_err, y, y_err ,chisqr, ndf, lin, lin_err, slope, inter, diodeMean, diodeMean_err
    else: print(f"[Error] Analysis failed: {path}")

def main():
    parser = argparse.ArgumentParser(prog='MOLLER Experiment: Linearity uncertainty test',
                                     description='Compare linearity data of one PMT. \nCode by: Anuradha Gunawardhana')
    
    parser.add_argument("-d", "--dir", required=True, help="Record directory")
    parser.add_argument("-i","--ignore",type=bool, help="Ignore file count test")

    args = parser.parse_args()
    mypath = os.path.normpath(args.dir) # remove trailing slashes
    if args.ignore == None: ig=False
    else: ig=True
    
    if not ig and not allDirsPassed(mypath): return
    
    all_dirs = [i[0] for i in os.walk(mypath) if len(Path(i[0]).parents)==dirDepth]
    # all_dirs = filter_directories(all_dirs)
    pmt_list = list(set([i[0].split('/')[dirDepth-2] for i in os.walk(mypath) if len(Path(i[0]).parents)==dirDepth]))
    dirs = []
    # Discard test runs
    for dir in all_dirs:
        with open(f"{dir}/Experiment_data.txt", 'r') as Exp_data:
                expLines = Exp_data.readlines()
                for i in expLines:
                    id = i.split('=')[0]
                    value = i.split('=')[1].strip() 
                    if id == "Test_Run" : testRun = value
        if testRun=='false': dirs.append(dir)
    # 'Serial', 'CB', 'CR','D1','Nominal_Sensitivity','Dark_Current','Maximum_sensitivity'
    PMT_Spec = np.loadtxt('PMT_Specs.csv',delimiter=',',skiprows=1, usecols=(1,2,3,4,5,6))
    PMT_Spec_Serial = np.loadtxt('PMT_Specs.csv',dtype=('U8'), delimiter=',',skiprows=1, usecols=(0))

    diff =list(set(pmt_list)-set(PMT_Spec_Serial))
    if len(diff)!=0:
        print(f"[Error]: Check the PMT Spec entries: {diff}")
        return
    print("************* Please do not interrupt the process *************")
    print(f'Number of PMTs: {len(pmt_list)}')
    print(f"Total number of runs: {len(dirs)}")
    # print(dirs)
    json_data = []
    noTemperatureData = 0
    # Fill the database
    for pmt in progressbar(pmt_list):
        singlePMT_dirs = list(filter(lambda x: pmt in x, dirs))
        runs = [] # runs start empty 
        for dir in singlePMT_dirs:
            with open(f"{dir}/Experiment_data.txt", 'r') as Exp_data:
                expLines = Exp_data.readlines()
                if len(expLines) != 28: noTemperatureData+=1
                temp = "NA" # Account for any potential data losses
                for i in expLines:
                    id = i.split('=')[0]
                    value = i.split('=')[1].strip()
                    if id == "PMT_Serial" : serial = value
                    elif id == "Chopper_Frequency(Hz)" : frq = int(value)
                    elif id == "PMT_high_voltage(V)" : hv = -int(value)
                    elif id == "Cathode_Current_at_max_brightness(nA)" : I_cathode = int(value)
                    elif id == "PMT_Base_Stages" : baseStages = int(value)
                    elif id == "Temperature[LEDs,Dark Box](C)" : temp = float(value.split(',')[1])
                    elif id == "Pedestal_Means[pre,post](V)" : pedestalMeans = value
                    elif id == "Pedestal_STD[pre,post](V)" : PedestalSTD = float(value.split(',')[0].strip('[]'))
                    elif id == "Constant_LED(V)" : VC = float(value)
                    elif id == "Flashing_LED(V)" : VB = float(value)
                    elif id == "PMT_Power_On_Timestamp(DateTime)" : timestamp = int(value)

                if serial != pmt: print('\nError: Serial number does not match!', pmt, serial)
            x, x_err, y, y_err ,chiSqr, ndf, lin, lin_err, slope, inter, diodeMean, diodeMean_err = ComputeLinearity(dir)

            comb=[]
            for i in range(8):
                comb.append((i, i+1))
            dAdI=[]
            dAdI_err=[]
            Im=[]
            for i,u in list(comb):
                div,div_err = division_with_uncertainty((y[u]-y[i]), (y_err[u]+y_err[i]), (x[u]-x[i]), (x_err[u]+x_err[i]))
                dAdI_err.append(div_err)
                dAdI.append(div)
                Im.append((x[u]+x[i])/2)

            params,cov = curve_fit(constFunc,Im,dAdI, sigma=dAdI_err, p0=[0], absolute_sigma=True) # set initial guess for mean as 0
            mean_dAdI = params[0]
            mean_dAdI_err = np.sqrt(np.diag(cov))[0]

            fit_params={"m": slope, "c": inter,"Chi_square": chiSqr, "ndf": ndf}
            LED_voltages={"constant": VC, "flashing": VB}
            linearity={"Non_Linearity": lin,"Lin_err": lin_err}
            method= 'Quartet' if frq==960 else 'Pairwise'
            dAdI_data={"dAdI":mean_dAdI, "dAdI_err":mean_dAdI_err}
            pedestalData={"preMean": float(pedestalMeans.strip('[]').split(',')[0]), 
                          "postMean": float(pedestalMeans.strip('[]').split(',')[1]), 
                          "STD": PedestalSTD}
            
            runs.append({"Timestamp": timestamp,
                        "HV": hv, 
                        "Max_cathode_current": I_cathode,
                        "LED_flashing_frequency": frq, 
                        "PMT_base_stages": baseStages, 
                        "Dark_box_temperature": temp, 
                        "Non_Linearity": linearity,
                        "LED_voltages": LED_voltages,
                        "Pedestal_data":pedestalData,
                        "Linear_fit_params": fit_params,
                        "dAdI_analysis": dAdI_data,
                        "Anode_current": x.tolist(),
                        "Anode_current_err": x_err.tolist(),
                        "Asymmetry_calculation_method": method,
                        "Asymmetry": y.tolist(),
                        "Asymmetry_err": y_err.tolist(),
                        "Photodiode_mean": diodeMean.tolist(), 
                        "Photodiode_mean_err": diodeMean_err.tolist()
                        })

        sid = np.where(PMT_Spec_Serial == pmt)    
        testTicket = {'CB': PMT_Spec[sid][0][0], 
                          'CR': PMT_Spec[sid][0][1], 
                          'D1_gain': PMT_Spec[sid][0][2], 
                          'Nominal_sensitivity':  int(PMT_Spec[sid][0][3]), 
                          'Dark_Current': PMT_Spec[sid][0][4], 
                          'Max_sensitivity': int(PMT_Spec[sid][0][5])}

        json_data.append({"PMT": pmt, "TestTicket": testTicket, "runs": runs})

    formatted_data = pprint.pformat(json_data, indent=1, width=100, compact=True) # make 
    formatted_data = str(formatted_data).replace("'", '"')

    with open('Database.json', 'w') as f:
        f.write(formatted_data)
    
    print(f"[Info]: Database created successfully!")
    if noTemperatureData:print(f"[Info]: Potential data losses detected in {noTemperatureData} directories")

if __name__ == "__main__":
    main()