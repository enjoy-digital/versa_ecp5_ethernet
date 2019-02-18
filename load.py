#!/usr/bin/env python3

import os

os.system("python3 openocd/bit_to_svf.py build/gateware/top.bit top.svf")
os.system("openocd -f openocd/ecp5-versa5g.cfg -c \"transport select jtag; init; svf top.svf; exit\"")
