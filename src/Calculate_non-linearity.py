# Code by:  Anuradha Gunawardhana
# Date:     2023.08.16
# Description: Calculate the final integral and differential non-linearity of a PMT.

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from scipy.optimize import curve_fit
import Calculate_Asymmetry
import sys
import logging
import argparse
import os
from itertools import combinations

anode_current_max = 10 #(Units:μA) The program will return the error code 2 if the max anode current passed this threshold
anode_current_min = 8

logging.basicConfig(level=logging.INFO,
                    format="[%(levelname)s]: %(message)s",
                    handlers=[logging.FileHandler('logs'),logging.StreamHandler()])

def constFunc(x,c):
    return c

def linearFunc(x,intercept,slope):
    return intercept + slope * x

def secondOrdFunc(x, a, b, c):
    return a + b*x + c*x**2

def division_with_uncertainty(n,nr,d,dr):
    return n/d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n/d))

def multiplication_with_uncertainty(n,nr,d,dr):
    return n*d, abs(np.sqrt(((nr/n)**2)+(dr/d)**2)*(n*d))

def ComputeLinearity(path):
    res, y, y_err, x, x_err,_,_ = Calculate_Asymmetry.calculateAsymmetry(path , 
                                                                       filter_count=9, 
                                                                    #    forceQuartet=True,
                                                                    #    forcePairwise=True,
                                                                       plotting=True
                                                                       )
    if res==0:
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

    return res,x, x_err, y, y_err, y_fit_linear,chisqr, ndf, lin, lin_err

