# Receives bytes from Hydro Thunder Diego and PC, verifies and decodes data, (optionally) modifies the data, re-encodes the data, then outputs to the other side
# CPLD security functions pulled from linkinpark9812's hydro-test.py script posted to KLOV forums

import sys
import threading
import queue
import readchar
import time
import serial


def DataMap1(data, baseData):
  newData = 0

  dataMap = [0x7, 0x2, 0x4, 0x5, 0x6, 0x1, 0x0, 0x3, 0xC, 0xB, 0xE, 0x9, 0xD, 0xF, 0x8, 0xA, 0x13, 0x15, 0x14, 0x11, 0x10, 0x17, 0x12, 0x16, 0x18, 0x1A, 0x1D, 0x1F, 0x19, 0x1B, 0x1C, 0x1E]

  #Map
  for i in range(0,32):
    newData |= ((data & 0x1) << dataMap[i])
    if(i<=30): data = data >> 0x1

  #XOR
  newData = newData ^ baseData

  return newData


def DataMap2(data):
  newData = 0

  dataMap = [0x2, 0x1D, 0x14, 0x5, 0x1F, 0xC, 0xE, 0x11, 0x1, 0x16, 0x19, 0x9, 0x6, 0x1B, 0x13, 0x3, 0x10, 0xD, 0x15, 0x8, 0x0, 0x1C, 0xA, 0x1E, 0x4, 0x18, 0xB, 0x12, 0x17, 0xF, 0x1A, 0x7]

  #Map
  for i in range(0,32):
    newData |= ((data & 0x1) << dataMap[i])
    if(i<=30): data = data >> 0x1

  return newData


def CalculateData(data, prevData, startSeq):
  newData = 0
  if(startSeq == True):
    #Data Map 1 
    baseData = 0x7D3E9554 #Start Seq base data (Calculated from Hydro Thunder's hard coded Start Seq)
    newData = DataMap1(data, baseData)
  else:
    #Data Map 2
    baseData = 0x511B5522 #Non-Start Seq base data (Seems to be constant, Start Seq has no effect on it)
    movedPrevData = DataMap2(prevData)
    newData = DataMap1(data, baseData)
    #XOR
    newData = newData ^ movedPrevData

  return newData;


def endian_swap(data):
  return ((data&0x000000FF)<<24)|((data&0x0000FF00)<<8)|((data&0x00FF0000)>>8)|((data&0xFF000000)>>24)


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


#global vars for security emulation getting input from Diego thread and outputting from PC thread
pc_sec_emu_word=0x00000000
pc_sec_emu_rst=0
pc_sec_emu_clk=0

