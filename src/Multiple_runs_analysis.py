# Code by:      Anuradha Gunawardhana
# Date:         2024.04.10
# Description:  Analysis of the multiple consecutive non-linearity runs

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from matplotlib.ticker import AutoMinorLocator,AutoLocator
import uproot
import os
import logging
import argparse
#import scienceplotse
import matplotlib
from scipy.optimize import curve_fit
import matplotlib.ticker as mticker

# from itertools import combinations
#matplotlib.rcParams.update({
        #"pgf.texsystem": "pdflatex",
        #"font.family": "serif",
        #"text.usetex": True,
        #"pgf.rcfonts": False,
    #})
#plt.style.use(["science", "grid"])


ADC_rate = 14705883         # Samples/sec
selection_ratio = 60        # % portion of the data needed to be selected from a half cycle
quartet_frequency = 960     # Chopper frequency for the quartet asymmetry analysis
pairwise_frequency = 1920   # Chopper frequency for the pairwise asymmetry analysis
debug = False
# runCount = 10

forcePairwise=False     # force the analysis to do the pairwise analysis regardless of the chopper frequency
forceQuartet=False
filter_count=9
gain = 200
# logging.basicConfig(#filename='logs',
#                     level=logging.DEBUG,
#                     format='[%(levelname)s]:%(message)s',
#                     datefmt = "%Y-%m-%d %H:%M:%S")

filter_transmission = [100, 79, 63, 50, 40, 32, 25, 10, 5, 1, 0.1, 0.01]

def createSobel(n): # n=8 -> [1, 1, 1, 1,-1,-1,-1,-1]
    arr_1 = np.ones((int(n/2),),dtype=int)
    f = np.append(arr_1, arr_1*-1)
    return f

def constFunc(x,c):
    return c

def linearFunc(x,intercept,slope):
    return intercept + slope * x

def division_with_uncertainty(n,nr,d,dr):
    return n/d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n/d))

def multiplication_with_uncertainty(n,nr,d,dr):
    return n*d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n*d))


def addOrReplaceLine(data_path, lineIdentifier, value):
    lineFound=False
    with open(f"{data_path}/Experiment_data.txt", 'r+') as Exp_data:
        expLines = Exp_data.readlines()
        for i, line in enumerate(expLines):
            id = line.split('=')[0]
            # value = i.split('=')[1].strip() 
            if id == lineIdentifier:
                lineFound=True
                lineNum=i
        if lineFound:
            with open(f"{data_path}/Experiment_data.txt", 'w') as Exp_data:
                for i, line in enumerate(expLines):
                    if lineNum!=i: Exp_data.write(line)
                    else: Exp_data.write(f'{lineIdentifier}={value}\n') # Replace the line with new data
        else: Exp_data.write(f'{lineIdentifier}={value}\n') # Add the new data line if not exist

def linearFit(x,y,x_err,y_err):

    params,cov = curve_fit(linearFunc,x,y, sigma=y_err, p0=[np.mean(y), 0], absolute_sigma=True) # set initial guesses of intercept to mean of the asymmetries and 0 for slope
    inter = params[0]
    slope = params[1]
    sigma = np.sqrt(np.diag(cov)) #  fit error

    inter_err = sigma[0]
    slope_err = sigma[1]

    logging.debug(f'The slope = {slope:.5f}, with uncertainty {slope_err:.5f}')
    logging.debug(f'The intercept = {inter:.4f}, with uncertainty {inter_err:.4f}')

    y_fit_linear = linearFunc(x,*params)

    chisqr = np.sum(((y-y_fit_linear)/y_err)**2) # reduced chi-square
    ndf = len(y) - 2 # (#observations -  #fitted parameters) since linear fit, only two parameters
    
    # To be linear: (m/c)*max[x]=0 condition needs to be satisfied
    b, b_err = division_with_uncertainty(slope,slope_err,inter,inter_err)
    lin, lin_err = multiplication_with_uncertainty(b,b_err,np.max(x),x_err[np.argmax(x)])

    return lin, lin_err, y_fit_linear, chisqr, ndf

