# Receives bytes from Hydro Thunder Diego or PC, verifies data, then outputs decoded values

import sys
import serial
import time

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

if len(sys.argv) != 3:
  print("Usage: ht_rx.py <diego|pc> <serial port>")
  sys.exit(1)

if sys.argv[1] == "diego":
  ser_fmt=0 # Diego serial format
elif sys.argv[1] == "pc":
  ser_fmt=1 # PC serial format
else:
  print("Usage: ht_rx.py <diego|pc> <serial port>")
  sys.exit(1)

ser = serial.Serial(sys.argv[2], 38400) # open serial port

# initialize vars
currbyte=""
bytenum=0
msg=bytearray()
if ser_fmt == 0:
  print("< Receiving from Diego >")
else:
  print("< Receiving from PC >")
print("Press ctrl-break to end")
while True:
  prevbyte = currbyte
  currbyte = ser.read() # read byte
  if currbyte == b'\xc0':
    if prevbyte != currbyte:
      print() # print one new line
      bytenum=0 # start of new message
      msg=bytearray() # clear message
  else:
    if currbyte != b'\xdb': # do nothing if current byte is escape
      if prevbyte == b'\xdb' and currbyte == b'\xdc':
        currbyte = b'\xc0' # replace with end
      elif prevbyte == b'\xdb' and currbyte == b'\xdd':
        currbyte = b'\xdb' # replace with esc
      print(currbyte.hex(), end='') # print current byte
      msg+=currbyte # append byte to message array
      if bytenum == 9: # validate checksum
        checksum=fletcher16(msg[0:8])
        if ((msg[9]<<8)|(msg[8])) != checksum:
          print(" cs bad:",hex(checksum), end='')
        if parity(msg[0:8]): # check parity over message only
          print(" parity check failed", end='')
        if ser_fmt == 0: #print Diego bits
          print(' {0:.6f} '.format(time.time()), end=' ') #timestamp
          print(format(msg[0], '08b')[1],end=' ') #byte[0] bit 6 Diego initialized, set to byte[0] bit 6 of PC message (usually 1 except first message)
          print(format(msg[0], '08b')[2],end=' ') #byte[0] bit 5 security clock
          print(format(msg[0], '08b')[3],end=' ') #byte[0] bit 4 always 0?
          print(format(msg[0], '08b')[5],end=' ') #byte[0] bit 2 security reset
          print(format(msg[0], '08b')[6:8],end=' ') #byte[0] bits 1-0 security sequence bits
          print(format(msg[1], '08b')[1:4],end=' ') #byte[1] bits 6-4 coin 5
          print(format(msg[1], '08b')[4:7],end=' ') #byte[1] bits 3-1 coin 4
          print(format(msg[1], '08b')[7],end='') #byte[1] bit 0, (upper bit with line below)
          print(format(msg[2], '08b')[0:2],end=' ') #byte[2] bits 7-6 coin 3
          print(format(msg[2], '08b')[2:5],end=' ') #byte[2] bits 5-3 coin 2
          print(format(msg[2], '08b')[5:8],end=' ') #byte[2] bits 2-0 coin 1, coins are 0 when never used, then count from 1 through 7 once used (never goes back to 0)
          print(format(msg[3], '08b'),end=' ') #byte[3] steering (left is 0x00-ish, right is 0xFF-ish), also has random 2-bit pattern at start (security?)
          print(format(msg[4], '08b'),end=' ') #byte[4] throttle (reverse is 0x00-ish, full is 0xFF-ish), also has random 2-bit pattern at start (same values as steering, security?)
          print(format(msg[5], '08b'),end=' ') #byte[5] DIPs (switch corresponding to bit position, only read at startup, off=1, on=0)
          print(format(msg[6], '08b'),end='') #byte[6] switches: test vol+ vol- credit pilot low high boost, pressed=0
        else:
          #print PC bits
          print(' {0:.6f} '.format(time.time()), end=' ') #timestamp
          print(format(msg[0], '08b')[1],end=' ') #byte[0] bit 6 initialize Diego
          print(format(msg[0], '08b')[2],end=' ') #byte[0] bit 5 security clock
          print(format(msg[0], '08b')[3],end=' ') #byte[0] bit 4 always 0?
          print(format(msg[0], '08b')[5],end=' ') #byte[0] bit 2 security reset
          print(format(msg[0], '08b')[6:8],end=' ') #byte[0] bits 1-0 security sequence bits
          print(format(msg[1], '08b')[6:8],end=' ') #byte[1] bits 1-0 always 00?
          print(format(msg[2], '08b'),end=' ') #byte[2] force feedback (two's complement, negative for right force, positive for left force)
          print(format(msg[3], '08b'),end=' ') #byte[3] lamps: headertop headerbottom x x high low pilot boost
          print(format(msg[4], '08b'),end=' ') #byte[4] pattern of 1 shifting up and down in lower 4 bits every two messages? doesn't seem to relate to security (free-runs even without security stuff changing), maybe timer output for watchdog?
          print(format(msg[5], '08b'),end=' ') #byte[5] always 0x80? (except 0x00 in first Tx?)
          print(format(msg[6], '08b'),end='') #byte[6] always 0xFF? (except 0x84 for first couple Tx?)
      bytenum += 1
ser.close() # close port
