#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.boards.platforms import versa_ecp5

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.uart import UARTWishboneBridge

from litescope import LiteScopeAnalyzer

from liteeth.common import *
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from ecp5rgmii import LiteEthPHYRGMII

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_i = ClockDomain(reset_less=True)

        # # #

        # clk / rst
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")
        platform.add_period_constraint(clk100, 10.0)

        # pll
        self.submodules.pll = pll = ECP5PLL()
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll.locked | ~rst_n)


class BaseSoC(SoCCore):
    csr_map = {
        "ddrphy":    16,
        "analyzer":  17
    }
    csr_map.update(SoCCore.csr_map)
    def __init__(self, **kwargs):
        platform = versa_ecp5.Platform(toolchain="diamond")
        sys_clk_freq = int(133e6)
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
                          cpu_type=None, with_uart=False,
                          csr_data_width=32,
                          ident="Versa ECP5 test SoC", ident_version=True,
                          **kwargs)

        # crg
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # ethernet mac/udp/ip stack
        ethphy = LiteEthPHYRGMII(platform.request("eth_clocks"),
                        platform.request("eth"))
        ethcore = LiteEthUDPIPCore(ethphy,
                                   mac_address=0x10e2d5000000,
                                   ip_address=convert_ip("192.168.1.50"),
                                   clk_freq=sys_clk_freq,
                                   with_icmp=True)
        self.submodules += ethphy, ethcore

        # etherbone bridge
        self.submodules.etherbone = LiteEthEtherbone(ethcore.udp, 1234)
        self.add_wb_master(self.etherbone.wishbone.bus)

        ethphy.crg.cd_eth_rx.clk.attr.add("keep")
        ethphy.crg.cd_eth_tx.clk.attr.add("keep")
        platform.add_period_constraint(ethphy.crg.cd_eth_rx.clk, period_ns(125e6))
        platform.add_period_constraint(ethphy.crg.cd_eth_tx.clk, period_ns(125e6))

        # uart
        self.submodules.bridge = UARTWishboneBridge(platform.request("serial"), sys_clk_freq, baudrate=115200)
        self.add_wb_master(self.bridge.wishbone)

        # led blinking
        led_counter = Signal(32)
        self.sync += led_counter.eq(led_counter + 1)
        self.comb += platform.request("user_led", 0).eq(led_counter[26])

        # analyzer
        analyzer_signals = [
            Signal(16)
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 128)

    def do_exit(self, vns):
        if hasattr(self, "analyzer"):
            self.analyzer.export_csv(vns, "test/analyzer.csv")

def main():
    soc = BaseSoC()
    builder = Builder(soc, output_dir="build", csr_csv="test/csr.csv")
    vns = builder.build(toolchain_path="/usr/local/diamond/3.10_x64/bin/lin64")
    soc.do_exit(vns)


if __name__ == "__main__":
    main()
