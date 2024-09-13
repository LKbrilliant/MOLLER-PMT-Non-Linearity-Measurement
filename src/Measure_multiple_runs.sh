#!/bin/bash
# Code by:    Anuradha Gunawardhana
# Date:       2024.08.02
# Details:    This script is used to record multiple linearity tests consecutively.

base_dir='Test_Data'
filter_order=( '4' '11' '8' '2' '9' '7' '3' '5' '1' '6' '10' '12' )
pedestal_count=0
directoryCreated=false
SECONDS=0

function usage {
  echo ""
  echo " -----------------------------------------------------"
  echo "|  MOLLER PMT Multiple Linearity Measurement : Usage  |"
  echo " -----------------------------------------------------"
  echo ""
  echo "Code by: Anuradha Gunawardhana"
  echo "Date: 10.06.2024"
  echo "Version: 0.4"
  echo ""
  echo "Usage: $0 -vc|--vconst <voltage> -vb|--vblink <voltage> -hv|--highVolt <voltage> -f|--frequency <freq> -g|--gain <preamp-gain> -s|--serial <serial> -ts|--timeStamp <time-stamp> -d|--dir <directory>"
  echo ""
  echo "Options:"
  echo "  -vc, --vconst     Constant LED voltage (0-5)V."
  echo "  -vb, --vblink     Blinking LED voltage (0-5)V"
  echo "  -hv, --highVolt   PMT high voltage (0-1000)V"
  echo "  -f,  --frequency  Chopper frequency (0-3000)Hz"
  echo "  -g,  --gain       Pre-amp gain setting (20k, 100k, 200k, 1M)"
  echo "  -s,  --serial     PMT serial number"
  echo "  -b,  --base       Number of stages in the base (3,4)"
  echo "  -Ic, --Icahode    Cathode current at max brightness (100% light transmission)"
  echo "  -ts, --timeStamp  Time stamp of PMT powerd on time (YYYYMMDDhhmm)"
  echo "  -tr, --testRun    Test run or not (true,false)"
  echo "  -r,  --runs       Test run or not (true,false)"
  echo "  -d,  --dir        [Optional] Data directory name. Will create a folder -d inside 'base_dir'"

  exit 1
}

while [[ $# -gt 0 ]] ; do
  case "$1" in
    -vc | --vconst)
      VC="$2"
      shift
      shift
      ;;
    -vb | --vblink)
      VB="$2"
      shift
      shift
      ;;
    -hv | --highVolt)
      HV="$2"
      shift
      shift
      ;;
    -f | --frequency)
      FRQ="$2"
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
    -d | --dir)
      DIR="$2"
      shift
      shift
      ;;
    -Ic | --Icathode)
      I_Cathode="$2"
      shift
      shift
      ;;
    -ts | --timeStamp)
      DATETIME="$2"
      shift
      shift
      ;;
    -tr | --testRun)
      TEST="$2"
      shift
      shift
      ;;
    -r | --runs)
      RUNS="$2"
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

# Check for missing (NULL) inputs
if [ -z "$VC" ] || [ -z "$VB" ] || [ -z "$HV" ] || [ -z "$FRQ" ] || [ -z "$GAIN" ] || [ -z "$SERIAL" ] || [ -z "$DATETIME" ] || [ -z "$BASE" ] || [ -z "$I_Cathode" ] || [ -z "$TEST" ] || [ -z "$RUNS" ]; then
  echo "[ERROR] Missing required options"
  usage
fi

# Check for invalid inputs (non-numeric)
for u in $VC $VB $HV $FRQ $TIME $BASE $I_Cathode $RUNS ; do
  if ! [[ "$u" =~ ^[0-9]+([.][0-9]+)?$ ]] ; then
    echo "[ERROR] Invalid value: $u"
    usage
  fi
done

if [ "$TEST" != "true" ] && [ "$TEST" != "false" ] ;then 
  echo "[ERROR] Invalid value for testRun: $TEST"
  echo "[Options]: true, false"
  usage
fi

if [ "$I_Cathode" != "7" ] && [ "$I_Cathode" != "9" ] && [ "$I_Cathode" != "12" ] && [ "$I_Cathode" != "15" ] && [ "$I_Cathode" != "18" ] ; then
  echo "[ERROR] Invalid value for cathode current: $I_Cathode"
  echo "[Options]: 7, 9, 12, 15, 18"
  usage
fi

if [ "$GAIN" != "20k" ] && [ "$GAIN" != "100k" ] && [ "$GAIN" != "200k" ] && [ "$GAIN" != "200k" ] ; then
  echo "[ERROR] Invalid value for preamp gain: $GAIN"
  echo "[Options]: 20k, 100k, 200k, 1M"
  usage
fi

