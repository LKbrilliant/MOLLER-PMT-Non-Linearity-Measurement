# Code by:      Anuradha Gunawardhana
# Date:         2023.11.22 
# Description:  Connect to the BK PRECISION 9129B 3-channel power supply over the usb (using an TTL to USB converter) and
#               take readings or execute commands

import serial
import time
import serial.tools.list_ports
import argparse
import sys

def main():
    counter = 0
    debug = False
    Imax_PMT = 1
    Imax_LED = 0.03
    # I_PMT_operational = 400
    I_PMT_operational = 120

    # V_PMT = 5.6
    V_PMT = 10
    Vmax_LED = 5
    V_constLED = 0
    V_flashingLED = 0

    parser = argparse.ArgumentParser(prog='Power Supply Control v0.1',
                                     description='Communicate with BK PRECISION 9129B 3 Channel Power supply. Code by: Anuradha Gunawardhana')
    parser.add_argument("-c",
                        help="Perform actions. Commands: [model, beep, outputON, outputOFF]")
    
    parser.add_argument("-v",
                        nargs=2,
                        help="Set the voltage for the two LEDs.")
    
    parser.add_argument("-ri",
                        help="Read current")
    
    parser.add_argument("-rv",
                        help="Read voltage")

    args = parser.parse_args()
    if args.v:
        V_constLED, V_flashingLED = args.v
        if float(V_constLED) > Vmax_LED or float(V_flashingLED) > Vmax_LED : print(f"[PowerSupply Warning]: Maximum voltage limit detected. Vmax={float(Vmax_LED):.2f} V")
        if float(V_constLED) > Vmax_LED: V_constLED = Vmax_LED       #Setting the voltage limit for LEDs
        if float(V_flashingLED) > Vmax_LED: V_flashingLED = Vmax_LED

    cmds = {"model": '*IDN?',
            "beep": 'SYST:BEEP',
            "outStatus": 'OUTP:STAT?',
            "remoteDisabled": 'SYST:LOC',
            "remoteEnabled": 'SYST:REM',
            "setCurrentLimit": f'APP:CURR {Imax_PMT},{Imax_LED},{Imax_LED}',
            "setVoltage": f'APP:VOLT {V_PMT},{V_flashingLED},{V_constLED}', # CH1:PMT,  CH2:Flashing LED, CH3:Constant LED,
            "outputON": 'OUTP:STAT 1',
            "outputOFF": 'OUTP:STAT 0',
            "readCurrent":'MEAS:CURR:ALL?',
            "readVolt" : "MEAS:ALL?"}

    ports = serial.tools.list_ports.comports()
    if ports == []:
        print("[PowerSupply Error]: No serial devices detected!")
        sys.exit(1)

    else:
        for port, desc, hwid in sorted(ports):
            if debug: print(port, desc, hwid)
            if "067B:2303" in hwid: #Hardware id for the TTL to USB converter
                ser = serial.Serial(port, 38400,timeout=1) # Need to to set baud rate value on the Power supply on the MENU
                if debug: print("[PowerSupply]: Wait - Opening the serial port!")
                if ser.is_open: 
                    if debug: print("[PowerSupply]: Port is already open!")
                else:
                    ser.open()
                    if ser.is_open and debug: print("[PowerSupply]: Port is Open!")
                
                def setCommand(n):
                    p = str.encode(cmds[n]+'\n') # encode string as byte
                    ser.write(p)
                    ser.reset_output_buffer()
                    time.sleep(.1)

                    line = (str(ser.read_until('\r')))[2:-5]
                    q = line.split('\\r')
                    return q[-1]
                
                setCommand("remoteEnabled") # Allow remote access
                if args.c:setCommand(args.c)
                elif args.v:
                    setCommand("setCurrentLimit")
                    setCommand("setVoltage")
                    setCommand("outputON")
                    s = setCommand("readVolt")
                    while(s == ''): # no response
                        print('[Power Supply Failed]: Couldn\'t set the voltage!')
                        setCommand("readVolt")
                        counter+=1
                        if (counter == 1):
                            print('[Power Supply EXIT]: Failed to set the voltage.')
                            sys.exit(1)
                        time.sleep(1)
                    if float(s.split(",")[0]) == 0: setCommand("outputON")
                    q = setCommand("readVolt")
                    r = setCommand("readCurrent")
                    vpmt = float(0 if q.split(",")[0]=='' else q.split(",")[0])
                    vconst = float(0 if q.split(",")[1]=='' else q.split(",")[1])
                    vblink = float(0 if q.split(",")[2]=='' else q.split(",")[2])

                    Ipmt = float(0 if r.split(",")[0]=='' else r.split(",")[0])*1000
                    Iconst = float(0 if r.split(",")[1]=='' else r.split(",")[1])*1000
                    Iblink = float(0 if r.split(",")[2]=='' else r.split(",")[2])
                    print(f'[PowerSupply Done]: Measured ch1:[{vpmt:.2f} V, {Ipmt:.2f} mA], ch2:[{vconst:.2f} V, {Iconst} mA], ch3:[{vblink:.2f} V, {Iblink} mA]')
                    baseImax = I_PMT_operational*1.1
                    baseImin = I_PMT_operational*0.9
                    time.sleep(.2)
                    if (Ipmt >= baseImax or Ipmt < baseImin):
                        print('[PowerSupply Warning]: PMT current anomaly detected')
                        print('[PowerSupply] Turning off')
                        setCommand("outputOFF")
                        sys.exit(1)

                elif args.ri:
                    q = setCommand("readCurrent")
                    ch = int(args.ri)-1
                    x = q.split(',')[ch]
                    print(f'Current: Ch{ch+1} = {x if x!="" else "NULL"}' )
                elif args.rv:
                    q = setCommand("readVolt")
                    ch = int(args.rv)-1
                    x = q.split(',')[ch]
                    print(f'Voltage: Ch{ch+1} = {x if x!="" else "NULL"}' )
                setCommand("remoteDisabled") # Enable local control

                ser.close()
                sys.exit(0)

        print("[PowerSupply Failed]: BK PRECISION 9129B power supply not detected!")
        sys.exit(1)

if __name__ == "__main__":
    main()
