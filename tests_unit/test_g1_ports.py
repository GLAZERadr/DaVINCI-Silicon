"""Regression tests for the G1 port check (agent/pipeline.py validate/ports).

live04-breakdown attempt 1 (2 Nov) was rejected with "extra ['v']": the
argument of its helper `function clog2` was read as a module port. The RTL
passes the frozen suite 10/10 (verify/recheck_g1.py). These tests keep that
design accepted and check that real port mistakes are still caught.

usage: python -m pytest tests_unit
"""
import re
from pathlib import Path

from agent import pipeline as p

FIX = Path(__file__).parent / "fixtures"
RTL = (FIX / "live04_breakdown_attempt1.v").read_text()


def test_live04_attempt1_rtl_passes_g1():
    assert p.validate(RTL) is None


def test_live04_attempt1_full_reply_passes_g1():
    # The whole model reply, ```verilog fence included, as the pipeline sees it.
    rtl, _ = p.extract((FIX / "live04_breakdown_attempt1_response.md").read_text())
    assert rtl == RTL
    assert p.validate(rtl) is None


def test_function_arguments_are_not_ports():
    code = p.COMMENTS.sub(" ", RTL)
    assert "v" not in p.ports(code)
    assert set(p.ports(code)) == {x["name"] for x in p.INTERFACE["ports"]}


def test_task_arguments_are_not_ports():
    rtl = RTL.replace("endmodule", "    task bump;\n        input [3:0] step;\n        begin end\n    endtask\nendmodule")
    assert p.validate(rtl) is None


def test_port_names_in_comments_are_ignored():
    rtl = RTL.replace("endmodule", "    // input wire ghost;\n    /* output reg phantom; */\nendmodule")
    assert p.validate(rtl) is None


def test_real_extra_port_is_still_rejected():
    rtl = RTL.replace("input  wire             clk,", "input  wire             clk,\n    input  wire             spare,", 1)
    assert "input  wire             clk," in RTL
    assert re.search(r"extra \['spare'\]", p.validate(rtl) or "")


def test_missing_port_is_still_rejected():
    rtl = re.sub(r"\n\s*output reg\s+\[CW-1:0\]\s+count", "", RTL, count=1)
    rtl = re.sub(r",\s*\n(\s*\);)", r"\n\1", rtl, count=1)
    assert re.search(r"missing \['count'\]", p.validate(rtl) or "")


def test_wrong_direction_is_still_rejected():
    rtl = RTL.replace("input  wire             rd_en", "output wire             rd_en", 1)
    assert "input  wire             rd_en" in RTL
    assert "wrong direction ['rd_en']" in (p.validate(rtl) or "")
