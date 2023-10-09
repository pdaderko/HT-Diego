# Translates between Hydro Thunder Diego and BackForceFeeder
# Allows using Hydro Thunder controls (through Diego) as controller (with force feedback support) for PC
# Requires BackForceFeeder (including vJoy) for controller emulation and com0com (or similar) virtual null modem for this script to communicate with BFF
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


#BFF string definitions
version_str="V0.1.9.0 IO BOARD ON UNKNOWN"
hardware_str="GI3A4O3P1F1" #3xDI(x8) for buttons + driveboard, 4xAIn, 3xDO(x8) for direction, lamps and driveboard, 1xPWM out, 1xFullstate, 0xEnc

#global variables for sharing Diego and BFF states between processes
streaming=0
ain0=0x80 #steering
ain1=0x80 #throttle
din0=0xFF #buttons
din1=0xFF #coin (emulated switches using Diego coin count)
din2=0xFF #DIP switches


#generates button/wheel/throttle value message for BFF
def SendStatusFrame():
  global din0
  global din1
  global din2
  global ain0
  global ain1
  
  sendstr=""

  #digital inputs
  sendstr+="I%02XI%02XI%02X" % (din0,din1,din2)
  
  #analog inputs
  sendstr+="A%03XA%03XA%03XA%03X" % ((ain0<<4),(ain1<<4),0x800,0x800)
  
  #wheel state
  sendstr+="F%08XF%08X" % (0,0)
  
  sendstr+='\n'
  
  #print(sendstr)
  diego_queue.put(sendstr.encode('utf-8'))


#global vars for security emulation getting input from Diego thread and outputting from PC thread
pc_sec_emu_word=0x00000000
pc_sec_emu_rst=0
pc_sec_emu_clk=0


#receives, decodes, and (optionally) modifies data from Diego for BFF, putting into diego_queue
def read_diego_input():

  global pc_sec_emu_word
  global pc_sec_emu_rst
  global pc_sec_emu_clk
  global streaming
  global din0
  global din1
  global din2
  global ain0
  global ain1

  #initialize values
  diego_init=1 #0b6
  diego_sec_clk=0 #0b5
  diego_unk_0b4=0 #0b4, always 0?
  diego_sec_rst=0 #0b2
  diego_sec_seq=0 #0b1:0
  diego_coin5=0 #1b6:4
  prev_diego_coin5=0
  diego_coin4=0 #1b3:1
  prev_diego_coin4=0
  diego_coin3=0 #1b0,2b7:6
  prev_diego_coin3=0
  diego_coin2=0 #2b5:3
  prev_diego_coin2=0
  diego_coin1=0 #2b2:0
  prev_diego_coin1=0
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


            #emulate coin switch based on rolling coin count
            if diego_coin1!=prev_diego_coin1:
              prev_diego_coin1=diego_coin1
              diego_coin1=1
            else:
              diego_coin1=0
            if diego_coin2!=prev_diego_coin2:
              prev_diego_coin2=diego_coin2
              diego_coin2=1
            else:
              diego_coin3=0
            if diego_coin3!=prev_diego_coin3:
              prev_diego_coin3=diego_coin3
              diego_coin3=1
            else:
              diego_coin4=0
            if diego_coin4!=prev_diego_coin4:
              prev_diego_coin4=diego_coin4
              diego_coin4=1
            else:
              diego_coin4=0
            if diego_coin5!=prev_diego_coin5:
              prev_diego_coin5=diego_coin5
              diego_coin5=1
            else:
              diego_coin5=0


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


            #build BFF message
            ain0=diego_steering
            ain1=diego_throttle
            din0=((diego_test<<7)|(diego_volup<<6)|(diego_voldn<<5)|(diego_credit<<4)|(diego_pilot<<3)|(diego_low<<2)|(diego_high<<1)|diego_boost)^0xFF
            din1=(diego_coin5<<4)|(diego_coin4<<3)|(diego_coin3<<2)|(diego_coin2<<1)|diego_coin1
            din2=((diego_dip7<<7)|(diego_dip6<<6)|(diego_dip5<<5)|(diego_dip4<<4)|(diego_dip3<<3)|(diego_dip2<<2)|(diego_dip1<<1)|diego_dip0)^0xFF
            if streaming==1:
              SendStatusFrame()

        bytenum += 1


#sends Diego data to BFF, getting from diego_queue
def write_diego_output():
  while (True):
    time.sleep(0.001) #only check for new data every ~1 ms
    while (diego_queue.qsize() > 0):
      diego_tx_byte = diego_queue.get()
      #print(diego_tx_byte,end=' ')
      bff_ser.write(bytes(diego_tx_byte))


