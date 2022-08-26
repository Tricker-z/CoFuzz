#include <stdio.h>

#include "include/types.h"

void __log_branch(u32 prev_loc, u32 succ_true, u32 succ_false, u8* condition,
                  u32 taken) {
  /* Log the branch condition */

  if (taken)
    fprintf(stderr, "[*] (Br_true_%s): %d,%d\n", condition, prev_loc,
            succ_true);
  else
    fprintf(stderr, "[*] (Br_false_%s): %d,%d\n", condition, prev_loc,
            succ_false);
}

void __log_switch(u32 case_num, u32 bit_width, u32 prev_loc, u32 default_loc,
                  u8* case_cov, u32* case_loc) {
  /* Log the switch condition */

  u32 idx, dest_loc = 0;

  for (idx = 0; idx < case_num; idx++)
    if (case_cov[idx]) {
      dest_loc = case_loc[idx];
      break;
    }

  if (!dest_loc) dest_loc = default_loc;

  fprintf(stderr, "[*] (Switch_i%d_%d): %d,%d\n", bit_width, case_num, prev_loc,
          dest_loc);
}