if [ ${#SERIAL} -gt 8 ]; then
  echo "[ERROR] Invalid value for PMT serial: $SERIAL"
  echo "[Options]: XXX-XXX or XXX-XXXX"
  usage
fi

if [ "$BASE" != "3" ] && [ "$BASE" != "4" ] ; then
  echo "[ERROR]: Invalid value for number of stages in the base: $BASE"
  echo "[Options]: 3, 4"
  usage
fi

DATE=${DATETIME:0:8}
TIME=${DATETIME:8:12}

if [ ${#DATETIME} != 12 ] || [ ${DATE:0:4} -lt 2024 ] || [ ${DATE:4:2} -gt 12 ] || [ ${DATE:6:8} -gt 31 ] || [ $TIME -gt 2359 ] || [ ${TIME:0:2} -gt 23 ] || [ ${TIME:2:2} -gt 59 ]; then
  echo "[ERROR] Invalid value for PMT turned on time stamp: $DATETIME"
  usage
fi

echo "------------------------------------------------"
echo "|         Initiating the data collection       | "
echo "------------------------------------------------"
# Set LED voltages
STD_OUT="$(python Power_Supply_Control.py -v $VC $VB)"
if [ $? -eq "1" ] ; then
  echo "[Recording Failed] Power supply failed!"
  exit 1
fi

echo "$STD_OUT"
IFS=', ' read -ra val <<< "$STD_OUT" # Separating string
I_PMT=${val[5]} # PMT base current
IC=${val[13]} # Constant LED current draw

if [[ -z "$DIR" ]];
then
  DIRNAME=./$base_dir/Multiple_runs/$SERIAL/`date +"%Y%m%d%H%M"`
else
  DIRNAME=./$base_dir/$DIR/$SERIAL/`date +"%Y%m%d%H%M"`
fi

# Set Chopper frequency
python Chopper_Control.py -c setFrequency $FRQ
if [ $? -eq "1" ] ; then
  echo "[Recording Failed] Could not initiate the Chopper!"
  exit 1
fi

# Inirial pedestal run

echo ""
echo "------------------------------------------------"
echo "|  New record | Run 0 -- Filter position 12   |"
echo "------------------------------------------------"
echo "[Wait]: Setting filter position: 12"
python Filter_Control.py -c setPosition 12
if [ $? -eq "1" ] ; then
  echo "[Recording Failed] Moving filter into position!"
  exit 1
fi

echo "[CMData] Running"
./CMData
rm *.dat
rm *.out

echo "[CMData] Recording successful!"

echo "[Record Saving]: Creating data directory: $DIRNAME"
mkdir -p $DIRNAME
touch $DIRNAME/Temp_data.txt

echo "[Record Saving]: Copying files to: $DIRNAME "
mv ./Int_Run_000.root $DIRNAME/Run-0-F12.root
sleep 1


# Start filter cycle
for (( u=1; u<=RUNS; u++ ))
  do
  python Multiple_read_temp.py $DIRNAME
  for (( i=1; i<=12; i++ ))
    do
        echo ""
        echo "------------------------------------------------"
        echo "|  New record | Run $u -- Filter position $i   |"
        echo "------------------------------------------------"
        echo "[Wait]: Setting filter position: $i"
        python Filter_Control.py -c setPosition $i
        if [ $? -eq "1" ] ; then
          echo "[Recording Failed] Moving filter into position!"
          exit 1
        fi

        echo "[CMData] Running"
        ./CMData
        rm *.dat
        rm *.out

        echo "[CMData] Recording successful!"

        # if [ "$directoryCreated" = false ] ; then
        #   echo "[Record Saving]: Creating data directory: $DIRNAME"
        #   mkdir -p $DIRNAME
        #   touch $DIRNAME/Temp_data.txt  # Create an empty text file to save temp data
        #   directoryCreated=true
        # fi
        echo "[Record Saving]: Copying files to: $DIRNAME "
        mv ./Int_Run_000.root $DIRNAME/Run-$u-F${filter_order[$i-1]}.root
        sleep 1
  done
done
cp ./CMDataSettings.txt $DIRNAME
echo "================================================"
echo "                  Record End                    "
echo "  Data dir:       $DIRNAME                      "
echo "  Time escape:    $SECONDS seconds              "
echo "================================================"
echo ""
echo ""

echo "Filter_Order=4,11,8,2,9,7,3,5,1,6,10,12
Test_Run=$TEST
Multiple_Runs=True
PMT_Power_On_Timestamp(DateTime)=$DATETIME
PMT_Current(mA)=$I_PMT
PMT_Base_Stages=$BASE
PMT_Serial=$SERIAL
Chopper_Frequency(Hz)=$FRQ
Constant_LED(V)=$VC
Constant_LED(mA)=$IC
Flashing_LED(V)=$VB
PMT_high_voltage(V)=$HV
Preamp_gain(Ohm)=$GAIN
Cathode_Current_at_max_brightness(nA)=$I_Cathode
Record_Time(s)=$SECONDS" >> $DIRNAME/Experiment_data.txt

exit 0