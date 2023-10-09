//Decompiled Hydro.exe using Ghidra
//below are several functions relevant to Diego/PC communications, with some comments added as I traced through them



/////     Tx from PC     /////

//FUN_000ba772 populates Tx array with data then calls FUN_000baba9
//FUN_000baba9 looks to create payload then calls FUN_000bad19
//FUN_000bad19 looks like Fletcher 16 checksum, which calls FUN_000baf25 at the end to SLIP encode

void FUN_000ba772(void)
{
  byte local_14;
  undefined local_13;
  undefined local_12;
  undefined local_11;
  undefined local_10;
  byte local_f;
  undefined local_e;
  int local_c;
  undefined4 local_8;
  
  local_8 = FUN_00098158(0);
  _DAT_00719c20 = _DAT_00719c20 + 1;
  _memset(&local_14,0,8); //clear array
  local_11 = DAT_00603949; //array[3] byte, lamps
  local_10 = DAT_0060394a; //array[4] byte, pattern of shifting 1s in lower 4 bits
  local_12 = DAT_00603948; //array[2] byte, force feedback
  local_f = DAT_0060394e | DAT_00603950; //array[5], DAT_0060394e always 0 and DAT_00603950 uses bit 7
  local_e = DAT_0060394f; //array[6] byte
  local_14 = local_14 | DAT_00603951; //array[0], DAT_00603951 uses bit 6
  if (DAT_00603935 == '\0') {
    for (local_c = 0; local_c < 3; local_c = local_c + 1) {
      if (*(int *)(local_c * 4 + 0x603938) != 0) {
        *(int *)(local_c * 4 + 0x603938) = *(int *)(local_c * 4 + 0x603938) + -1;
        DAT_00603934 = DAT_00603934 ^ 0x10;
        DAT_00603935 = '\x01';
        _DAT_00603944 = local_c + 1;
        break;
      }
    }
  }
  local_13 = DAT_00603944; //array[1] byte, DAT_00603944 should be 0-3
  local_14 = local_14 | DAT_00603934 | DAT_00603961 | DAT_00603960 |
             (byte)((uint)_DAT_0060395c >> 0x1e); //array[0], DAT_00603934 bit 4, DAT_00603961 bit 5 (security clock), DAT_00603960 bit 2 (security reset), _DAT_0060395c in bits 1 and 0 (2 security bits shifted out MSbits first), (bits 7 and 3 unused)
  FUN_00098158(local_8);
  FUN_000baba9(0,&local_14,8);
  return;
}

//param_1 passed through to output (always 0)
//param_2 is data array (always length 8)
//param_3 is length of array (always 8)
void FUN_000baba9(undefined4 param_1,byte *param_2,undefined4 param_3)
{
  byte bVar1; //bVar1 gets set to random garbage
  char cVar2; //parity bit
  
  *param_2 = *param_2 & 0xf7; //clear bit 3 of param_2[0]
  bVar1 = FUN_000d9c38(); //randomize
  *param_2 = *param_2 | bVar1 & 8; //put random val into bit 3 of param_2[0]
  param_2[1] = param_2[1] & 3; //clear bits 2-7 of param_2[1]
  bVar1 = FUN_000d9c38(); //randomize
  param_2[1] = param_2[1] | bVar1 & 0xfc; //put random val into bits 2-7 of param_2[1]
  bVar1 = FUN_000d9c38(); //randomize
  param_2[7] = bVar1; //entire param_2[7] byte is random
  *param_2 = *param_2 & 0x7f; //mask off upper bit of param_2[0] and use for parity
  cVar2 = FUN_000bac91(param_2,8); //compute parity
  if (cVar2 != '\0') { //if odd
    *param_2 = *param_2 | 0x80; //set MSb of param_2[0]
  }
  FUN_000bad19(param_1,param_2,param_3); //add checksum, then SLIP encode
  return;
}


/////     Rx from Diego     /////

//callback function probably calls FUN_000baff9 on Rx, which does SLIP substitutions, and calls FUN_000badf7 at the end
//FUN_000badf7 calls FUN_000baec7 to check Fletcher checksum, and if passes, calls FUN_000bac4e
//FUN_000bac4e confirms message has length of 8, calls FUN_000bac91 to check parity, and if passes, calls FUN_000ba8af to decode

