# Simulates Diego output using input from keyboard

import sys
import threading
import queue
import readchar
import time
import serial

#Video enable sequence
#Script repeatedly outputs sequence to enable OEM 3DFX video output
#B7C85F52
#B8AD0DEA
#050D8168
#E23C1A36
#F9DCDD9C
#A15C0538
#842E0D10
#274B6E18
#Array stored as [rst, clk, seq]
video_enable=[
[1,1,2],[0,0,3],[0,1,1],[0,0,3],[0,1,3],[0,0,0],[0,1,2],[0,0,0],
[0,1,1],[0,0,1],[0,1,3],[0,0,3],[0,1,1],[0,0,1],[0,1,0],[0,0,2],
[0,1,2],[0,0,3],[0,1,2],[0,0,0],[0,1,2],[0,0,2],[0,1,3],[0,0,1],
[0,1,0],[0,0,0],[0,1,3],[0,0,1],[0,1,3],[0,0,2],[0,1,2],[0,0,2],
[0,1,0],[0,0,0],[0,1,1],[0,0,1],[0,1,0],[0,0,0],[0,1,3],[0,0,1],
[0,1,2],[0,0,0],[0,1,0],[0,0,1],[0,1,1],[0,0,2],[0,1,2],[0,0,0],
[0,1,3],[0,0,2],[0,1,0],[0,0,2],[0,1,0],[0,0,3],[0,1,3],[0,0,0],
[0,1,0],[0,0,1],[0,1,2],[0,0,2],[0,1,0],[0,0,3],[0,1,1],[0,0,2],
[0,1,3],[0,0,3],[0,1,2],[0,0,1],[0,1,3],[0,0,1],[0,1,3],[0,0,0],
[0,1,3],[0,0,1],[0,1,3],[0,0,1],[0,1,2],[0,0,1],[0,1,3],[0,0,0],
[0,1,2],[0,0,2],[0,1,0],[0,0,1],[0,1,1],[0,0,1],[0,1,3],[0,0,0],
[0,1,0],[0,0,0],[0,1,1],[0,0,1],[0,1,0],[0,0,3],[0,1,2],[0,0,0],
[0,1,2],[0,0,0],[0,1,1],[0,0,0],[0,1,0],[0,0,2],[0,1,3],[0,0,2],
[0,1,0],[0,0,0],[0,1,3],[0,0,1],[0,1,0],[0,0,1],[0,1,0],[0,0,0],
[0,1,0],[0,0,2],[0,1,1],[0,0,3],[0,1,1],[0,0,0],[0,1,2],[0,0,3],
[0,1,1],[0,0,2],[0,1,3],[0,0,2],[0,1,0],[0,0,1],[0,1,2],[0,0,0],
]

#non-blocking keyboard input thread
def read_kbd_input(inputQueue):
  while (True):
    key = readchar.readkey()
    inputQueue.put(key)

def fletcher16(data):
  cb0 = 0
  cb1 = 0
  for i in range(len(data)):
    cb0 = (cb0 + data[i]) % 255
    cb1 = (cb1 + cb0) % 255
  cb0 = 255 - ((cb1 + cb0) % 255) #slight mod from standard
  return (cb1 << 8) | cb0

def parity(data):
  parity=0
  for i in range(len(data)):
    parity ^= data[i]
  return parity.bit_count() & 1

if len(sys.argv) != 2:
  print("Usage: ht_diego_sim.py <serial port>")
  sys.exit(1)

ser = serial.Serial(sys.argv[1], 38400) # open serial port

#non-blocking input stuff
inputQueue = queue.Queue()
inputThread = threading.Thread(target=read_kbd_input, args=(inputQueue,), daemon=True)
inputThread.start()

#initialize values
diego_init=1 #0b6
diego_sec_clk=0 #0b5
diego_unk_0b4=0 #0b4, always 0?
diego_sec_rst=0 #0b2
diego_sec_seq=0 #0b1:0
diego_coin5=0 #1b6:4
diego_coin4=0 #1b3:1
diego_coin3=0 #1b0,2b7:6
diego_coin2=0 #2b5:3
diego_coin1=0 #2b2:0
diego_steering=0x80 #3b7:0
diego_throttle=0x80 #4b7:0
diego_dip7=1 #5b7
diego_dip6=1 #5b6
diego_dip5=1 #5b5
diego_dip4=1 #5b4
diego_dip3=1 #5b3
diego_dip2=1 #5b2
diego_dip1=1 #5b1
diego_dip0=1 #5b0
diego_test=1 #6b7
diego_volup=1 #6b6
diego_voldn=1 #6b5
diego_credit=1 #6b4
diego_pilot=1 #6b3
diego_low=1 #6b2
diego_high=1 #6b1
diego_boost=1 #6b0
diego_unused=0 #7b7:0, unused

msg=bytearray(8)
sec_cnt=0