# receives, decodes, and (optionally) modifies data from Diego, putting into diego_queue
def read_diego_input():

  global pc_sec_emu_word
  global pc_sec_emu_rst
  global pc_sec_emu_clk

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
  
  diego_sec_emu_word=0x00000000
  diego_sec_emu_shift_cnt=0
  diego_sec_emu_startseq=0
  prev_diego_sec_clk=-1


  #read data from Diego
  currbyte=""
  bytenum=0
  diego_msg=bytearray()
  while True:
    prevbyte = currbyte
    currbyte = diego_ser.read() # read byte
    if currbyte == b'\xc0':
      if prevbyte != currbyte:
        #print() # print one new line
        bytenum=0 # start of new message
        diego_msg=bytearray() # clear message
    else:
      if currbyte != b'\xdb': # do nothing if current byte is escape
        if prevbyte == b'\xdb' and currbyte == b'\xdc':
          currbyte = b'\xc0' # replace with end
        elif prevbyte == b'\xdb' and currbyte == b'\xdd':
          currbyte = b'\xdb' # replace with esc
        #print(currbyte.hex(), end='') # print current byte
        diego_msg+=currbyte # append byte to message array
        if bytenum == 9: # validate checksum
          checksum=fletcher16(diego_msg[0:8])
          if ((diego_msg[9]<<8)|(diego_msg[8])) != checksum:
            #print(" cs bad:",hex(checksum), end='')
            ...
          elif parity(diego_msg[0:8]): # check parity over message only
            #print(" parity check failed", end='')
            ...
          else:
            #print(' {0:.6f} '.format(time.time()), end=' ') #timestamp

            #byte[0] bit 6 Diego initialized, set to byte[0] bit 6 of PC message (usually 1 except first message)
            #print(format(diego_msg[0], '08b')[1],end=' ')
            diego_init=(diego_msg[0]>>6)&1

            #byte[0] bit 5 security clock?
            #print(format(diego_msg[0], '08b')[2],end=' ')
            diego_sec_clk=(diego_msg[0]>>5)&1

            #byte[0] bit 4 always 0?
            #print(format(diego_msg[0], '08b')[3],end=' ')
            diego_unk_0b4=(diego_msg[0]>>4)&1

            #byte[0] bit 2 security reload?
            #print(format(diego_msg[0], '08b')[5],end=' ')
            diego_sec_rst=(diego_msg[0]>>2)&1

            #byte[0] bits 1-0 security bits?
            #print(format(diego_msg[0], '08b')[6:8],end=' ')
            diego_sec_seq=diego_msg[0]&3

            #byte[1] bits 6-4 coin 5?
            #print(format(diego_msg[1], '08b')[1:4],end=' ')
            diego_coin5=(diego_msg[1]>>4)&7

            #byte[1] bits 3-1 coin 4?
            #print(format(diego_msg[1], '08b')[4:7],end=' ')
            diego_coin4=(diego_msg[1]>>1)&7

            #byte[1] bit 0, (upper bit with line below)
            #print(format(diego_msg[1], '08b')[7],end='')
            diego_coin3=(diego_msg[1]&1)<<2

            #byte[2] bits 7-6 coin 3?
            #print(format(diego_msg[2], '08b')[0:2],end=' ')
            diego_coin3|=(diego_msg[2]>>6)&3

            #byte[2] bits 5-3 coin 2?
            #print(format(diego_msg[2], '08b')[2:5],end=' ')
            diego_coin2=(diego_msg[2]>>3)&7

            #byte[2] bits 2-0 coin 1, 0 when never used, then counts from 1 through 7 once used (never goes back to 0)
            #print(format(diego_msg[2], '08b')[5:8],end=' ')
            diego_coin1=diego_msg[2]&7

            #byte[3] steering (left is 0x00-ish, right is 0xFF-ish), also has random 2-bit pattern at start (security?)
            #print(format(diego_msg[3], '08b'),end=' ')
            diego_steering=diego_msg[3]

            #byte[4] throttle (reverse is 0x00-ish, full is 0xFF-ish), also has random 2-bit pattern at start (same values as steering, security?)
            #print(format(diego_msg[4], '08b'),end=' ')
            diego_throttle=diego_msg[4]
            
            #byte[5] DIPs (switch corresponding to bit position, only read at startup, off=1, on=0)
            #print(format(diego_msg[5], '08b'),end=' ')
            diego_dip7=(diego_msg[5]>>7)&1
            diego_dip6=(diego_msg[5]>>6)&1
            diego_dip5=(diego_msg[5]>>5)&1
            diego_dip4=(diego_msg[5]>>4)&1
            diego_dip3=(diego_msg[5]>>3)&1
            diego_dip2=(diego_msg[5]>>2)&1
            diego_dip1=(diego_msg[5]>>1)&1
            diego_dip0=diego_msg[5]&1
            
            #byte[6] switches: test vol+ vol- credit pilot low high boost, pressed=0
            #print(format(diego_msg[6], '08b'),end='')
            diego_test=(diego_msg[6]>>7)&1
            diego_volup=(diego_msg[6]>>6)&1
            diego_voldn=(diego_msg[6]>>5)&1
            diego_credit=(diego_msg[6]>>4)&1
            diego_pilot=(diego_msg[6]>>3)&1
            diego_low=(diego_msg[6]>>2)&1
            diego_high=(diego_msg[6]>>1)&1
            diego_boost=diego_msg[6]&1
            
            #byte[7] unused
            diego_unused=diego_msg[7]


            #read data from Diego to feed into PC security emulation
            if diego_sec_clk!=prev_diego_sec_clk: #clock toggled
              if diego_sec_rst==1: #reset
                diego_sec_emu_startseq=1 #set start sequence flag for calculation function
                diego_sec_emu_shift_cnt=0 #register empty if reset
              diego_sec_emu_word=((diego_sec_emu_word<<2)|diego_sec_seq)&0xFFFFFFFF #shift two new bits into register
              diego_sec_emu_shift_cnt+=2 #two more bits in register
              if diego_sec_emu_shift_cnt==32: #register full, generate next security word
                pc_sec_emu_word=CalculateData(diego_sec_emu_word, pc_sec_emu_word, diego_sec_emu_startseq) #run calculation function
                #print(diego_sec_emu_startseq, end=' ')
                #print(hex(diego_sec_emu_word), end=' ')
                #print(hex(pc_sec_emu_word))
                if diego_sec_emu_startseq==1:
                  pc_sec_emu_rst=1 #set flag for pc output to set reset flag
                  diego_sec_emu_startseq=0 #clear start seq flag
                diego_sec_emu_shift_cnt=0 #register empty
              pc_sec_emu_clk=diego_sec_clk #toggle clock for PC thread

            prev_diego_sec_clk=diego_sec_clk


            #modify data here

            #diego_init=1 #0b6
            #diego_sec_clk=0 #0b5
            #diego_unk_0b4=0 #0b4, always 0?
            #diego_sec_rst=0 #0b2
            #diego_sec_seq=0 #0b1:0

            #print('D',end=' ')
            #print(diego_sec_rst,end=' ')
            #print(diego_sec_clk,end=' ')
            #print(diego_sec_seq)
            
            #diego_coin5=0 #1b6:4
            #diego_coin4=0 #1b3:1
            #diego_coin3=0 #1b0,2b7:6
            #diego_coin2=0 #2b5:3
            #diego_coin1=0 #2b2:0
            #diego_steering=0x80 #3b7:0
            #diego_throttle=0x80 #4b7:0
            #diego_dip7=1 #5b7
            #diego_dip6=1 #5b6
            #diego_dip5=1 #5b5
            #diego_dip4=1 #5b4
            #diego_dip3=1 #5b3
            #diego_dip2=1 #5b2
            #diego_dip1=1 #5b1
            #diego_dip0=1 #5b0
            #diego_test=1 #6b7
            #diego_volup=1 #6b6
            #diego_voldn=1 #6b5
            #diego_credit=1 #6b4
            #diego_pilot=1 #6b3
            #diego_low=1 #6b2
            #diego_high=1 #6b1
            #diego_boost=1 #6b0
            #diego_unused=0 #7b7:0, unused


            #build message
            diego_msg[0]=(diego_init<<6)|(diego_sec_clk<<5)|(diego_unk_0b4<<4)|(diego_sec_rst<<2)|diego_sec_seq
            diego_msg[1]=(diego_coin5<<4)|(diego_coin4<<1)|(diego_coin3>>2)
            diego_msg[2]=((diego_coin3&3)<<6)|(diego_coin2<<3)|diego_coin1
            diego_msg[3]=diego_steering
            diego_msg[4]=diego_throttle
            diego_msg[5]=(diego_dip7<<7)|(diego_dip6<<6)|(diego_dip5<<5)|(diego_dip4<<4)|(diego_dip3<<3)|(diego_dip2<<2)|(diego_dip1<<1)|diego_dip0
            diego_msg[6]=(diego_test<<7)|(diego_volup<<6)|(diego_voldn<<5)|(diego_credit<<4)|(diego_pilot<<3)|(diego_low<<2)|(diego_high<<1)|diego_boost
            diego_msg[7]=diego_unused
            if parity(diego_msg[0:8]):
              diego_msg[0]^=0x80 #make even parity
            csum=fletcher16(diego_msg[0:8])
            #print(hex(diego_msg[0]),end=' ')
            #print(hex(diego_msg[1]),end=' ')
            #print(hex(diego_msg[2]),end=' ')
            #print(hex(diego_msg[3]),end=' ')
            #print(hex(diego_msg[4]),end=' ')
            #print(hex(diego_msg[5]),end=' ')
            #print(hex(diego_msg[6]),end=' ')
            #print(hex(diego_msg[7]))
            diego_queue.put(b'\xc0') # write start
            for i in range(8):
              if diego_msg[i] == 0xC0: #replace with 0xDB 0xDC
                diego_queue.put(b'\xdb') # write byte
                diego_queue.put(b'\xdc') # write byte
              elif diego_msg[i] == 0xDB: #replace with 0xDB 0xDD
                diego_queue.put(b'\xdb') # write byte
                diego_queue.put(b'\xdd') # write byte
              else:
                diego_queue.put(bytes([diego_msg[i]])) # write byte
            diego_queue.put(bytes([csum&0xFF])) # write checksum
            diego_queue.put(bytes([csum>>8])) # write checksum
            diego_queue.put(b'\xc0') # write end

        bytenum += 1