//param_1 is data array, which has gone through checksum and parity checks
void FUN_000ba8af(byte *param_1)
{
  bool bVar1;
  int local_14;
  byte local_10 [8];
  uint local_8;
  
  _DAT_00719c1c = _DAT_00719c1c + 1;
  DAT_0060394b = param_1[4]; //entire param_1[4] byte used
  DAT_0060394c = param_1[3]; //entire param_1[3] byte used
  DAT_0060394d = param_1[6]; //entire param_1[6] byte used
  //grab pieces of other param_1 bytes into local array for coin1 through coin5
  local_10[0] = param_1[2] & 7; //param_1[2] bits 0 through 2
  local_10[1] = (byte)((int)(uint)param_1[2] >> 3) & 7; //param_1[2] bits 3 through 5
  local_10[2] = (byte)((int)(uint)param_1[2] >> 6) | (byte)((param_1[1] & 1) << 2); //param_1[1] bit 0 and param_1[2] bits 6 and 7
  local_10[3] = (byte)((int)(uint)param_1[1] >> 1) & 7; //param_1[1] bits 1 through 3
  local_10[4] = (byte)((int)(uint)param_1[1] >> 4) & 7; //param_1[1] bits 4 through 6
  for (local_14 = 0; local_14 < 5; local_14 = local_14 + 1) { //loop over array checking for 0x00
    if (local_10[local_14] == 0) { //value of 0
      *(undefined4 *)(local_14 * 4 + 0x603920) = 0; //coin count is 0 if never used
    }
    else { //value not 0
      while ((uint)local_10[local_14] != *(uint *)(local_14 * 4 + 0x603920)) {
        *(int *)(local_14 * 4 + 0x60390c) = *(int *)(local_14 * 4 + 0x60390c) + 1; //increment some value
        *(int *)(local_14 * 4 + 0x603920) = *(int *)(local_14 * 4 + 0x603920) + 1; //increment some value
        if (*(int *)(local_14 * 4 + 0x603920) == 8) {
          *(undefined4 *)(local_14 * 4 + 0x603920) = 1; //coin count rolls over from 7 to 1
        }
      }
    }
  }
  if ((DAT_00603935 != '\0') &&
     (local_8 = local_8 & 0xffffff00 | *param_1 & 0xffffff10,
     (*param_1 & 0x10) == (uint)DAT_00603934)) { //param_1[0] bit 4
    DAT_00603935 = '\0';
    _DAT_00603944 = 0;
  }
  if ((DAT_00603952 != '\0') &&
     (local_8 = local_8 & 0xffffff00 | *param_1 & 0xffffff40,
     (*param_1 & 0x40) == (uint)DAT_00603951)) { //param_1[0] bit 6
    DAT_00603952 = '\0';
    bVar1 = DAT_00603950 == -0x80;
    if (bVar1) {
      DAT_0060394f = param_1[5]; //entire param_1[5] byte used
    }
    DAT_00603950 = -0x80;
    if (_DAT_00603904 != (code *)0x0) {
      (*_DAT_00603904)(DAT_0060394e,DAT_0060394f,bVar1);
    }
  }
  DAT_0060395a = *param_1 & 0x20; //param_1[0] bit 5, security clock
  if (DAT_0060395a != DAT_00603961) {
    _DAT_0060395c = _DAT_0060395c << 2;
    DAT_00603961 = DAT_00603961 ^ 0x20;
    DAT_00603960 = 0;
    if ((*param_1 & 4) != 0) { //param_1[0] bit 2, security reset
      DAT_00603958 = 0;
      DAT_00603959 = '\x04';
    }
    _DAT_00603954 = _DAT_00603954 << 2 | *param_1 & 3; //param_1[0] bits 1 and 0, shift security bits into 32-bit word (MSbits first)
    DAT_00603958 = DAT_00603958 + 2;
    if (((DAT_00603958 & 0x1f) == 0) && //word full
       (_DAT_0060395c = (*_DAT_00603908)(_DAT_00603954,DAT_00603959), DAT_00603959 != '\0')) {
      DAT_00603959 = '\0';
      DAT_00603960 = 4;
    }
  }
  return;
}
