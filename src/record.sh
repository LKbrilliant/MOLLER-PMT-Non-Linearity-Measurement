#!/bin/bash
# Details:    The script will depend on several python scripts and MOLLER ADC readout program(CMData) to 
#             cycle through the 12 filter positions for data collection and analysis to calculate the non-
#             linear behaviour of MOLLER PMTs. require main.sh to function
# Code by:    Anuradha Gunawardhana
# Date:       2024.06.06

FRQ=(1920 960) # Chopper frequencies to test 
WARMUP=2 # Usual PMT warmup time
function usage {
  echo ""
  echo "--------------------------------------------------"
  echo "|  MOLLER PMT Non-Linearity Measurement : Usage  |"
  echo "--------------------------------------------------"
  echo ""
  echo "Code by: Anuradha Gunawardhana"
  echo "Date: 03.06.2024"
  echo "Version: 0.4"
  echo ""
  echo "Usage: $0 -s|--serial <serial> -hv|--highVolt <voltage> -g|--gain <preamp-gain> -ts|--timeStamp <time-stamp>"
  echo "          -b|--base <Base-stages> -on|--overnight <wait-hours> -v7|--VLEDat7nA <V_LED@7nA_Cathode> -v9|--VLEDat9nA <V_LED@9nA_Cathode> " 
  echo "          -v12|--VLEDat12nA <V_LED@12nA_Cathode> -v15|--VLEDat15nA <V_LED@15nA_Cathode> -v18|--VLEDat18nA <V_LED@18nA_Cathode>"
  echo ""
  echo "Options:"
  echo "  -s,   --serial        PMT serial number"
  echo "  -v7,  --VLEDat7nA     LED voltage at 7nA cathode current"
  echo "  -v9,  --VLEDat9nA     LED voltage at 9nA cathode current"
  echo "  -v12, --VLEDat12nA    LED voltage at 12nA cathode current"
  echo "  -v15, --VLEDat15nA    LED voltage at 15nA cathode current"
  echo "  -v18  --VLEDat18nA    LED voltage at 18nA cathode current"
  echo "  -b,   --base          [Optional] Number of stages in the base (3,4)(default=3)"
  echo "  -on   --overnight     [Optional] set overnight wait time duting runs (min=2) if larger than minimum, will do a test at 2 and (waitTime -2)h"
  echo "  -hv,  --highVolt      [Optional] PMT high voltage (0-1000)(default=-800V)V"
  echo "  -g,   --gain          [Optional] Pre-amp gain setting (20k, 100k, 200k, 1M)(default=200k) "
  echo "  -ts,  --timeStamp     [Optional] Time stamp of PMT powerd on time (YYYYMMDDhhmm)"

  exit 1
}

function timer (){
  waitTime=$((3600 * $@)) # 3600 = 1 hour
  while [ $waitTime -gt 0 ] ; do
    printf "\rWaiting: %02d:%02d:%02d" $((waitTime/3600)) $(( (waitTime/60)%60)) $((waitTime%60))
    sleep 1
    waitTime=$((waitTime-1))
  done
}

echo "==========================================="
echo "|  PMT Non-Linearity Measurment for MOLLER |"
echo "==========================================="

while [[ $# -gt 0 ]] ; do
  case "$1" in
    -hv | --highVolt)
      HV="$2"
      shift
      shift
      ;;
    -g | --gain)
      GAIN="$2"
      shift
      shift
      ;;
    -s | --serial)
      SERIAL="$2"
      shift
      shift
      ;;
    -b | --base)
      BASE="$2"
      shift
      shift
      ;;
    -ts | --timeStamp)
      DATETIME="$2"
      shift
      shift
      ;;
    -on | --overnight)
      WAIT="$2"
      shift
      shift
      ;;
    -v7 | --VLEDat7nA)
      V7="$2"
      shift
      shift
      ;;
    -v9 | --VLEDat9nA)
      V9="$2"
      shift
      shift
      ;;
    -v12 | --VLEDat12nA)
      V12="$2"
      shift
      shift
      ;;
    -v18 | --VLEDat18nA)
      V18="$2"
      shift
      shift
      ;;
    -v15 | --VLEDat15nA)
      V15="$2"
      shift
      shift
      ;;
    -h | --help)
      usage
      shift
      ;;
    *)
      echo "Invalid option: $1"
      usage
  esac