# sends re-encoded Diego data to PC, getting from diego_queue
def write_diego_output():
  while (True):
    time.sleep(0.001) #only check for new data every ~1 ms
    while (diego_queue.qsize() > 0):
      diego_tx_byte = diego_queue.get()
      #print(diego_tx_byte,end=' ')
      pc_ser.write(bytes(diego_tx_byte))


# receives, decodes, and (optionally) modifies data from PC, putting into pc_queue
def read_pc_input():

  global pc_sec_emu_word
  global pc_sec_emu_rst
  global pc_sec_emu_clk

  #initialize values
  pc_init=1 #0b6
  pc_sec_clk=0 #0b5
  pc_unk_0b4=0 #0b4, always 0?
  pc_sec_rst=0 #0b2
  pc_sec_seq=0 #0b1:0
  pc_unk_1b10=0 #1b1:0, always 00?
  pc_ffb=0 #2b7:0
  pc_lamp_hdr_top=0 #3b7
  pc_lamp_hdr_bottom=0 #3b6
  pc_lamp_high=0 #3b3
  pc_lamp_low=0 #3b2
  pc_lamp_pilot=0 #3b1
  pc_lamp_boost=0 #3b0
  pc_walk=0 #4b3:0
  pc_unk_5b70=0x80 #5b7:0, always 0x80 except 0x00 in first message
  pc_unk_6b70=0xFF #6b7:0, always 0xFF except 0x84 in first set of messages
  pc_unused=0 #7b7:0, unused
  
  pc_sec_emu_shift_cnt=0
  prev_pc_sec_emu_clk=-1
  prev_pc_sec_clk=-1
  

  #read data from PC
  currbyte=""
  bytenum=0
  pc_msg=bytearray()
  while True:
    prevbyte = currbyte
    currbyte = pc_ser.read() # read byte
    if currbyte == b'\xc0':
      if prevbyte != currbyte:
        #print() # print one new line
        bytenum=0 # start of new message
        pc_msg=bytearray() # clear message
    else:
      if currbyte != b'\xdb': # do nothing if current byte is escape
        if prevbyte == b'\xdb' and currbyte == b'\xdc':
          currbyte = b'\xc0' # replace with end
        elif prevbyte == b'\xdb' and currbyte == b'\xdd':
          currbyte = b'\xdb' # replace with esc
        #print(currbyte.hex(), end='') # print current byte
        pc_msg+=currbyte # append byte to message array
        if bytenum == 9: # validate checksum
          checksum=fletcher16(pc_msg[0:8])
          if ((pc_msg[9]<<8)|(pc_msg[8])) != checksum:
            #print(" cs bad:",hex(checksum), end='')
            ...
          elif parity(pc_msg[0:8]): # check parity over message only
            #print(" parity check failed", end='')
            ...
          else:
            #print(' {0:.6f} '.format(time.time()), end=' ') #timestamp
            
            #byte[0] bits 6-4 (1 except first initialization is 0,1/0 usually toggled every message though not always - maybe lfsr clock for lower bits?,0)
            #print(format(pc_msg[0], '08b')[1:4],end=' ')
            pc_init=(pc_msg[0]>>6)&1
            pc_sec_clk=(pc_msg[0]>>5)&1
            pc_unk_0b4=(pc_msg[0]>>4)&1

            #byte[0] bits 2-0 (reset sequence in bit 2?, random sequence in bits 1-0 - only changes when bit 5 changes?)
            #print(format(pc_msg[0], '08b')[5:8],end=' ')
            pc_sec_rst=(pc_msg[0]>>2)&1
            pc_sec_seq=pc_msg[0]&3

            #byte[1] bits 1-0 always 00?
            #print(format(pc_msg[1], '08b')[6:8],end=' ')
            pc_unk_1b10=pc_msg[1]&3
            
            #byte[2] force feedback (two's complement, negative for right force, positive for left force)
            #print(format(pc_msg[2], '08b'),end=' ')
            pc_ffb=pc_msg[2]

            #byte[3] lamps: headertop headerbottom x x high low pilot boost
            #print(format(pc_msg[3], '08b'),end=' ')
            pc_lamp_hdr_top=(pc_msg[3]>>7)&1
            pc_lamp_hdr_bottom=(pc_msg[3]>>6)&1
            pc_lamp_high=(pc_msg[3]>>3)&1
            pc_lamp_low=(pc_msg[3]>>2)&1
            pc_lamp_pilot=(pc_msg[3]>>1)&1
            pc_lamp_boost=pc_msg[3]&1

            #byte[4] pattern of 1 shifting up and down in lower 4 bits every two messages? doesn't seem to relate to security (free-runs even without security stuff changing), maybe timer output for watchdog? seems to only affect Diego status LEDs (works fine if always 0)
            #print(format(pc_msg[4], '08b'),end=' ')
            pc_walk=pc_msg[4]&0x0F

            #byte[5] always 0x80? value doesn't seem to matter
            #print(format(pc_msg[5], '08b'),end=' ')
            pc_unk_5b70=pc_msg[5]

            #byte[6] always 0xFF? (except 0x84 for first couple Tx? what if no Diego attached?) value doesn't seem to matter
            #print(format(pc_msg[6], '08b'),end='')
            pc_unk_6b70=pc_msg[6]
            
            #byte[7] unused
            pc_unused=pc_msg[7]


            prev_pc_sec_clk=pc_sec_clk


            #print('P',end=' ')
            #print(pc_sec_rst,end=' ')
            #print(pc_sec_clk,end=' ')
            #print(pc_sec_seq)


            #emulate PC security
            pc_sec_rst=pc_sec_emu_rst #0b2
            pc_sec_clk=pc_sec_emu_clk #0b5
            if pc_sec_emu_clk!=prev_pc_sec_emu_clk: #clock toggled
              if pc_sec_emu_rst==1: #reset
                pc_sec_emu_shift_cnt=0 #register full
                pc_sec_emu_rst=0 #clear reset pending flag
              else:
                pc_sec_emu_shift_cnt=(pc_sec_emu_shift_cnt+2)%32 #two more bits shifted out of register
            prev_pc_sec_emu_clk=pc_sec_emu_clk
            pc_sec_seq=(endian_swap(pc_sec_emu_word)>>(30-pc_sec_emu_shift_cnt))&3 #0b1:0
            
            #print('E',end=' ')
            #print(pc_sec_rst,end=' ')
            #print(pc_sec_clk,end=' ')
            #print(pc_sec_seq)
              

            #modify data here
            
            #pc_init=1 #0b6
            #pc_sec_clk=0 #0b5
            #pc_unk_0b4=0 #0b4, always 0?
            #pc_sec_rst=0 #0b2
            #pc_sec_seq=0 #0b1:0
            
            #pc_unk_1b10=0 #1b1:0, always 00?
            #pc_ffb=0 #2b7:0
            #pc_lamp_hdr_top=0 #3b7
            #pc_lamp_hdr_bottom=0 #3b6
            #pc_lamp_high=0 #3b3
            #pc_lamp_low=0 #3b2
            #pc_lamp_pilot=0 #3b1
            #pc_lamp_boost=0 #3b0
            #pc_walk=0 #4b3:0
            #pc_unk_5b70=0 #0x80 #5b7:0, always 0x80 except 0x00 in first message
            #pc_unk_6b70=0 #0xFF #6b7:0, always 0xFF except 0x84 in first set of messages
            #pc_unused=0 #7b7:0, unused


            #build message
            pc_msg[0]=(pc_init<<6)|(pc_sec_clk<<5)|(pc_unk_0b4<<4)|(pc_sec_rst<<2)|pc_sec_seq
            pc_msg[1]=pc_unk_1b10
            pc_msg[2]=pc_ffb
            pc_msg[3]=(pc_lamp_hdr_top<<7)|(pc_lamp_hdr_bottom<<6)|(pc_lamp_high<<3)|(pc_lamp_low<<2)|(pc_lamp_pilot<<1)|pc_lamp_boost
            pc_msg[4]=pc_walk
            pc_msg[5]=pc_unk_5b70
            pc_msg[6]=pc_unk_6b70
            pc_msg[7]=pc_unused
            if parity(pc_msg[0:8]):
              pc_msg[0]^=0x80 #make even parity
            csum=fletcher16(pc_msg[0:8])
            #print(hex(pc_msg[0]),end=' ')
            #print(hex(pc_msg[1]),end=' ')
            #print(hex(pc_msg[2]),end=' ')
            #print(hex(pc_msg[3]),end=' ')
            #print(hex(pc_msg[4]),end=' ')
            #print(hex(pc_msg[5]),end=' ')
            #print(hex(pc_msg[6]),end=' ')
            #print(hex(pc_msg[7]))
            pc_queue.put(b'\xc0') # write start
            for i in range(8):
              if pc_msg[i] == 0xC0: #replace with 0xDB 0xDC
                pc_queue.put(b'\xdb') # write byte
                pc_queue.put(b'\xdc') # write byte
              elif pc_msg[i] == 0xDB: #replace with 0xDB 0xDD
                pc_queue.put(b'\xdb') # write byte
                pc_queue.put(b'\xdd') # write byte
              else:
                pc_queue.put(bytes([pc_msg[i]])) # write byte
            pc_queue.put(bytes([csum&0xFF])) # write checksum
            pc_queue.put(bytes([csum>>8])) # write checksum
            pc_queue.put(b'\xc0') # write end

        bytenum += 1


