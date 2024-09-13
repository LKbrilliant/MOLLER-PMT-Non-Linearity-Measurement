# Code by:      Anuradha Gunawardhana
# Date:         2024.04.22 
# Description:  Receive serial data from the arduino which is connected to two temperature sensors and
#               append data to a text file. 

import serial
import sys
import serial.tools.list_ports
import argparse
 
def main():
    print("------------------------------------------------")
    print("|             Reading Temperature              |")
    print("------------------------------------------------")

    parser = argparse.ArgumentParser(prog='Temperature Monitor',
                                     description='Read values through serial interface from two temperature sensors attached to an Arduino. Code by: Anuradha Gunawardhana')
    
    parser.add_argument("dir", help="Select the destination directory")
    args = parser.parse_args() 

    baud_rate = 9600
    ports = serial.tools.list_ports.comports()
    if ports == []:
        print("[TEMP_Monitor Error]: No serial devices detected!")
        sys.exit(1)

    for port, desc, hwid in sorted(ports):
        if desc == "USB Serial" :
            ser = serial.Serial(port, baud_rate)
            if ser.is_open: print("[TEMP_Monitor]: Port is already open!")
            else:
                ser.open()
                if ser.is_open: print("[TEMP_Monitor]: Port is Open!")
            line = str(ser.readline(), encoding='utf-8').strip()
            count = 0
            while(len(line)!=34):
                print("[TEMP_Monitor]: Warning! serial data mismatch")
                line = str(ser.readline(), encoding='utf-8').strip()
                # print("[TEMP_Monitor]: Warning! NO serial data")
                count+=1
                if count > 1: 
                    print("[TEMP_Monitor Failed]: No data! Try reconnecting the USB cable")
                    sys.exit(1)
            
            t_LEDs = line.strip().split(',')[1]
            h_room = line.strip().split(',')[0][5:]
            t_darkBox = line.strip().split(',')[3]
            h_darkBox = line.strip().split(',')[2][5:]

            print(f"[TEMP_Monitor]: LEDs:{t_LEDs}, DarkBox:{t_darkBox}")
            with open(f"{args.dir}/Temp_data.txt", 'a') as f:
                f.writelines(f"Temperature[LEDs,Dark Box](C)={t_LEDs},{t_darkBox}\n")
            print(f"[TEMP_Monitor]: Done saving temperature to {args.dir}/Temp_data.txt")
            ser.close()
            sys.exit(0)

    print("[TEMP_Monitor ERROR]: No serial temperature monitor available")
    sys.exit(1)

if __name__ == "__main__":
    main()
