# Code by:  Anuradha Gunawardhana
# Date:     2024.09.13
# Description: Utility functions for calculating the LED asymmetry from the recorded root files

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from matplotlib.ticker import AutoMinorLocator,AutoLocator
import uproot
import os
import logging

ADC_rate = 14705883         # Samples/sec
selection_ratio = 60        # % portion of the data needed to be selected from a half cycle
quartet_frequency = 960     # Chopper frequency for the quartet asymmetry analysis
pairwise_frequency = 1920   # Chopper frequency for the pairwise asymmetry analysis
dataQualityThreshold = 3    # Maximum threshold factor of standard deviations allowed for random noise 
debug = False

# logging.basicConfig(#filename='logs',
#                     level=logging.DEBUG,
#                     format='[%(levelname)s]:%(message)s',
#                     datefmt = "%Y-%m-%d %H:%M:%S")

filter_transmission = [100, 79, 63, 50, 40, 32, 25, 10, 5, 1, 0.1, 0.01]

def createSobel(n): # n=8 -> [1, 1, 1, 1,-1,-1,-1,-1]
    arr_1 = np.ones((int(n/2),),dtype=int)
    f = np.append(arr_1, arr_1*-1)
    return f

def addOrReplaceLine(data_path, lineIdentifier, value):
    '''
    Add new entries to the experiment_data text file.
    If the value identifier already exist in the file, only the value is update
    If there's no existing identifier, a new one will be created with the value 
    '''
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

def find_anomalies(data, threshold=dataQualityThreshold):
    return np.abs(data - np.mean(data)) > threshold * np.std(data)

def dataQualityTest(data,sobelSize):
    anomaly_threshold = 1
    for i,y in enumerate(data):
        if i!=9 and i!=10: # Skip filter 10 and 11 as they are not used for the analysis but test pedestal runs
            stat_anomalies = find_anomalies(y)
            anSum = np.sum(stat_anomalies)
            stat_factor = (anSum/len(stat_anomalies))*100
            if stat_factor > anomaly_threshold: 
                print(f'🚨 [ERROR]: {stat_factor:.2f}% anomalies detected in F{i+1} data')
                return -1

        if i<9: 
            sobel_filtered_data = abs(np.convolve(y, createSobel(sobelSize), mode="same"))*(1/sobelSize)  
            sobel_filtered_data = sobel_filtered_data[int(sobelSize/2):-int(sobelSize/2)] # discard missing values from sides 
            peaks, _  = find_peaks(sobel_filtered_data, distance = int(sobelSize*0.9))
            periods = np.diff(peaks)
            
            sobel_anomalies = find_anomalies(periods)
            anSum = np.sum(sobel_anomalies)
            sobel_factor = (anSum/len(sobel_anomalies))*100
            if sobel_factor > anomaly_threshold:
                print(f'🚨 [ERROR]: {sobel_factor:.2f}% period related anomalies detected in F{i+1}')
                return -1
            
    if debug: print(f"✅ [Test Passed]: Total detected data irregularities are less than {anomaly_threshold}%")
    return 1