done

# Checke for optional inputs
if [ -z "$SERIAL" ] ; then
  echo "[ERROR] Missing required options"
  usage
fi

if [ -z "$HV" ] ; then
  if [ -z "$BASE" ] ; then
    BASE=3
    baseDIR="3-Stage"
    HV=800
    echo "[INFO] Using default Base with $BASE stages"
    echo "[INFO] Using default HV: -$HV V"
  elif [ $BASE -eq 4 ] ; then
    HV=600
    baseDIR="4-Stage"
    echo "[INFO] Using default HV for the 4 stage base: -$HV V"
  elif [ $BASE -eq 3 ] ; then
    HV=800
    baseDIR="3-Stage"
    echo "[INFO] Using default HV for the 3 stage base: -$HV V"
  fi
fi

if [ -z "$BASE" ] ; then
  BASE=3
  baseDIR="3-Stage"
  echo "[INFO] Using default Base with $BASE stages"
else
  baseDIR="$BASE-Stage"
fi

if [ -z "$GAIN" ]  ; then
  GAIN=200k
  echo "[INFO] Using default preamp gain: $GAIN kΩ"
fi

if [ -z "$WAIT" ]  ; then
  WAIT=$WARMUP
  echo "[ERROR] Using the default warmup time: $WAIT h"
fi

# Check for invalid inputs (non-numeric)
# for u in $HV $FRQ $TIME $BASE; do
for u in $HV $TIME $BASE; do
  if ! [[ "$u" =~ ^[0-9]+([.][0-9]+)?$ ]] ; then
    echo "[ERROR] Invalid value: $u"
    usage
  fi
done

if [ "$GAIN" != "20k" ] && [ "$GAIN" != "100k" ] && [ "$GAIN" != "200k" ] && [ "$GAIN" != "200k" ] ; then
  echo "[ERROR] Invalid value for preamp gain: $GAIN"
  echo "[Options]: 20k, 100k, 200k, 1M"
  usage
fi

if [ ${WAIT} -lt 2 ] ; then
  echo "[Warning] Wait time need to be at least $WARMUP h. Using default warmup time: $WARMUP h"
  WAIT=$WARMUP
fi