#receives, decodes, and (optionally) modifies data from BFF for Diego, putting into bff_queue
def read_bff_input():

  global pc_sec_emu_word
  global pc_sec_emu_rst
  global pc_sec_emu_clk
  global streaming

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
  

  #read data from BFF
  streaming=0
  while(True):
    pc_msg=bytearray(8)
    line = bff_ser.readline()
    line=(line.decode('utf-8'))
    line=line.strip() #remove trailing newline
    #print(line)
    param_e_cnt=0 #count for multiple 'e' parameters per line
    param_o_cnt=0 #count for multiple 'o' parameters per line
    param_p_cnt=0 #count for multiple 'p' parameters per line
    while (len(line) > 0):
      #parsing based on FeederIOBoard/Protocol.cpp
      if line[0] == '?': #handshake
        print("Protocol: 0x%s,0x%s" % (line[1:5],line[5:9]))
        line="" #clear line

      elif line[0] == '~': #reset
        print("Resetting...")
        line="" #clear line

      elif line[0] == 'C': #command line
        print("Command: %s" % (line[1:]))
        line="" #clear line

      elif line[0] == 'D': #debug on
        print("Debug on:")
        line=line[1:] #remove command

      elif line[0] == 'd': #debug off
        print("Debug off:")
        line=line[1:] #remove command

      elif line[0] == 'E': #encoder
        #print("Set encoder %d to: 0x%s" % (param_e_cnt, line[1:9]))
        line=line[9:] #remove command and values

      elif line[0] == 'G': #hardware description
        bff_ser.write(hardware_str.encode('utf-8'))
        bff_ser.write("\n".encode('utf-8'))
        line="" #clear line

      elif line[0] == 'H': #halt streaming
        streaming=0
        print("Halt Streaming")
        line="" #clear line

      elif line[0] == 'I': #initialize
        bff_ser.write("RInitialization done\n".encode('utf-8'))
        line="" #clear line

      elif line[0] == 'O': #output
        #print("Set output %d to: 0x%s" % (param_o_cnt, line[1:3]))
        if param_o_cnt==1:
          pc_lamp=int(line[1:3], 16)
          pc_lamp_hdr_top=(pc_lamp>>7)&1 #3b7
          pc_lamp_hdr_bottom=(pc_lamp>>6)&1 #3b6
          pc_lamp_high=(pc_lamp>>3)&1 #3b3
          pc_lamp_low=(pc_lamp>>2)&1 #3b2
          pc_lamp_pilot=(pc_lamp>>1)&1 #3b1
          pc_lamp_boost=pc_lamp&1 #3b0
        param_o_cnt+=1
        line=line[3:] #remove command and values

      elif line[0] == 'P': #pwm
        #print("Set PWM %d to: 0x%s" % (param_p_cnt, line[1:4]))
        if param_p_cnt==0:
          pc_ffb=((int(line[1:4], 16)>>4)-0x80) #2b7:0
          #scale FFB value for stronger/weaker response
          pc_ffb*=ffb_scale
          #clip values to min and max
          if pc_ffb<-0x80:
            pc_ffb=-0x80
          elif pc_ffb>0x7F:
            pc_ffb=0x7F
          pc_ffb&=0xFF
          #print(line[1:4])
          #print(hex(pc_ffb))
        param_p_cnt+=1
        line=line[4:] #remove command and values

      elif line[0] == 'S': #start streaming
        streaming=1
        print("Start Streaming")
        line="" #clear line

      elif line[0] == 'T': #stop watchdog
        line="" #clear line

      elif line[0] == 'U': #status
        SendStatusFrame()
        line=line[1:] #remove command

      elif line[0] == 'V': #version
        print("Version: %s" % (line[1:]))
        bff_ser.write(version_str.encode('utf-8'))
        bff_ser.write("\n".encode('utf-8'))
        line="" #clear line

      elif line[0] == 'W': #start watchdog
        line="" #clear line

      else:
        print("Unhandled command")
        line="" #clear line

    if streaming==1:
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
      #pc_unk_5b70=0x80 #5b7:0, always 0x80 except 0x00 in first message
      #pc_unk_6b70=0xFF #6b7:0, always 0xFF except 0x84 in first set of messages
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
      bff_queue.put(b'\xc0') # write start
      for i in range(8):
        if pc_msg[i] == 0xC0: #replace with 0xDB 0xDC
          bff_queue.put(b'\xdb') # write byte
          bff_queue.put(b'\xdc') # write byte
        elif pc_msg[i] == 0xDB: #replace with 0xDB 0xDD
          bff_queue.put(b'\xdb') # write byte
          bff_queue.put(b'\xdd') # write byte
        else:
          bff_queue.put(bytes([pc_msg[i]])) # write byte
      bff_queue.put(bytes([csum&0xFF])) # write checksum
      bff_queue.put(bytes([csum>>8])) # write checksum
      bff_queue.put(b'\xc0') # write end


#sends re-encoded data to Diego, getting from bff_queue
def write_bff_output():
  while (True):
    time.sleep(0.001) #only check for new data every ~1 ms
    while (bff_queue.qsize() > 0):
      bff_tx_byte = bff_queue.get()
      #print(bff_tx_byte,end=' ')
      diego_ser.write(bytes(bff_tx_byte))


if len(sys.argv) != 4:
  print("Usage: ht_diego_bff.py <FFB multiplier> <Diego serial port> <BFF serial port>")
  sys.exit(1)

# grab multiplier value (2 seems to be good for full scale with BFF)
ffb_scale = int(sys.argv[1])

# open serial ports
diego_ser = serial.Serial(sys.argv[2], 38400) # open serial port
bff_ser = serial.Serial(sys.argv[3], 115200) # open serial port

# non-blocking serial I/O stuff
diego_queue = queue.Queue() # queue for Diego data output (to BFF)
bff_queue = queue.Queue() # queue for BFF data output (to Diego)
diego_rx_thread = threading.Thread(target=read_diego_input, daemon=True) # receives data from Diego
diego_tx_thread = threading.Thread(target=write_diego_output, daemon=True) # sends data to Diego
bff_rx_thread = threading.Thread(target=read_bff_input, daemon=True) # receives data from BFF
bff_tx_thread = threading.Thread(target=write_bff_output, daemon=True) # sends data to BFF

# start threads
diego_rx_thread.start()
diego_tx_thread.start()
bff_rx_thread.start()
bff_tx_thread.start()

print("Press any key to quit")
readchar.readkey()

diego_ser.close() # close port
bff_ser.close() # close port