print("See source code for keyboard mapping")
print("Press 'q' to quit")
while True:
  #check for input from keyboard
  if (inputQueue.qsize() > 0):
    keypress = inputQueue.get()
  else:
    keypress = ''
    
  if keypress=='q': #quit
    break

  if keypress=='1': #coin 1
    diego_coin1+=1
    if diego_coin1==8:
      diego_coin1=1
  if keypress=='2': #coin 2
    diego_coin2+=1
    if diego_coin2==8:
      diego_coin2=1
  if keypress=='3': #coin 3
    diego_coin3+=1
    if diego_coin3==8:
      diego_coin3=1
  if keypress=='4': #coin 4
    diego_coin4+=1
    if diego_coin4==8:
      diego_coin4=1
  if keypress=='5': #coin 5
    diego_coin5+=1
    if diego_coin5==8:
      diego_coin5=1
  if keypress=='\x00H': #up arrow (don't go to 0xFF, software doesn't seem to like that when boost is enabled)
    diego_throttle=0xFE
  if keypress=='\x00P': #down arrow (don't go to 0x00, software doesn't seem to like that when boost is enabled)
    diego_throttle=0x01
  if keypress=='\x00K': #left arrow
    diego_steering=0x00
  elif keypress=='\x00M': #right arrow
    diego_steering=0xFF
  else:
    diego_steering=0x80
  if keypress=='t': #test
    diego_test=0
  else:
    diego_test=1
  if keypress=='+': #vol +
    diego_volup=0
  else:
    diego_volup=1
  if keypress=='-': #vol -
    diego_voldn=0
  else:
    diego_voldn=1
  if keypress=='c': #credit
    diego_credit=0
  else:
    diego_credit=1
  if keypress=='p': #pilot
    diego_pilot=0
  else:
    diego_pilot=1
  if keypress=='l': #low
    diego_low=0
  else:
    diego_low=1
  if keypress=='h': #high
    diego_high=0
  else:
    diego_high=1
  if keypress=='b': #toggle boost
    diego_boost^=1
  if keypress=='i': #toggle init
    diego_init^=1
  if keypress=='&': #toggle dip7
    diego_dip7^=1
  if keypress=='^': #toggle dip6
    diego_dip6^=1      
  if keypress=='%': #toggle dip5
    diego_dip5^=1      
  if keypress=='$': #toggle dip4
    diego_dip4^=1      
  if keypress=='#': #toggle dip3
    diego_dip3^=1      
  if keypress=='@': #toggle dip2
    diego_dip2^=1      
  if keypress=='!': #toggle dip1
    diego_dip1^=1      
  if keypress==')': #toggle dip0
    diego_dip0^=1
    
  #write security values to enable video
  diego_sec_clk=video_enable[sec_cnt][1]
  diego_sec_rst=video_enable[sec_cnt][0]
  diego_sec_seq=video_enable[sec_cnt][2]

  #build message
  msg[0]=(diego_init<<6)|(diego_sec_clk<<5)|(diego_unk_0b4<<4)|(diego_sec_rst<<2)|diego_sec_seq
  msg[1]=(diego_coin5<<4)|(diego_coin4<<1)|(diego_coin3>>2)
  msg[2]=((diego_coin3&3)<<6)|(diego_coin2<<3)|diego_coin1
  msg[3]=diego_steering
  msg[4]=diego_throttle
  msg[5]=(diego_dip7<<7)|(diego_dip6<<6)|(diego_dip5<<5)|(diego_dip4<<4)|(diego_dip3<<3)|(diego_dip2<<2)|(diego_dip1<<1)|diego_dip0
  msg[6]=(diego_test<<7)|(diego_volup<<6)|(diego_voldn<<5)|(diego_credit<<4)|(diego_pilot<<3)|(diego_low<<2)|(diego_high<<1)|diego_boost
  msg[7]=diego_unused
  if parity(msg):
    msg[0]^=0x80 #make even parity
  csum=fletcher16(msg)
  #print(hex(msg[0]),end=' ')
  #print(hex(msg[1]),end=' ')
  #print(hex(msg[2]),end=' ')
  #print(hex(msg[3]),end=' ')
  #print(hex(msg[4]),end=' ')
  #print(hex(msg[5]),end=' ')
  #print(hex(msg[6]),end=' ')
  #print(hex(msg[7]))
  ser.write(b'\xc0') # write start
  for i in range(8):
    if msg[i] == 0xC0: #replace with 0xDB 0xDC
      ser.write(b'\xdb') # write byte
      ser.write(b'\xdc') # write byte
    elif msg[i] == 0xDB: #replace with 0xDB 0xDD
      ser.write(b'\xdb') # write byte
      ser.write(b'\xdd') # write byte
    else:
      ser.write(bytes([msg[i]])) # write byte
  ser.write(bytes([csum&0xFF])) # write checksum
  ser.write(bytes([csum>>8])) # write checksum
  ser.write(b'\xc0') # write end
  sec_cnt=(sec_cnt+1)%128 #loop through video enable message (128 packets long)
  time.sleep(0.03) #send packet every ~30 ms

ser.close() # close port