if [ ${#SERIAL} -gt 8 ] || [ ${#SERIAL} -lt 7 ]; then
  echo "[ERROR] Invalid value for PMT serial: $SERIAL"
  echo "[Options]: XXX-XXX or XXX-XXXX"
  usage
fi

if [ "$BASE" != "3" ] && [ "$BASE" != "4" ] ; then
  echo "[ERROR]: Invalid value for number of stages in the base: $BASE"
  echo "[Options]: 3, 4"
  usage
fi
# if [ $BASE -eq 3 ] && [ -z "$V12" ] || [ -z "$V18" ] || [ -z "$V15" ] ; then
if [[ $BASE -eq 3 && ( -z "$V12" || -z "$V18" || -z "$V15" ) ]] ; then
    echo "[ERROR] Missing required options"
    usage
elif [[ $BASE -eq 4 && ( -z "$V7" || -z "$V9" || -z "$V12" ) ]] ; then
    echo "[ERROR] Missing required options"
    usage
fi

opts=`date +"%Y%m%d%H%M"`
if [ -z "$DATETIME" ] ; then
  echo "[INFO]: Taking the current Data&Time($opts), as the PMT turn on time."
  read -p  "Press 'Enter' to start the data collection:"
  DATETIME=$opts
else
  DATE=${DATETIME:0:8}
  TIME=${DATETIME:8:12}

  if [ ${#DATETIME} != 12 ] || [ ${DATE:0:4} -lt 2024 ] || [ ${DATE:4:2} -gt 12 ] || [ ${DATE:6:8} -gt 31 ] || [ $TIME -gt 2359 ] || [ ${TIME:0:2} -gt 23 ] || [ ${TIME:2:2} -gt 59 ]; then
    echo "[ERROR] Invalid value for PMT turned on time stamp: $DATETIME"
    usage
  fi
fi

su=0.01 #0.02 ~ 1% voltage change
if [ $BASE -eq 3 ] ; then
  V_l15=$(echo "scale=2; $V15-$su" | bc)
  V_h15=$(echo "scale=2; $V15+$su" | bc) # floating point addition
  VC=($V12  $V15  $V18  $V15  $V15) # CH2:Flashing LED, CH3:Constant LED
  VB=($V12  $V15  $V18  $V_l15  $V_h15) # Voltage perturbation sequence for constant and blining LEDs
  Ic_order=(12 15 18 15 15) # Order of cathode currents used for testing (nA)
elif [ $BASE -eq 4 ] ; then
  V_l9=$(echo "scale=2; $V9-$su" | bc)
  V_h9=$(echo "scale=2; $V9+$su" | bc) # floating point addition
  V7_low=$(echo "scale=2; $V7-0.01" | bc)
  V9_low=$(echo "scale=2; $V9-0.03" | bc)
  V12_low=$(echo "scale=2; $V12-0.03" | bc)
  VC=($V7  $V9  $V12  $V9  $V9) # CH2:Flashing LED, CH3:Constant LED
  VB=($V7_low $V9_low $V12_low $V_l9  $V_h9) # Voltage perturbation sequence for constant and blining LEDs
  Ic_order=(7 9 12 9 9) # Order of cathode currents used for testing (nA)
fi

# Initiate the data collection by preforming first test run at 15nA cathode current level
./max_anode_current_test.sh -vc ${VC[1]} -hv $HV -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -d $baseDIR -Ic ${Ic_order[1]} -tr true
status=$?
if [ $status -eq "1" ] ; then
  exit 1
fi

#Check whether the max anode current is in the correct range
while [ $status -eq "2" ] || [ $status -eq "3" ] ; do # Catch high anode current situation from the previous analysis
  python Power_Supply_Control.py -c beep # Make a beep sound from the power supply
  if [ $status -eq "2" ] ; then
    echo "[Suggestion]: Try decreasing the PMT high-voltage"
  fi
  if [ $status -eq "3" ] ; then
    echo "[Suggestion]: Try increasing the PMT high-voltage"
  fi
  read -p "New PMT high-voltage: " HV
  read -p "After changing the high-voltage press enter to continue: "
  ./max_anode_current_test.sh -vc ${VC[1]} -hv $HV -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -d $baseDIR -Ic ${Ic_order[1]} -tr true
  status=$?
done

# Do a full test run
./main.sh -vc ${VC[1]} -vb ${VB[1]} -hv $HV -f ${FRQ[0]} -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -d $baseDIR -Ic ${Ic_order[1]} -tr true

# Do the perturbation runs after 2h. Take this run as the official run
if [ $WAIT -gt $WARMUP ] ; then # If not overnight
  echo ""
  timer $WARMUP
  echo ""
  for f in "${!FRQ[@]}"; do # Go through different frequencies
    for i in "${!VC[@]}"; do # Change the max cathode current
      ./main.sh -vc ${VC[i]} -vb ${VB[i]} -hv $HV -f ${FRQ[f]} -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -d $baseDIR -Ic ${Ic_order[i]} -tr false
      if [ $? -eq "1" ] ; then
        exit 1
      fi
    done
  done
  ./Measure_multiple_runs.sh -vc ${VC[1]} -vb ${VB[1]} -hv $HV -f ${FRQ[0]} -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -Ic ${Ic_order[1]} -tr true -r 20 
fi

# Do another perturbation run after overnight warmup (mark as a test run).
while true ; do
  echo ""
  if [ $WAIT -gt $WARMUP ] ; then
    timer $(($WAIT - $WARMUP))
  else
    timer $WARMUP
  fi
  echo ""
  for f in "${!FRQ[@]}"; do # Go through different frequencies
    for i in "${!VC[@]}"; do # Change the max cathode current
      ./main.sh -vc ${VC[i]} -vb ${VB[i]} -hv $HV -f ${FRQ[f]} -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -d $baseDIR -Ic ${Ic_order[i]} -tr true
      if [ $? -eq "1" ] ; then
        exit 1
      fi
    done
  done
  ./Measure_multiple_runs.sh -vc ${VC[1]} -vb ${VB[1]} -hv $HV -f ${FRQ[0]} -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -Ic ${Ic_order[1]} -tr true -r 20 
  # ./Measure_anode_currents.sh -vs 2.58 -ve 2.94 -st 0.02 -hv $HV -g $GAIN -s $SERIAL -b $BASE -ts $DATETIME -tr true
done