# sends re-encoded PC data to Diego, getting from pc_queue
def write_pc_output():
  while (True):
    time.sleep(0.001) #only check for new data every ~1 ms
    while (pc_queue.qsize() > 0):
      pc_tx_byte = pc_queue.get()
      #print(pc_tx_byte,end=' ')
      diego_ser.write(bytes(pc_tx_byte))


def write_diego_through():
  while (True):
    #time.sleep(0.001) #only check for new data every ~1 ms
    diego_readbyte=diego_ser.read()
    #print(diego_readbyte,end=' ')
    pc_ser.write(bytes(diego_readbyte))


def write_pc_through():
  while (True):
    #time.sleep(0.001) #only check for new data every ~1 ms
    pc_readbyte=pc_ser.read()
    #print(pc_readbyte,end=' ')
    diego_ser.write(bytes(pc_readbyte))


if len(sys.argv) != 3:
  print("Usage: ht_mitm.py <Diego serial port> <PC serial port>")
  sys.exit(1)

# open serial ports
diego_ser = serial.Serial(sys.argv[1], 38400) # open serial port
pc_ser = serial.Serial(sys.argv[2], 38400) # open serial port

# non-blocking serial I/O stuff
diego_queue = queue.Queue() # queue for Diego data output (to PC)
pc_queue = queue.Queue() # queue for PC data output (to Diego)
diego_rx_thread = threading.Thread(target=read_diego_input, daemon=True) # receives data from Diego for decoding
diego_tx_thread = threading.Thread(target=write_diego_output, daemon=True) # sends re-encoded data to Diego
pc_rx_thread = threading.Thread(target=read_pc_input, daemon=True) # receives data from PC for decoding
pc_tx_thread = threading.Thread(target=write_pc_output, daemon=True) # sends re-encoded data to PC

diego_through_thread = threading.Thread(target=write_diego_through, daemon=True) # Diego through
pc_through_thread = threading.Thread(target=write_pc_through, daemon=True) # PC through

#set simple=1 for simple passthrough, 0 for decode/mod/recode
simple=0
# start threads
if simple==0:
  diego_rx_thread.start()
  diego_tx_thread.start()
  pc_rx_thread.start()
  pc_tx_thread.start()
else:
  diego_through_thread.start()
  pc_through_thread.start()

print("Press any key to quit")
readchar.readkey()

diego_ser.close() # close port
pc_ser.close() # close port
