# Code by:    Anuradha Gunawardhana
# Date:       2023.08.08 
# Description: Connect to the Thorlabs FW102C 12 position filter wheel and execute commands over serial

import serial
import time
import serial.tools.list_ports
import argparse
import sys

debug = False

def main():
    counter = 0

    parser = argparse.ArgumentParser(prog='Filter Control v0.1',
                                     description='Communicate with Thorlabs filter-wheel FW212CNEB. Code by: Anuradha Gunawardhana')

    parser.add_argument("-r",
                        metavar="request",
                        help="Request information from the filter. Choices:[model, baudRate, filterCount, currentPosition, triggerMode, speed, sensors]")

    parser.add_argument("-c",
                        nargs=2,
                        metavar=("Command", "{value}"),
                        help="Send commands to the filter wheel. Choices:[setPosition <1-12>, setFilterCount <6/12>, setTrigger <0/1>(input/output), setSpeed <0/1>(slow/high), setSensors <0/1>(off/on), setBaud <0/1>(9600/115200), saveCurrent")

    args = parser.parse_args()

    info = {"model" : '*idn?',
            "baudRate" : 'baud?',           # 0=9600, 1=115200
            "filterCount" : 'pcount?',      # 6 filters, 12 filters
            "currentPosition" : 'pos?',     # 1-12
            "triggerMode" : 'trig?',        # 0=inputMode, 1=outputMode
            "speed" : 'speed?',              # 0=slow, 1=high
            "sensors" : 'sensors?'}          # 0=sensor lights Off, 1=sensor lights On

    cmds = {"setPosition" : 'pos=',         # 1-12
            "setFilterCount" : 'pcount=',    # 6, 12
            "setTrigger" : 'trig=',          # 0=inputMode 1=OutputMode
            "setSpeed" : 'speed=',           # 0=slow , 1=high
            "setSensors" : 'sensors=',       # 0=sensor lights Off, 1=sensor lights On
            "setBaud" : 'baud=',             # 0=9600, 1=115200
            "save" : 'save'}

    ports = serial.tools.list_ports.comports()
    if ports == []:
        print("[Filter Error]: No serial devices detected!")
        sys.exit(1)

    else:
        for port, desc, hwid in sorted(ports):
            if desc == "FW102C - FW102C" :
                ser = serial.Serial(port, 115200, timeout=1)
                if debug: print("[Filter]: Wait - Opening the filter wheel serial port!")
                if ser.is_open: 
                    if debug: print("[Filter]: Port is already open!")
                else:
                    ser.open()
                    if ser.is_open and debug: print("[Filter]: Port is Open!")
                def getInfo(n):
                    p = str.encode(info[n]+'\r') # encode string as byte
                    ser.write(p)
                    ser.reset_output_buffer()
                    time.sleep(.1)

                    line = (str(ser.read_until('\r')))[2:-5]
                    q = line.split('\\r')
                    print(f'[Filter INFO]: {n} - {q[-1]}' )
                    return q[-1]

                def setCmd(cmd,val):
                    p = str.encode(cmds[cmd]+str(val)+'\r') # encode string as byte
                    ser.write(p)
                    ser.reset_output_buffer()
                    time.sleep(.2)
                    print(f'[Filter ACTION]: {cmd} - {val}' )
                    ser.reset_output_buffer()

                if args.r:
                    out = getInfo(args.r)
                    if out != "":
                        ser.close()
                        sys.exit(0)

                if args.c:
                    command, value = args.c
                    setCmd(command, value)
                    if command == "setPosition":
                        time.sleep(3)
                        while(getInfo('currentPosition') != value):
                            print('[Filter Failed]: Moving to position. Retrying..')
                            setCmd(command, value)
                            counter+=1
                            if (counter == 10):
                                print('[Filter EXIT]: Failed to move into position.')
                                sys.exit(1)
                            time.sleep(1)

                        print('[Filter Done]: Moving to position')
                        ser.close()
                        sys.exit(0)

        print("[Filter Failed]: Thorlabs FW2112CNEB filter wheel not detected!")
        sys.exit(1)

if __name__ == "__main__":
    main()