def calculateAsymmetry(data_path,
                       filter_count,            # upto how many filters used for the analysis from filter 1
                       plotting=False,
                       forcePairwise=False,     # force the analysis to do the pairwise analysis regardless of the chopper frequency
                       forceQuartet=False,
                       bins=100):               # Bin count of the histograms

    if debug: print(" ------------------------------------------------")
    if debug: print("|         Debug:Non-Linearity Analysis           |")
    if debug: print(" ------------------------------------------------")

    fileTestPassed = False
    dataTestPassed = False
    #----------------------File count Test--------------------------#
    expected_file_list = []
    if debug: print(f"[Test begin]: Checking the root files - \"{data_path}\"")
    for i in range(1, 12):
        expected_file_list.append(f'{i}.root')
    expected_file_list.append('12-0.root')
    expected_file_list.append('12-1.root')
    if debug: print(f"Expected files = {expected_file_list}")
    
    dir_files = []
    for path in os.listdir(data_path):
        if os.path.isfile(os.path.join(data_path, path)):
            dir_files.append(path)
    if debug: print(f"Actual files = {dir_files}")
    
    check =  all(file in dir_files for file in expected_file_list)

    if check: 
        if debug: print(" ✅ [Test Passed]: All the necessary files are in order")
        fileTestPassed =True
    else: 
        logging.info(" 🚨 [Test Failed]: File list does not match with the filter count")
    #---------------------length test config--------------------#
    with open(f"{data_path}/CMDataSettings.txt", 'r') as CMData_settings:
        lines = CMData_settings.readlines()
        prescale = int(lines[4].split(" ")[1])                  # Get the prescale value used for down-sampling the data while recording
        record_length = float(lines[5].split(" ")[1])
    dataArr_limit = int((ADC_rate/prescale)*record_length*0.9)  # determine where the data 90% mark is
    if debug: print(f'prescale={prescale}, record_length={record_length:.2f}, data_limit:{dataArr_limit}')

    if debug: print(f"[Test begin]: Preprocessing \"{data_path}\"")
    length_passed = np.empty([len(expected_file_list)])
    data = np.empty([len(expected_file_list),dataArr_limit])
    diode_data = np.empty([len(expected_file_list),dataArr_limit])
    if debug: print(f"Data size= {data.shape}")
    #----------------------- Plot config ------------------------#
    if plotting: 
        figRaw, rawPlot = plt.subplots(figsize=(10, 7), constrained_layout = True)
        figFull, fullPlot = plt.subplots(figsize=(10,7),constrained_layout = True)
        figPhotodiode, diodePlot = plt.subplots(figsize=(10, 7), constrained_layout = True)
        figPedestal, pedestalPlot = plt.subplots(figsize=(8, 6), constrained_layout = True)
        figSobel, sobelPlot = plt.subplots(filter_count, 1,figsize=(15, 10),constrained_layout = True,sharex=True)
        figAsyHist, asyPlot = plt.subplots(3, 3, figsize=(13, 12),constrained_layout = True)
    #----------------------- Load data ------------------------#
    for f,rootFile in enumerate(expected_file_list):
        file = uproot.open(f'{data_path}/{rootFile}')
        tree = file['DataTree']
        branches = tree.arrays()  
        t = branches['tStmp'].to_numpy()
        t = t.reshape((t.shape[1]))
        ch0 = branches['ch1_data'].to_numpy()   # Photomultiplier(PMT) data
        ch0 = ch0.reshape((ch0.shape[1]))

        ch1 = branches['ch0_data'].to_numpy()   # Photo diode data
        ch1 = ch1.reshape((ch1.shape[1]))

        #---------------Check data lengths --------------------#
        if (t[-1] > 100 and len(ch0) > dataArr_limit): 
            data[f] = ch0[0:dataArr_limit]    # Trim the edges
            diode_data[f] = ch1[0:dataArr_limit]
            length_passed[f] = 1
            # if debug: print(f"F{f} - [Initial,Trimmed] shapes = [{ch0.shape},{data[f].shape}]")

            #-------- setup raw PMT and photo-diode data for plotting -------#
            pt = int(dataArr_limit*0.025) # custom points
            ft = dataArr_limit  # Full length end point
            # pt = int(dataArr_limit)
            if plotting:
                if f<9:
                    rawPlot.plot(t[0:pt], data[f][0:pt],alpha=0.5,label=f'F{f+1}: {filter_transmission[f]}%')
                    fullPlot.plot(t[0:ft], data[f],alpha=0.5,label=f'F{f+1}: {filter_transmission[f]}%')
                    diodePlot.plot(t[0:pt], diode_data[f][0:pt],alpha=0.5,label=f'F{f+1}: {filter_transmission[f]}%')

                if f==11: 
                    rawPlot.plot(t[0:pt], data[f][0:pt],alpha=0.5,label='Pre-Pedestal')
                    fullPlot.plot(t[0:ft], data[f],alpha=0.5,label='Pre-Pedestal')
                    diodePlot.plot(t[0:pt], diode_data[f][0:pt],alpha=0.5,label='Pre-Pedestal')
                if f==12: 
                    rawPlot.plot(t[0:pt], data[f][0:pt],alpha=0.5,label='Post-Pedestal')
                    fullPlot.plot(t[0:ft], data[f],alpha=0.5,label='Post-Pedestal')
                    diodePlot.plot(t[0:pt], diode_data[f][0:pt],alpha=0.5,label='Post-Pedestal')
        else: length_passed[f] = 0
    #------------------- Length test results -------------------#
    if not np.all(length_passed): 
        logging.error(f" 🚨 [Test Failed]: Data length is less than {dataArr_limit} ms")
    else: 
        if debug: print(f" ✅ [Test Passed]: Found adequate data for the analysis")
        dataTestPassed = True
        #---------------- Since test passed, collect Experiment_data --------------#
        with open(f"{data_path}/Experiment_data.txt", 'r') as Exp_data:
            expLines = Exp_data.readlines()
            for i in expLines:
                id = i.split('=')[0]
                value = i.split('=')[1].strip() 
                if id == "Chopper_Frequency(Hz)" : chopper_frequency = int(value)
                if id == "Record_Time(s)" : runTime = value
                if id == "PMT_Serial" : pmtName = value
        #-------Determine whether to do the pairwise or quartet analysis ----------#
        if chopper_frequency != pairwise_frequency and chopper_frequency != quartet_frequency: 
            logging.error("🚨 [Analysis Failed]:Chopper frequencies don't match")
        if forcePairwise and forceQuartet: 
            logging.error("🚨 [Analysis Failed]:Cannot force both analysis same time")
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

        for p in range(2):
            file = uproot.open(f'{data_path}/12-{p}.root')   
            ch0 = file['DataTree'].arrays()['ch1_data'].to_numpy()
            pedestal[p] = ch0.reshape((ch0.shape[1]))
            pedestal_sigma[p] = np.std(pedestal[p])
            pedestal_mean[p] = np.mean(pedestal[p]) # mean of each pedestal
            m="Pre" if p==0 else "Post"
            if plotting: pedestalPlot.hist(pedestal[p], bins=bins, alpha=0.6, label=f'{m}-Pedestal',density=True)

        pedestal_mean_diff = abs(pedestal_mean[1] - pedestal_mean[0])
        mean_pedestal_sigma = np.mean(pedestal_sigma) # mean of standard deviations 
        fac = 0.2 # fraction of acceptable drift 
        k = True if pedestal_mean_diff < fac*mean_pedestal_sigma else False
        if plotting:
            pedestalPlot.xaxis.set_minor_locator(AutoMinorLocator())
            pedestalPlot.yaxis.set_minor_locator(AutoMinorLocator())
            pedestalPlot.set_xlabel("ADC Voltage (V)")
            pedestalPlot.set_ylabel("Probability Density")
            pedestalPlot.set_title("Probability densities of ADC pedestal runs")
            pedestalPlot.legend(title=rf'$\sigma_{{pre}}$= {pedestal_sigma[0]:.3e}'+'\n'+
                                    fr'$\sigma_{{post}}$= {pedestal_sigma[1]:.3e}'+'\n'+
                                    fr'{"✔️" if k else "‼️"} $|\mu_{{post}}-\mu_{{pre}}| {"<" if k else ">"} \sigma_{{avg}}*{int(fac*100)}\%$'+'\n'+
                                    f'Run Time = {runTime}s')
            pedestalPlot.margins(0)
            figPedestal.savefig(f"{data_path}/pedestal.png")

        pedestal_correction = np.mean(pedestal_mean) # average of both mean
        data -= pedestal_correction

        #---------------------- Pedestal correction for photodiode ----------------------#
        photodiode_pedestal = np.mean([np.mean(diode_data[11]), np.mean(diode_data[12])])
        diode_data = diode_data[0:filter_count]  # keep only 9 filter positions
        diode_data -= photodiode_pedestal
        diodeMean = np.mean(diode_data,axis=1)
        diodeMean_err = np.std(diode_data,axis=1)/np.sqrt(len(diode_data[0]))

        if debug: print(f'Pedestal [mean(correction), drift/pre_sigma] = [{pedestal_correction:.4f}, {abs((np.mean(pedestal[0])-np.mean(pedestal[1]))/pedestal_sigma[0]):.8f}]')
        #-------------Plot the raw PMT and photo-diode data----------------------#
        if plotting:
            rawPlot.xaxis.set_minor_locator(AutoMinorLocator())
            rawPlot.yaxis.set_minor_locator(AutoMinorLocator())
            rawPlot.legend(loc='upper right',fontsize="12") 
            rawPlot.set_ylabel(r'Voltage $(V)$',fontsize=15) 
            rawPlot.set_xlabel(r"Time $(ms)$",fontsize=15)
            rawPlot.set_title("Raw data: Constant LED with Flashing LED", fontsize=18)
            rawPlot.margins(x=0)
            figRaw.savefig(f"{data_path}/RawData.png")

            # fullPlot.xaxis.set_minor_locator(AutoMinorLocator())
            # fullPlot.yaxis.set_minor_locator(AutoMinorLocator())
            fullPlot.grid(linestyle='--')
            fullPlot.legend(loc='upper right',fontsize="12") 
            fullPlot.set_ylabel(r'Voltage $(V)$',fontsize=15) 
            fullPlot.set_xlabel(r"Time $(ms)$",fontsize=15)
            fullPlot.set_title("Raw data: Full range", fontsize=18)
            fullPlot.margins(x=0)
            figFull.savefig(f"{data_path}/rawData_full.png")

            diodePlot.xaxis.set_minor_locator(AutoMinorLocator())
            diodePlot.yaxis.set_minor_locator(AutoMinorLocator())
            diodePlot.legend(loc='upper right',fontsize="12") 
            diodePlot.set_ylabel(r'Voltage $(V)$',fontsize=15) 
            diodePlot.set_xlabel(r"Time $(ms)$",fontsize=15)
            diodePlot.set_title("Photodiode raw data", fontsize=18)
            diodePlot.margins(x=0)
            figPhotodiode.savefig(f"{data_path}/Photodiode_raw.png")

        #-----------------------Sobel window size--------------------------#
        sampling_rate = ADC_rate/prescale                                   # Usual rate ~ 1,470,588.3
        samples_per_cycle = sampling_rate/chopper_frequency
        sobelSize = int(samples_per_cycle*0.5)             # Sobel size should cover around quarter(0.25) of H-L cycle to get a triangular shape
        w = int(samples_per_cycle*selection_ratio/(4*100))  # Data selection width. Total selection =2*w
        if debug: print(f'\nSOBEL DATA - Samples per cycle = {int(samples_per_cycle)}, SobelSize = {sobelSize}, Selection_width({selection_ratio}%) = {2*w}')
        #------------------------------------------------------------------#

        A_LED = np.empty(filter_count) #Ratio between high and low levels
        A_LED_err = np.empty(filter_count)
        V_mean = np.empty(filter_count) #Mean voltage level
        V_mean_err = np.empty(filter_count)
    #---------------- Data quality check ----------------#
    dataQualityPassed = dataQualityTest(data,sobelSize)
    #---------------- Asymmetry calculation --------------#
    if fileTestPassed and dataTestPassed and dataQualityPassed:
        if plotting:
            figSobel.suptitle(f"Data Filtering", fontsize=14)
            figAsyHist.suptitle(f"LED Asymmetry distribution", fontsize=18)
            sep_plot_lim=int(dataArr_limit*0.02) # Plot length (data points)

            xt=np.arange(0,sep_plot_lim)/(sampling_rate/1000) #scale the x-axis to proper milliseconds range

        for i,f in enumerate(data[0:filter_count]):
            #------------------- Asymmetry pair counting ------------------#
            DC_offset = np.mean(f) # DC offset to plot sobel triangular wave
            sobel_filtered_data = abs(np.convolve(f, createSobel(sobelSize), mode="same"))*(1/sobelSize)  
            sobel_filtered_data = sobel_filtered_data[int(sobelSize/2):-int(sobelSize/2)] # discard missing values from sides 
            peaks, _  = find_peaks(sobel_filtered_data, distance = int(sobelSize*0.9))

            Asy_count = int(len(peaks)/2)-2  # Asymmetry pair count. -2 for skipping last two peaks
            A_LED_temp = np.zeros(Asy_count)
            V_mean_temp = np.zeros(Asy_count)
            #----------------- filtering (and plotting) data based on the analysis method ------------#
            clr = ['red', 'orange'] # colors for quartet analysis separation plot
            for u in range(Asy_count):  # Iterate over peaks and select H & L data points
                if analysisMethod == 'quartet':      # Quartet analysis for 960Hz
                    v1 = np.append(f[peaks[2*u+2]:peaks[2*u+2]+w], f[peaks[2*u+4]-w:peaks[2*u+4]])
                    v2 = f[peaks[2*u+3]-w:peaks[2*u+3]+w]
                    r=0 # For plotting
                    if np.mean(v1) < np.mean(v2): # (v1<v2) = |+--+|+--+|+--+|,  (v1>v2) = |-++-|-++-|-++-| 
                        v1 = np.append(f[peaks[2*u+3]:peaks[2*u+3]+w], f[peaks[2*u+5]-w:peaks[2*u+5]])
                        v2 = f[peaks[2*u+4]-w:peaks[2*u+4]+w]
                        r=1
                    if plotting and peaks[2*u+3]+w < sep_plot_lim:
                        sobelPlot[i].scatter(np.append(np.arange(peaks[2*u+2+r],peaks[2*u+2+r]+w)/(sampling_rate/1000), np.arange(peaks[2*u+4+r]-w,peaks[2*u+4+r])/(sampling_rate/1000)),v1, alpha=0.5, color=clr[u%2] if (np.mean(v1)>np.mean(v2)) else 'g',marker ='.',linewidths=0.2)
                        sobelPlot[i].scatter(np.arange(peaks[2*u+3+r]-w,peaks[2*u+3+r]+w)/(sampling_rate/1000),v2, alpha=0.5, color='g' if (np.mean(v1)>np.mean(v2)) else clr[u%2],marker ='.',linewidths=0.2)
                
                if analysisMethod == 'pairwise':     # Pairwise analysis for 1920Hz flashing (Calculate asymmetry by selecting every adjacent H&L pair)
                    v1 = f[peaks[2*u+2]-w:peaks[2*u+2]+w]       # Selecting data using peaks(skip two first peaks)    -+-|+-|+-|+-|+-|+-
                    v2 = f[peaks[2*u+3]-w:peaks[2*u+3]+w]

                    if plotting and peaks[2*u+3]+w < sep_plot_lim:
                        sobelPlot[i].scatter(np.arange(peaks[2*u+2]-w,peaks[2*u+2]+w)/(sampling_rate/1000),v1, alpha=0.5, color='r' if (np.mean(v1)>np.mean(v2)) else 'g',marker ='.',linewidths=0.2)
                        sobelPlot[i].scatter(np.arange(peaks[2*u+3]-w,peaks[2*u+3]+w)/(sampling_rate/1000),v2, alpha=0.5, color='g' if (np.mean(v1)>np.mean(v2)) else 'r',marker ='.',linewidths=0.2)
                #------H,L separation per each asymmetry pair ------#
                H = max(np.mean(v1), np.mean(v2))    # Differentiate H and L based on the magnitude
                L = min(np.mean(v1), np.mean(v2))

                V_mean_temp[u] = (H + L)/2
                A_LED_temp[u] = (H - L)/(H + L) # calculate Asymmetry for selected pair of High and LOW
            #--------- Final mean asymmetry per filter --------#
            A_LED[i] = np.mean(A_LED_temp) # Final asymmetry for per filter positions
            A_LED_err[i] = np.std(A_LED_temp)/np.sqrt(len(A_LED_temp)) # standard error of mean
            
            V_mean[i]  = np.mean(V_mean_temp)
            V_mean_err[i] = np.std(V_mean_temp)/np.sqrt(len(V_mean_temp)) # standard error of mean
            #--------- Plotting asymmetry distributions and sobel filtering--------#
            if plotting:
                sobelPlot[i].plot(xt, f[0:sep_plot_lim], label="Raw Data", alpha=0.3)
                sobelPlot[i].plot(xt,(sobel_filtered_data + DC_offset-np.mean(sobel_filtered_data))[0:sep_plot_lim], alpha=0.7,label='Sobel filtered data')
                peaks_plot_len = 0
                for d,r in enumerate(peaks):
                    if r > sep_plot_lim: 
                        peaks_plot_len = d-1
                        break
                sobelPlot[i].legend(title=f'ND Filter: {filter_transmission[i]}%', bbox_to_anchor=(1.01, 1), borderaxespad=0)
                sobelPlot[i].set_ylabel(r"$Voltage(V)$",fontsize=11)
                sobelPlot[i].xaxis.set_minor_locator(AutoMinorLocator()) 
                sobelPlot[i].margins(x=0)     

                nn, b, patches = asyPlot[int(i/3), i%3].hist(A_LED_temp, bins=bins, alpha=0.6, label="Data")
                nk=np.max(nn)
                asyPlot[int(i/3), i%3].axvline(A_LED[i],ls='--',color='r',label=r'$\mu$',lw=1)
                # asyPlot[int(i/3), i%3].fill_betweenx(np.arange(0,nk), eminus, eplus, facecolor='green', alpha=0.8)
                asyPlot[int(i/3), i%3].errorbar(A_LED[i], nk/10, xerr=A_LED_err[i],elinewidth=1, capsize=3, ecolor='k', lw=0, label=r'$\sigma /\sqrt{{n}}$')
                asyPlot[int(i/3), i%3].set_title(fr"F:{filter_transmission[i]}%, $\sigma$={np.std(A_LED_temp):.2e}, $\mu$={A_LED[i]:.2e}, $\sigma /\sqrt{{n}}$={np.std(A_LED_temp)/np.sqrt(len(A_LED_temp)):.2e}",fontsize=12)
                asyPlot[int(i/3), i%3].set_xlabel(r"$A_{LED}$",fontsize=14)
                asyPlot[int(i/3), i%3].set_ylabel(r"$Count$",fontsize=14)
                asyPlot[int(i/3), i%3].margins(0)
                asyPlot[int(i/3), i%3].legend(title=f'n={len(A_LED_temp)}')
                asyPlot[int(i/3), i%3].xaxis.set_major_locator(AutoLocator())
                asyPlot[int(i/3), i%3].tick_params(axis='x',rotation = 45)

        if plotting:        
            # sobelPlot[0].legend(bbox_to_anchor=(1.01, 1), borderaxespad=0)
            sobelPlot[filter_count-1].set_xlabel(r"$Time(ms)$",fontsize=11)

            figSobel.savefig(f"{data_path}/Sobel_filtering.png")

            figAsyHist.savefig(f"{data_path}/Asymmetry_distribution.png")

        if debug: print(" ✅ [Complete]: LED Asymmetries, Means and errors are calculated")
        res=0

        # add/replace analysis data
        addOrReplaceLine(data_path, 'Pedestal_Means[pre,post](V)', f'[{pedestal_mean[0]},{pedestal_mean[1]}]')
        addOrReplaceLine(data_path, 'Pedestal_STD[pre,post](V)', f'[{pedestal_sigma[0]},{pedestal_sigma[1]}]')

        return res, A_LED, A_LED_err, V_mean, V_mean_err, diodeMean, diodeMean_err

    else: 
        print(f" 🚨 [ERROR]: {pmtName} analysis failed. One or more tests failed")
        res=-1
        return res, A_LED, A_LED_err, V_mean, V_mean_err, diodeMean, diodeMean_err