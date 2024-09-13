# Code by:    Anuradha Gunawardhana
# Date:       2023.08.08
# Description: Connect to the Thorlabs MC2000B chopper controller and execute commands over serial

import serial
import time
import serial.tools.list_ports
import argparse
import sys

debug = False

def main():
    counter = 0

    parser = argparse.ArgumentParser(prog='Chopper Control v0.1',
                                     description='Communicate with Thorlabs Optical chopper MC2000B. Code by: Anuradha Gunawardhana')

    parser.add_argument("-r",
                        metavar="request",
                        help="Request information from the Chopper. Choices:[model, baud_rate, filter_count, current_position, trigger_mode, speed, sensors]")

    parser.add_argument("-c",
                        nargs=2,
                        metavar=("Command", "{value}"),
                        help="Send commands to the Chopper Choices:[setPosition {1-12}, setChopperCount {6/12}, setTrigger {0/1}{input/output}, setSpeed {0/1}{slow/high}, setSensors {0/1}{off/on}, setBaud {0/1}{9600/115200}, saveCurrent")

    args = parser.parse_args()

    info = {"model" : '*idn?',
            "getFrequency" : 'freq?',        # 0 - 3000
            "getBlade" : 'blade?',          # 3 = MC1F30
            "getEnable" :"enable?"}          # 0 / 1

    cmds = {"setFrequency" : 'freq=',        # 0 - 3,000
            "setBlade" : 'blade=',           # 3 = MC1F30
            "setEnable": "enable="}          # 0 / 1

    ports = serial.tools.list_ports.comports()
    if ports == []:
        print("[Chopper Error]: No serial devices detected!")
        sys.exit(1)

    else:
        for port, desc, hwid in sorted(ports):
            # print(port,desc,hwid)
            if desc == "MC2000B - MC2000B" :
                ser = serial.Serial(port, 115200, timeout=1)
                if debug: print("[Chopper]: Wait - Opening the filter wheel serial port!")
                if ser.is_open: 
                    if debug: print("[Chopper]: Port is already open!")
                else:
                    ser.open()
                    if ser.is_open and debug: print("[Chopper]: Port is Open!")
                def getInfo(n):
                    p = str.encode(info[n]+'\r') # encode string as byte
                    ser.write(p)
                    ser.reset_output_buffer()
                    time.sleep(.1)

                    line = (str(ser.read_until('\r')))[2:-5]
                    q = line.split('\\r')
                    # print(f'[Chopper INFO]: {n} - {q[-1]}' )
                    return q[-1]

                def setCmd(cmd,val):
                    p = str.encode(cmds[cmd]+str(val)+'\r') # encode string as byte
                    ser.write(p)
                    ser.reset_output_buffer()
                    time.sleep(.2)
                    # print(f'[Chopper ACTION]: {cmd} - {val}' )
                    ser.reset_output_buffer()

                if args.r:
                    out = getInfo(args.r)
                    if out != "":
                        ser.close()
                        sys.exit(0)

                if args.c:
                    command, value = args.c
                    setCmd(command, value)
                    if command == "setFrequency":
                        time.sleep(.5)
                        while(getInfo('getFrequency') != value):
                            print('[Chopper Failed]: Moving to position. Retrying..')
                            setCmd(command, value)
                            counter+=1
                            if (counter == 10):
                                print('[Chopper EXIT]: Failed to move into position.')
                                sys.exit(1)
                            time.sleep(1)

                        if (getInfo('getBlade') != 3):
                            time.sleep(.5)
                            setCmd('setBlade', 3)
                            while(not getInfo('getEnable')):
                                print('[Chopper Failed]: Couldn\'t set the blade type!')
                                setCmd('setBlade', 3)
                                counter+=1
                                if (counter == 10):
                                    print('[Chopper EXIT]: Failed to set the blade Type.')
                                    sys.exit(1)
                                time.sleep(1)

                        setCmd('setEnable', 1)
                        time.sleep(.5)
                        while(not getInfo('getEnable')):
                            print('[Chopper Failed]: Couldn\'t start the chopper!')
                            setCmd('setEnable', 1)
                            counter+=1
                            if (counter == 10):
                                print('[Chopper EXIT]: Failed to Start the shopper.')
                                sys.exit(1)
                            time.sleep(1)

                        print(f'[Chopper Done]: Running chopper at {value} Hz')
                        ser.close()
                        sys.exit(0)

        print("[Chopper Failed]: Thorlabs Chopper wheel not detected!")
        sys.exit(1)

if __name__ == "__main__":
    main()
