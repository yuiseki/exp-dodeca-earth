"""The firmware's pin and address tables for hub6_one rev E must match the board that make.py draws.

    ../../.venv/bin/python -m pytest -q test_board_matches_firmware.py
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MAKE = os.path.join(HERE, "..", "..", "hardware", "hub6_one", "make.py")
INO = os.path.join(HERE, "hub6_bench.ino")


def make_constant(name):
    """A dict literal assigned at the top level of make.py."""
    tree = ast.parse(open(MAKE).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def firmware_block(define):
    """The lines between `#ifdef define` / `#elif defined(define)` and the next #elif/#else/#endif."""
    text = open(INO).read()
    m = re.search(r"#(?:ifdef|elif defined\()\s*" + define + r"\)?\n(.*?)\n#(?:elif|else|endif)", text, re.S)
    assert m, define
    return m.group(1)


def test_rev_e_address_matches_cs_output():
    # display d's chip select is U1 pin p, which is output Y(15 - p): the firmware's ADDRESS[d]
    cs_output = make_constant("CS_OUTPUT")
    block = firmware_block("HUB6_ONE_REV_E")
    addr = [int(x) for x in re.search(r"ADDRESS\[NUM_DISPLAYS\] = \{([^}]*)\}", block).group(1).split(",")]
    assert addr == [15 - cs_output[d] for d in range(6)]


def test_rev_e_address_pins_match_xiao_nets():
    nets = make_constant("XIAO_NETS")
    pin_of = {v: k for k, v in nets.items()}
    block = firmware_block("HUB6_ONE_REV_E")
    for k in range(3):
        assert re.search(rf"PIN_A{k} = {pin_of[f'LCD_A{k}']}\b", block), k