def main():
    parser = argparse.ArgumentParser(prog='MOLLER Experiment PMT Linearity Calculation',
                                     description='Calculate the PMT linearity for the MOLLER experiment. \nCode by: Anuradha Gunawardhana')
    
    parser.add_argument("dir", help=",<dir> .root file directory for single run ")
    args = parser.parse_args()
    mypath = os.path.normpath(args.dir) # remove trailing slashes
    timeStamp = mypath.split('/')[-1]                  
    # res, y, y_err, x, x_err = Calculate_Asymmetry.calculateAsymmetry(mypath , filter_count=9, plotting=True)  # y:(H-L)/(H+L) , x:(H+L)/2
    print('***** Please Do Not Interrupt The Process *****')
    res,x, x_err, y, y_err, y_fit_linear,chisqr, ndf, lin, lin_err = ComputeLinearity(mypath)
    with open(f"{mypath}/Experiment_data.txt", 'r') as Exp_data:
        expLines = Exp_data.readlines()
        for i in expLines:
            id = i.split('=')[0]
            value = i.split('=')[1].strip()
            if id == "Preamp_gain(Ohm)" : preamp = value
            elif id == "PMT_high_voltage(V)" : hv = value
            elif id == "PMT_Serial" : serial = value
            elif id == "Chopper_Frequency(Hz)" : frq = value
            elif id == "Constant_LED(V)" : vol = value
            elif id == "Cathode_Current_at_max_brightness(nA)" : I_cathode = value

    if (preamp == "1M"): gain = 1000
    else: gain = int(preamp[0:-1])

    x = (x/gain)*1000 
    x_err = (x_err/gain)*1000

    if res==0:        
        fig,axs = plt.subplots(2,1, figsize=(10,7),layout='constrained',sharex=True)

        axs[0].errorbar(x, y, yerr=y_err, fmt='r.',  markersize=5 ,elinewidth=2, capsize=4, ecolor='k', lw=0, label='LED Asymmetry')
        axs[0].plot(x,y_fit_linear,label='Linear fit',c='tab:blue')
        # ax.plot(x,y_fit_sec,label='Second ord. fit', c='tab:purple', linestyle='--')
        axs[0].set_ylabel(r"$A_{LED}$",fontsize=15)

        axs[0].set_title(f"",fontsize=18)
        axs[0].grid(linestyle='--')
        axs[0].xaxis.set_minor_locator(AutoMinorLocator())
        axs[0].yaxis.set_minor_locator(AutoMinorLocator())
        plt.suptitle("PMT non-linearity measurement", fontsize=16)
        axs[0].set_title(fr" PMT:{serial}, Pre-amp:{preamp}Ω, HV:-{hv}V, Frequency:{frq}Hz, $I_{{cathode}}@maxBrightness:{I_cathode}nA$",fontsize=12)

        axs[0].tick_params(axis='x', labelsize=11)
        axs[0].tick_params(axis='y', labelsize=11)
        
        s=0.005
        y_min = np.mean(y)-s
        y_max = np.mean(y)+s
        for k,point in enumerate(y):
                if point >= y_max:
                    axs[0].scatter(x[k],y_max*0.98, marker='$↑$', c='k')
                if point <= y_min:
                    axs[0].scatter(x[k],y_min*1.02, marker='$↓$', c='k')

        # logging.info(f"{'✅ ' if abs(lin*100) < 0.51 else ''}{serial}:({timeStamp}) - Non_linearity = ({(lin)*100:.3f} ± {(abs(lin_err))*100:.3f}) % ")
        axs[0].legend(title=f"% non-lin= {(lin)*100:.2f}±{(abs(lin_err))*100:.2f}" "\n" rf"$ \chi ^2 / ndf\ =$ {chisqr:.1f}/{ndf}",fontsize=12)

        axs[0].set_ylim(y_min, y_max)


        Calculate_Asymmetry.addOrReplaceLine(mypath,'Non-Linearity(%)',f'{(lin)*100:.2f}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Non-Linearity_Uncertainty(%)',f'{(abs(lin_err))*100:.2f}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Linear_Fit_Chi_Square',f'{chisqr:.1f}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Linear_Fit_degrees_of_freedom',f'{ndf}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Minimum_Anode_Current(uA)',f'{np.min(x):.2f}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Maximum_Anode_Current(uA)',f'{np.max(x):.2f}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'X-Anode_Current(uA)',f'{x.tolist()}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Y-Asymmetry',f'{y.tolist()}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Asymmetry_Uncertainty',f'{y_err.tolist()}')
        Calculate_Asymmetry.addOrReplaceLine(mypath,'Anode_Current_Uncertainty(uA)',f'{x_err.tolist()}')

        # iter_list = np.arange(0,len(y))
        # comb = combinations(iter_list, 2) # calculating the combinations selecting 2 from 9 objects (n=9, r=2,nCr=36)

        comb=[]
        for i in range(8):
            comb.append((i, i+1))

        dAdI=[]
        dAdI_err=[]
        Im = []
        for i,u in list(comb):
            div,div_err = division_with_uncertainty((y[u]-y[i]), (y_err[u]+y_err[i]), (x[u]-x[i]), (x_err[u]+x_err[i]))
            dAdI_err.append(div_err)
            dAdI.append(div)
            Im.append((x[u]+x[i])/2)

        params,cov = curve_fit(constFunc,Im,dAdI, sigma=dAdI_err, p0=[0], absolute_sigma=True) # set initial guesses of intercept to mean of the asymmetries and 0 for slope
        mean_dAdI = params[0]
        mean_dAdI_err = np.sqrt(np.diag(cov))[0] #  fit error

        # mean_dAdI = np.mean(dAdI)
        # mean_dAdI_err = np.sqrt(np.sum(np.array(dAdI_err)**2))/len(dAdI_err)

        axs[1].errorbar(Im, dAdI, yerr=dAdI_err, fmt='r.',  markersize=5 ,elinewidth=2, capsize=4, ecolor='k', lw=0, label=r'$\Delta A /\Delta I$')
        axs[1].set_ylabel(r'$\Delta A_{LED} / \Delta I_{Anode}} (\mu A^{-1})$',fontsize=15)
        axs[1].set_xlabel(r"$I_{anode}\ (μA)$", fontsize=15)
        # axs[1].set_title(r'$\frac{\Delta A_{LED}}{\Delta I_{Anode}}}$' + ' vs. ' + r'$I_{Anode}}$', fontsize=16)
        axs[1].set_ylim(np.mean(dAdI)-s, np.mean(dAdI)+s)
        axs[1].grid(linestyle='--')
        axs[1].xaxis.set_minor_locator(AutoMinorLocator())
        axs[1].yaxis.set_minor_locator(AutoMinorLocator())
        axs[1].tick_params(axis='x', labelsize=11)
        axs[1].tick_params(axis='y', labelsize=11)
        dAdI_title = fr"$dA/dI_{{mean}} $= ({mean_dAdI*100*1000:.2f} ± {mean_dAdI_err*100*1000:.2f})x10⁻³ %μA⁻¹"
        axs[1].legend(title=dAdI_title,fontsize=12)

        fig.savefig(f"{mypath}/Non_linearity.pdf")

        logging.info(dAdI_title)

        A_max = np.max(x)
        if A_max > anode_current_max:
            logging.warning(f"🟡 {serial}:({timeStamp}) - High anode current detected: max(I_anode)={A_max:.2f} μA is higher than {anode_current_max} μA")
            sys.exit(2)
        elif A_max < anode_current_min:
            logging.warning(f"🟡 {serial}:({timeStamp}) - Low anode current detected max(I_anode)={A_max:.2f} μA is lower than {anode_current_min} μA")
            sys.exit(3)
        else:
            logging.info("Analysis successful")
            sys.exit(0)
    else:
        logging.error(f"🔴 {serial}:({timeStamp}) - Tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