def main():
    parser = argparse.ArgumentParser(prog='MOLLER Experiment PMT Linearity Calculation',
                                     description='Calculate the PMT linearity for the MOLLER experiment. \nCode by: Anuradha Gunawardhana')
    
    parser.add_argument("-d","--dir",required=True, help="Root file directory for single run ")
    # parser.add_argument("-r","--runs",required=True, help="Number of complete non-linearity runs")
    args = parser.parse_args()
    data_path = os.path.normpath(args.dir) # remove trailing slashes
    if debug: print(" ------------------------------------------------")
    if debug: print("|         Debug:Non-Linearity Analysis           |")
    if debug: print(" ------------------------------------------------")

    fileTestPassed = False
    dataTestPassed = False
    #----------------------File count Test--------------------------#
    dir_files = []
    for path in os.listdir(data_path):
        if os.path.isfile(os.path.join(data_path, path)):
            dir_files.append(path)
    # if debug: print(f"Actual files = {dir_files}")

    runCount = 0
    for dir in dir_files:
        if ".root" in dir:
            run = int(dir.split('-')[1])
            if run > runCount: runCount=run
    print(f'Number of runs: {runCount}')

    expected_file_list = []
    if debug: print(f"[Test begin]: Checking the root files - \"{data_path}\"")
    for u in range(1,runCount+1):
        for i in range(1, 10):
            expected_file_list.append(f'Run-{u}-F{i}.root')
    # if debug: print(f"Expected files = {expected_file_list}")
    
    
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
    length_passed = np.empty([runCount,9])
    data = np.empty([runCount,9,dataArr_limit])
    if debug: print(f"Data size= {data.shape}")
    #----------------------- Plot config ------------------------#
    for rootFile in expected_file_list:
        RunNumber = int(rootFile.split('-')[1])-1
        f = int(rootFile.split('-')[2].split('.')[0][1:])-1
        r = int(rootFile.split('-')[1])-1
        file = uproot.open(f'{data_path}/{rootFile}')
        tree = file['DataTree']
        branches = tree.arrays()  
        t = branches['tStmp'].to_numpy()
        t = t.reshape((t.shape[1]))
        ch0 = branches['ch1_data'].to_numpy()   # Photomultiplier(PMT) data
        ch0 = ch0.reshape((ch0.shape[1]))

        if (t[-1] > 100 and len(ch0) > dataArr_limit): 
            data[RunNumber,f] = ch0[0:dataArr_limit]    # Trim the edges
            length_passed[r,f] = 1
        else: 
            if debug: print(f"[ERROR]: {rootFile} - [Initial,Trimmed] shapes = [{ch0.shape},{data[f].shape}]")
            length_passed[r,f] = 0
    
    if not np.all(length_passed): 
        logging.error(f" 🚨 [Test Failed]: Data length is less than {dataArr_limit} ms")
    else: 
        if debug: print(f" ✅ [Test Passed]: Found adequate data for the analysis")
        dataTestPassed = True

        TEMP_PMT = np.empty([runCount])
        TEMP_LED = np.empty([runCount])
        with open(f"{data_path}/Temp_data.txt", 'r') as Temp_data:
            tempLines = Temp_data.readlines()
            for idx, line in enumerate(tempLines):
                TEMP_PMT[idx] = float(line.split(',')[-1])
                TEMP_LED[idx] = float(line.split(',')[1].split('=')[-1])

        with open(f"{data_path}/Experiment_data.txt", 'r') as Exp_data:
            expLines = Exp_data.readlines()
            for i in expLines:
                id = i.split('=')[0]
                value = i.split('=')[1].strip() 
                if id == "Chopper_Frequency(Hz)" : chopper_frequency = int(value)
                if id == "Record_Time(s)" : runTime = value
        
        if chopper_frequency != pairwise_frequency and chopper_frequency != quartet_frequency: 
            logging.error("🚨 [Analysis Failed]:Chopper frequencies don't match")
            res=-1
            return
        if forcePairwise and forceQuartet: 
            logging.error("🚨 [Analysis Failed]:Cannot force both analysis same time")
            res=-1
            return
        if not forcePairwise and not forceQuartet: analysisMethod = 'pairwise' if chopper_frequency==pairwise_frequency else 'quartet'
        elif forcePairwise: 
            logging.info(f'Forcing pairwise analysis on {chopper_frequency} Hz data')
            analysisMethod = 'pairwise'
        elif forceQuartet: 
            logging.info(f'Forcing quartet analysis on {chopper_frequency} Hz data')
            analysisMethod = 'quartet'
        #----------------------Pedestal Correction------------------------#
        pedestal = [0,0]
        pedestal_sigma = [0,0]
        pedestal_mean = [0,0]

        for n in range(runCount):
            for p in range(2):
                # file = uproot.open(f'{data_path}/12-{p}.root')
                if p==0: file = uproot.open(f'{data_path}/Run-{n}-F12.root')
                else: file = uproot.open(f'{data_path}/Run-{n+1}-F12.root')

                ch0 = file['DataTree'].arrays()['ch1_data'].to_numpy()
                pedestal[p] = ch0.reshape((ch0.shape[1]))
                pedestal_sigma[p] = np.std(pedestal[p])
                pedestal_mean[p] = np.mean(pedestal[p]) # mean of each pedestal

            data[n] -= np.mean(pedestal_mean)

            if debug: print(f'Pedestal [mean(correction), drift/pre_sigma] = [{np.mean(pedestal_mean):.4f}, {abs((np.mean(pedestal[0])-np.mean(pedestal[1]))/pedestal_sigma[0]):.8f}]')

        #-----------------------Sobel window size--------------------------#
        sampling_rate = ADC_rate/prescale                                   # Usual rate ~ 1,470,588.3
        samples_per_cycle = sampling_rate/chopper_frequency
        sobelSize = int(samples_per_cycle*0.5)             # Sobel size should cover around quarter(0.25) of H-L cycle to get a triangular shape
        w = int(samples_per_cycle*selection_ratio/(4*100))  # Data selection width. Total selection =2*w
        if debug: print(f'\nSOBEL DATA - Samples per cycle = {int(samples_per_cycle)}, SobelSize = {sobelSize}, Selection_width({selection_ratio}%) = {2*w}')
        #------------------------------------------------------------------#

        A_LED = np.empty([runCount, filter_count]) #Ratio between high and low levels
        A_LED_err = np.empty([runCount, filter_count])
        I_anode = np.empty([runCount, filter_count]) #Mean voltage level
        I_anode_err = np.empty([runCount, filter_count])

    if fileTestPassed and dataTestPassed:
        for r in range(runCount):
            figAsyHist, asyPlot = plt.subplots(3, 3, figsize=(13, 12),constrained_layout = True)
            figRaw, rawPlot = plt.subplots(figsize=(10, 7), constrained_layout = True)
            pt = int(dataArr_limit*0.1) # custom points
            for i,f in enumerate(data[r][0:filter_count]):

                DC_offset = np.mean(f) # DC offset to plot triangular wave
                sobel_filtered_data = abs(np.convolve(f, createSobel(sobelSize), mode="same"))*(1/sobelSize) 
                
                sobel_filtered_data = sobel_filtered_data[int(sobelSize/2):-int(sobelSize/2)] # discard missing values from sides 
                peaks, _  = find_peaks(sobel_filtered_data, distance = int(sobelSize*0.9))

                Asy_count = int(len(peaks)/2)-2  # -2 for skipping last two peaks
                A_LED_temp = np.zeros(Asy_count)
                A_LED_err_temp = np.zeros(Asy_count)
                V_mean_temp = np.zeros(Asy_count)
                V_mean_err_temp = np.zeros(Asy_count)

                clr = ['red', 'orange'] # colors for quartet analysis separation plot
                for u in range(Asy_count):  # Iterate over peaks and select H & L data points
                    if analysisMethod == 'quartet':      # Quartet analysis for 960Hz
                        v1 = np.append(f[peaks[2*u+2]:peaks[2*u+2]+w], f[peaks[2*u+4]-w:peaks[2*u+4]])
                        v2 = f[peaks[2*u+3]-w:peaks[2*u+3]+w]
                        r=0 # For plotting
                        if np.mean(v1) < np.mean(v2): # v1<v2: |+--+|+--+|+--+|  v1>v2: |-++-|-++-|-++-| 
                            v1 = np.append(f[peaks[2*u+3]:peaks[2*u+3]+w], f[peaks[2*u+5]-w:peaks[2*u+5]])
                            v2 = f[peaks[2*u+4]-w:peaks[2*u+4]+w]
                            r=1
                
                    if analysisMethod == 'pairwise':     # Pairwise analysis for 1920Hz flashing (Calculate asymmetry by selecting every adjacent H&L pair)
                        v1 = f[peaks[2*u+2]-w:peaks[2*u+2]+w]       # Selecting data using peaks(skip two first peaks)    -+-|+-|+-|+-|+-|+-
                        v2 = f[peaks[2*u+3]-w:peaks[2*u+3]+w]

                    H = max(np.mean(v1), np.mean(v2))    # Differentiate H and L using min and max
                    L = min(np.mean(v1), np.mean(v2))

                    V_mean_temp[u] = (H + L)/2
                    A_LED_temp[u] = (H - L)/(H + L) # calculate Asymmetry for selected pair of High and LOW
                
                A_LED[r][i] = np.mean(A_LED_temp) # Final asymmetry for per filter positions
                A_LED_err[r][i] = np.std(A_LED_temp)/np.sqrt(len(A_LED_temp)) # standard error of mean
                
                I_anode[r][i]  = (np.mean(V_mean_temp)/gain)*1000
                I_anode_err[r][i] = ((np.std(V_mean_temp)/np.sqrt(len(V_mean_temp)))/gain)*1000 # standard error of mean
            
                nn, b, patches = asyPlot[int(i/3), i%3].hist(A_LED_temp, bins=100, alpha=0.6)
                nk=np.max(nn)
                asyPlot[int(i/3), i%3].axvline(A_LED[r][i],ls='--',color='r',label=r'Mean($\mu$)',lw=1)
                # asyPlot[int(i/3), i%3].fill_betweenx(np.arange(0,nk), eminus, eplus, facecolor='green', alpha=0.8)
                asyPlot[int(i/3), i%3].errorbar(A_LED[r][i], nk/10, xerr=A_LED_err[r][i],elinewidth=1, capsize=3, ecolor='k', lw=0, label=r'$\delta\mu=\pm\sigma /\sqrt{{n}}$')
                asyPlot[int(i/3), i%3].set_title(fr"F:{filter_transmission[i]}\%, $\sigma$={np.std(A_LED_temp):.2e}, $\mu$={A_LED[0][i]:.2e}, $\sigma /                     \sqrt{{n}}$={np.std(A_LED_temp)/np.sqrt(len(A_LED_temp)):.2e}",fontsize=11)
                asyPlot[int(i/3), i%3].set_xlabel(r"$A_{LED}$",fontsize=14)
                asyPlot[int(i/3), i%3].set_ylabel(r"$Count$",fontsize=14)
                asyPlot[int(i/3), i%3].margins(0)
                asyPlot[int(i/3), i%3].legend(title=f'n={len(A_LED_temp)}')
                asyPlot[int(i/3), i%3].xaxis.set_major_locator(AutoLocator())
                asyPlot[int(i/3), i%3].tick_params(axis='x',rotation = 45)

                rawPlot.plot(f[0:pt],alpha=0.5,label=f'F{i+1}: {filter_transmission[i]}%')

            plt.suptitle(f"Asymmetry distribution [Run: {r+1:02}]", fontsize=18)
            figAsyHist.savefig(f"{data_path}/Asymmetry_distribution_{r+1:02}.png")
            figRaw.savefig(f"{data_path}/Raw_data_{r+1:02}.png")
            plt.close(figAsyHist) # Close the figure to save memory
            plt.close(figRaw)
            

        if debug: print(" ✅ [Complete]: LED Asymmetries, Means and errors are calculated")
        res=0

        # add/replace analysis data
        addOrReplaceLine(data_path, 'Pedestal_Means[pre,post](V)', f'[{pedestal_mean[0]},{pedestal_mean[1]}]')
        addOrReplaceLine(data_path, 'Pedestal_STD[pre,post](V)', f'[{pedestal_sigma[0]},{pedestal_sigma[1]}]')

        figAsyScatter, asyScatterPlot = plt.subplots(figsize=(6,4))
        for i in range(runCount):
            asyScatterPlot.errorbar(I_anode[i],A_LED[i], yerr=A_LED_err[i],fmt='.',ms=3, color='#e81d1d',
                   ecolor='black',elinewidth=0.5,capsize=3,capthick=0.5)
        asyScatterPlot.set_xlabel(r'Anode Current ($\mu$A)', fontsize=12)
        asyScatterPlot.set_ylabel('LED Asymmetry',fontsize=12)
        asyScatterPlot.set_title(f'Run Count = {runCount}',fontsize=12)
        figAsyScatter.savefig(f'{data_path}/all-{runCount}-runs.png',
                transparent=False,
                dpi=500,
                format='png',
                bbox_inches='tight')

        A_LED_mean = np.empty(filter_count)
        A_LED_mean_err = np.empty(filter_count)
        I_anode_mean = np.empty(filter_count) #Mean voltage level
        I_anode_mean_err = np.empty(filter_count)

        # Error estimation for multiple filter runs
        for i in range(filter_count):
            A_LED_mean[i] = np.mean(A_LED[:,i])
            A_LED_mean_err[i] = (np.std(A_LED[:,i]))

            I_anode_mean[i] = np.mean(I_anode[:,i])
            I_anode_mean_err[i] = np.std(I_anode[:,i])

        linearity=np.empty(runCount)
        linearity_err=np.empty(runCount)
        for i in range(runCount):
            lin, lin_err, _, _, _ = linearFit(I_anode[i],A_LED[i],I_anode_err[i],A_LED_err[i])
            linearity[i]=lin
            linearity_err[i]=lin_err

        # lin1, lin_err1, Asy_fit1, chi1, ndf1 = linearFit(I_anode_mean,A_LED_mean,I_anode_mean_err,A_LED_mean_err)
        # lin2, lin_err2, Asy_fit2, chi2, ndf2 = linearFit(I_anode[0],A_LED[0],I_anode_err[0],A_LED_err[0])

        figMeanSingle, meanSinglePlot = plt.subplots(figsize=(6,4))
        meanSinglePlot.errorbar(I_anode_mean,A_LED_mean, yerr=A_LED_mean_err,fmt='.',ms=3, alpha=0.7, lw=0, color='r',
                ecolor='r',elinewidth=0.5,capsize=3,capthick=0.5, label=f'Mean of {runCount} runs')
        
        # meanSinglePlot.plot(I_anode_mean,Asy_fit1,label='Linear fit:mean',c='tab:blue')

        meanSinglePlot.errorbar(I_anode[0],A_LED[0], yerr=A_LED_err[0],fmt='.',ms=3, alpha=0.7, lw=0, color='g',
            ecolor='g',elinewidth=0.5,capsize=3,capthick=0.5, label='Single run')
        
        # meanSinglePlot.plot(I_anode[0],Asy_fit2,label='Linear fit:single',c='tab:purple')

        meanSinglePlot.set_xlabel(r'Anode Current ($\mu$A)', fontsize=12)
        meanSinglePlot.set_ylabel('LED Asymmetry',fontsize=12)
        # ax3.set_title(f'Mean of {runCount}-runs')
        legend = meanSinglePlot.legend(fancybox=False, edgecolor="black")
        legend.get_frame().set_linewidth(0.5)
        figMeanSingle.savefig(f'{data_path}/single-with-{runCount}-runs.png',
                transparent=False,
                dpi=500, 
                format='png',
                bbox_inches='tight')
        
        # fig4, ax4 = plt.subplots(figsize=(6,4))
        # clr=np.linspace(0,255,runCount)
        # for i in range(9):
        #     # ax4.errorbar(I_anode[i],A_LED[i], yerr=A_LED_err[i],fmt='.',ms=3, color='#e81d1d',
        #     #             ecolor='black',elinewidth=0.5,capsize=3,capthick=0.5)
        #     ax4.scatter(I_anode[:,i],A_LED[:,i], s=3, c=clr, cmap='rainbow', alpha=0.8)
        #     # ax4.plot(I_anode[:,i],A_LED[:,i],lw=0.5)
        # ax4.set_xlabel(r'Anode Current ($\mu$A)', fontsize=12)
        # ax4.set_ylabel('LED Asymmetry',fontsize=12)
        # ax4.set_title(f'Run Count = {runCount}',fontsize=12)
        # fig4.savefig(f'{data_path}/{runCount}-runs-connected.png',
        #         transparent=False,
        #         dpi=500,
        #         format='png',
        #         bbox_inches='tight')

        figOverTime, overtimePlot = plt.subplots(10,1, figsize=(12,12),sharex=True)
        for i in range(10):
            if i<9:
                overtimePlot[i].plot(np.arange(1,runCount+1),A_LED[:,i])
                overtimePlot[i].set_ylabel(r'$A_{LED}$',fontsize=12)
            else:
                overtimePlot[i].errorbar(np.arange(1,runCount+1),linearity, yerr=linearity_err, elinewidth=1, capsize=3, ecolor='k', lw=0.5, ls='--')
                overtimePlot[i].set_ylabel(r'$Lin(\%)$',fontsize=12)

        overtimePlot[9].set_xlabel(r'Run number', fontsize=12)
        overtimePlot[0].set_title(f'Asymmetry variations',fontsize=12)
        plt.xticks(range(1,runCount+1))
        plt.hspace=0
        figOverTime.savefig(f'{data_path}/{runCount}-asy-lin-overtime.png',
                transparent=False,
                dpi=500, 
                format='png',
                bbox_inches='tight')

        figAsyMultiHist, asyMultiPlot = plt.subplots(3, 3, figsize=(11, 9),constrained_layout = True)
        for i in range(filter_count):
            nn, b, patches = asyMultiPlot[int(i/3), i%3].hist(A_LED[:,i], bins=20, alpha=0.6)
            nk=np.max(nn)
            asyMultiPlot[int(i/3), i%3].axvline(A_LED_mean[i],ls='--',color='r',label=r'Mean($\mu$)',lw=1)
            asyMultiPlot[int(i/3), i%3].errorbar(A_LED_mean[i], nk/10, xerr=A_LED_mean_err[i],elinewidth=1, capsize=3, ecolor='k', lw=0, label=r'$\delta=\pm\sigma$')
            asyMultiPlot[int(i/3), i%3].set_title(fr"F:{filter_transmission[i]}\%, $\mu$={A_LED_mean[i]:.2e}, $\sigma$={A_LED_mean_err[i]:.2e}",fontsize=11)
            asyMultiPlot[int(i/3), i%3].set_xlabel(r"$A_{LED}$",fontsize=14)
            asyMultiPlot[int(i/3), i%3].set_ylabel(r"$Count$",fontsize=14)
            legend = asyMultiPlot[int(i/3), i%3].legend(fancybox=False, edgecolor="black")
            legend.get_frame().set_linewidth(0.5)
            asyMultiPlot[int(i/3), i%3].xaxis.set_major_locator(AutoLocator())
            asyMultiPlot[int(i/3), i%3].tick_params(axis='x',rotation = 45)
        plt.suptitle(f"Consecutive {runCount} runs", fontsize=18)
        figAsyMultiHist.savefig(f"{data_path}/Multiple-Asymmetry_distribution.png")

        figTemp, tempPlot = plt.subplots(3, 3, figsize=(11, 9),constrained_layout = True)
        clr=np.linspace(0,255,runCount)
        for i in range(filter_count):
            tempPlot[int(i/3), i%3].scatter(TEMP_LED, A_LED[:,i],s=10,c=clr, cmap='viridis', alpha=0.8)
            tempPlot[int(i/3), i%3].set_title(fr"F:{filter_transmission[i]}\%",fontsize=11)
            tempPlot[int(i/3), i%3].set_xlabel(r"$LED Temp. (^oC)$",fontsize=13)
            tempPlot[int(i/3), i%3].set_ylabel(r"$A_{LED}$",fontsize=13)
            # tempPlot[int(i/3), i%3].legend()
            tempPlot[int(i/3), i%3].xaxis.set_major_locator(AutoLocator())
            tempPlot[int(i/3), i%3].tick_params(axis='x',rotation = 45)
        plt.suptitle(f"Consecutive {runCount} runs", fontsize=18)
        # plt.colorbar(orientation="horizontal").set_label(label='new label',size=15,weight='bold')
        figTemp.colorbar(tempPlot[0, 0].scatter(TEMP_LED, A_LED[:,0], c=clr, s=0), 
                         ticks=np.linspace(0,255,10),
                         format=mticker.FixedFormatter(np.linspace(1,runCount,10, dtype=int)),
                         ax=tempPlot, 
                         location='right',
                         aspect=60,
                         pad=0.02,
                         label="Run Number")
        figTemp.savefig(f"{data_path}/Asy-Temp.png")

        figAllTemps, allTempPlot = plt.subplots(figsize=(6,3))
        allTempPlot.plot(np.arange(1,runCount+1),TEMP_PMT, label='PMT')
        allTempPlot.plot(np.arange(1,runCount+1),TEMP_LED, label='LED')
        allTempPlot.set_xticks(range(1,runCount+1))
        allTempPlot.set_ylabel(r"$Temp. (^oC)$",fontsize=12)
        allTempPlot.set_xlabel("Run Number",fontsize=12)
        allTempPlot.set_title(f'Run Count = {runCount}',fontsize=14)
        legend = allTempPlot.legend(fancybox=False, edgecolor="black")
        legend.get_frame().set_linewidth(0.5)
        figAllTemps.savefig(f"{data_path}/AllTemps.png")

        figLinTemp, linTempPlot = plt.subplots(figsize=(10,6))
        linTempPlot.scatter(TEMP_LED, linearity)
        linTempPlot.set_xlabel(r"$LED Temp. (^oC)$",fontsize=12)
        linTempPlot.set_ylabel("Non-Linearity(\%)",fontsize=12)
        linTempPlot.set_title('Non-linearity vs. LED Temp.',fontsize=14)
        figLinTemp.savefig(f"{data_path}/lin-temp.png")

    else: 
        logging.error(" 🚨 [Analysis Failed]: One or more tests failed")
    
if __name__ == "__main__":
    main()
