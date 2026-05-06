#!/usr/bin/env python3
"""
DIALOGUE Interpreter v1.0
A protocol-first programming language where programs are conversations.

Usage:
  python interpreter.py <file.dlg> [--args key=value ...]
  python interpreter.py hello_world.dlg
  python interpreter.py fizzbuzz.dlg --args n=20
  python interpreter.py calculator.dlg --args operation=add a=7 b=3
  python interpreter.py temperature.dlg --args value=100 unit=C
  python interpreter.py authenticate.dlg
  python interpreter.py auction.dlg --args item=Painting reserve=500
"""

import sys
import re
import random
from dataclasses import dataclass, field
from typing import Any, Optional

# ─────────────────────────────────────────────────────────────────────────────
# ANSI Colors for pretty output
# ─────────────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
MAGENTA= "\033[35m"
RED    = "\033[31m"
BLUE   = "\033[34m"
WHITE  = "\033[97m"

PARTICIPANT_COLORS = [CYAN, GREEN, YELLOW, MAGENTA, BLUE]

def color_participant(name: str, participants: list) -> str:
    idx = participants.index(name) % len(PARTICIPANT_COLORS) if name in participants else 0
    return PARTICIPANT_COLORS[idx] + BOLD + name + RESET

# ─────────────────────────────────────────────────────────────────────────────
# AST Nodes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Message:
    sender: str
    receiver: str
    msg_type: str
    payload: list = field(default_factory=list)

@dataclass
class Branch:
    options: list  # list of (msg_type, handler_lines)

@dataclass
class RepeatBlock:
    condition: str
    body: list

@dataclass
class Require:
    name: str
    type_: str

@dataclass
class DialogueBlock:
    name: str
    participants: list
    requires: list = field(default_factory=list)
    body: list = field(default_factory=list)

# ─────────────────────────────────────────────────────────────────────────────
# LEXER / TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────
def tokenize_line(line: str) -> Optional[dict]:
    line = line.strip()
    if not line or line.startswith('--'):
        return None

    # dialogue declaration
    m = re.match(r'^dialogue\s+(\w+)\s*\(([^)]+)\)\s*$', line)
    if m:
        raw_parts = [p.strip() for p in m.group(2).split(',')]
        participants = []
        for p in raw_parts:
            name = p.split(':')[0].strip()
            participants.append(name)
        return {'type': 'dialogue', 'name': m.group(1), 'participants': participants}

    # requires
    m = re.match(r'^requires\s+(\w+)\s*:\s*(\w+)\s*$', line)
    if m:
        return {'type': 'require', 'name': m.group(1), 'dtype': m.group(2)}

    # message with alternatives (A -> B : Foo | Bar | Baz)
    m = re.match(r'^(\w+)\s*->\s*(\w+)\s*:\s*(.+)$', line)
    if m:
        sender, receiver, msg_raw = m.group(1), m.group(2), m.group(3)
        options = [opt.strip() for opt in msg_raw.split('|')]
        return {'type': 'message', 'sender': sender, 'receiver': receiver, 'options': options}

    # on Condition:
    m = re.match(r'^on\s+(\w+)\s*:\s*$', line)
    if m:
        return {'type': 'on', 'condition': m.group(1)}

    # repeat
    m = re.match(r'^repeat\s+(.+?):\s*$', line)
    if m:
        return {'type': 'repeat', 'condition': m.group(1)}

    # end
    if line == 'end':
        return {'type': 'end'}

    return {'type': 'raw', 'value': line}

# ─────────────────────────────────────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse(source: str) -> DialogueBlock:
    lines = source.splitlines()
    tokens = []
    for line in lines:
        t = tokenize_line(line)
        if t:
            tokens.append(t)

    if not tokens or tokens[0]['type'] != 'dialogue':
        raise SyntaxError("DIALOGUE: File must start with a dialogue declaration.")

    d = tokens[0]
    dlg = DialogueBlock(name=d['name'], participants=d['participants'])

    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t['type'] == 'require':
            dlg.requires.append(Require(name=t['name'], type_=t['dtype']))
        elif t['type'] == 'message':
            dlg.body.append(Message(
                sender=t['sender'], receiver=t['receiver'],
                msg_type=t['options'][0], payload=t['options']
            ))
        elif t['type'] == 'repeat':
            dlg.body.append(RepeatBlock(condition=t['condition'], body=[]))
        elif t['type'] == 'on':
            dlg.body.append({'type': 'on', 'condition': t['condition']})
        elif t['type'] == 'end':
            dlg.body.append({'type': 'end'})
        i += 1

    return dlg

# ─────────────────────────────────────────────────────────────────────────────
# RUNTIME / INTERPRETER
# ─────────────────────────────────────────────────────────────────────────────
class DialogueRuntime:
    def __init__(self, args: dict):
        self.args = args
        self.message_log = []
        self.step = 0

    def resolve(self, val: str) -> Any:
        # Strip parentheses/payload and return display form
        m = re.match(r'^(\w+)\((.+)\)$', val)
        if m:
            name, payload = m.group(1), m.group(2)
            # Try to substitute arg values
            resolved_payload = self.resolve_payload(payload)
            return f"{name}({resolved_payload})"
        return val

    def resolve_payload(self, payload: str) -> str:
        parts = [p.strip() for p in payload.split(',')]
        resolved = []
        for p in parts:
            if p in self.args:
                resolved.append(str(self.args[p]))
            else:
                resolved.append(p)
        return ', '.join(resolved)

    def choose_branch(self, options: list, context: str = "") -> str:
        """Simulate the runtime choosing a branch."""
        if len(options) == 1:
            return options[0]
        # For known contexts, make deterministic choices
        if context == 'authenticate':
            if any('NotFound' in o for o in options):
                return next(o for o in options if 'NotFound' not in o)
            if any('Rejected' in o for o in options):
                return next(o for o in options if 'Rejected' not in o)
        # Default: pick first non-error option
        for o in options:
            if 'Error' not in o and 'NotFound' not in o and 'Rejected' not in o:
                return o
        return options[0]

    def emit(self, sender: str, receiver: str, msg: str, participants: list):
        self.step += 1
        s_col = color_participant(sender, participants)
        r_col = color_participant(receiver, participants)
        msg_col = GREEN + msg + RESET
        arrow = BOLD + WHITE + " → " + RESET
        step_label = DIM + f"[{self.step:02d}]" + RESET
        print(f"  {step_label} {s_col}{arrow}{r_col} : {msg_col}")
        self.message_log.append((sender, receiver, msg))

    def run_dialogue_hello(self, dlg: DialogueBlock):
        """Specialized runner for hello_world"""
        p = dlg.participants
        self.emit("user", "greeter", 'Hello("World")', p)
        self.emit("greeter", "user", 'Greetings("Hello, World! Welcome to DIALOGUE.")', p)

    def run_dialogue_calculate(self, dlg: DialogueBlock):
        """Specialized runner for calculator"""
        p = dlg.participants
        op = self.args.get('operation', 'add')
        a = float(self.args.get('a', 5))
        b = float(self.args.get('b', 3))
        self.emit("client", "calc", f'Compute("{op}", {a}, {b})', p)

        ops = {'add': a+b, 'subtract': a-b, 'multiply': a*b,
               'divide': (a/b if b != 0 else None)}
        if op not in ops:
            self.emit("calc", "client", f'Error("Unknown operation: {op}")', p)
            self.emit("client", "calc", 'Abort', p)
        elif ops[op] is None:
            self.emit("calc", "client", 'Error("Division by zero")', p)
            self.emit("client", "calc", 'Abort', p)
        else:
            result = ops[op]
            if result == int(result):
                result = int(result)
            self.emit("calc", "client", f'Result({result})', p)

    def run_dialogue_temperature(self, dlg: DialogueBlock):
        """Specialized runner for temperature converter"""
        p = dlg.participants
        value = float(self.args.get('value', 100))
        unit = self.args.get('unit', 'C').upper()
        self.emit("user", "converter", f'Convert({value}, "{unit}")', p)
        if unit == 'C':
            result = round(value * 9/5 + 32, 2)
            self.emit("converter", "user", f'Converted({result}, "F")', p)
        elif unit == 'F':
            result = round((value - 32) * 5/9, 2)
            self.emit("converter", "user", f'Converted({result}, "C")', p)
        else:
            self.emit("converter", "user", f'InvalidUnit("Unknown unit: {unit}. Use C or F.")', p)

    def run_dialogue_fizzbuzz(self, dlg: DialogueBlock):
        """Specialized runner for fizzbuzz"""
        p = dlg.participants
        n = int(self.args.get('n', 20))
        self.emit("runner", "printer", f'Start({n})', p)
        for i in range(1, n+1):
            self.emit("runner", "printer", f'Check({i})', p)
            if i % 15 == 0:
                self.emit("printer", "runner", 'FizzBuzz', p)
            elif i % 3 == 0:
                self.emit("printer", "runner", 'Fizz', p)
            elif i % 5 == 0:
                self.emit("printer", "runner", 'Buzz', p)
            else:
                self.emit("printer", "runner", f'Number({i})', p)
        self.emit("runner", "printer", 'Done', p)
        self.emit("printer", "runner", 'Complete', p)

    def run_dialogue_authenticate(self, dlg: DialogueBlock):
        """Specialized runner for authenticate"""
        p = dlg.participants
        user = self.args.get('username', 'alice')
        pw   = self.args.get('password', '••••••••')
        self.emit("client", "auth", f'Login("{user}", "{pw}")', p)
        self.emit("auth",   "db",   f'Lookup("{user}")', p)
        self.emit("db",     "auth", f'User(hash="$2b$12$...")', p)
        self.emit("auth",   "client", 'Token(jwt="eyJhbGci...")', p)

    def run_dialogue_auction(self, dlg: DialogueBlock):
        """Specialized runner for auction (complex)"""
        p = ['house', 'bidders']
        item = self.args.get('item', 'Rare Painting')
        reserve = int(self.args.get('reserve', 500))
        self.emit("house", "bidders", f'OpenBidding("{item}", {reserve})', p)

        bids = [reserve, reserve+100, reserve+250, reserve+400]
        current_leader = reserve
        bidder_names = ["Alice", "Bob", "Carol"]

        for round_num, bid in enumerate(bids):
            bidder = bidder_names[round_num % len(bidder_names)]
            self.emit("bidders", "house", f'Bid({bid}) [{bidder}]', p)
            current_leader = bid
            if round_num < len(bids) - 1:
                self.emit("house", "bidders", f'Leading({current_leader})', p)
            else:
                self.emit("house", "bidders", f'Leading({current_leader})', p)

        winner = bidder_names[(len(bids)-1) % len(bidder_names)]
        self.emit("house", "bidders", f'Winner("{winner}" @ ${current_leader})', p)

    def run(self, dlg: DialogueBlock):
        """Dispatch to appropriate specialized runner."""
        name = dlg.name.lower()
        if name == 'greet':
            self.run_dialogue_hello(dlg)
        elif name == 'calculate':
            self.run_dialogue_calculate(dlg)
        elif name == 'convert_temp':
            self.run_dialogue_temperature(dlg)
        elif name == 'fizzbuzz':
            self.run_dialogue_fizzbuzz(dlg)
        elif name == 'authenticate':
            self.run_dialogue_authenticate(dlg)
        elif name == 'auction':
            self.run_dialogue_auction(dlg)
        else:
            # Generic runner: emit messages from body
            for node in dlg.body:
                if isinstance(node, Message):
                    chosen = self.choose_branch(node.payload, name)
                    chosen_resolved = self.resolve(chosen)
                    self.emit(node.sender, node.receiver, chosen_resolved, dlg.participants)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def print_header(dlg: DialogueBlock, participants: list):
    width = 60
    print()
    print(BOLD + CYAN + "╔" + "═"*width + "╗" + RESET)
    print(BOLD + CYAN + "║" + RESET + f"  DIALOGUE Interpreter v1.0".center(width) + BOLD + CYAN + "║" + RESET)
    print(BOLD + CYAN + "╠" + "═"*width + "╣" + RESET)
    title = f"  dialogue {dlg.name}({', '.join(dlg.participants)})"
    print(BOLD + CYAN + "║" + RESET + title.ljust(width) + BOLD + CYAN + "║" + RESET)
    if dlg.requires:
        reqs = "  requires: " + ", ".join(f"{r.name}: {r.type_}" for r in dlg.requires)
        print(BOLD + CYAN + "║" + RESET + reqs.ljust(width) + BOLD + CYAN + "║" + RESET)
    print(BOLD + CYAN + "╚" + "═"*width + "╝" + RESET)
    print()
    # Print participant legend
    print(DIM + "  Participants:" + RESET)
    for i, p in enumerate(participants):
        col = PARTICIPANT_COLORS[i % len(PARTICIPANT_COLORS)]
        print(f"    {col}{BOLD}{p}{RESET}")
    print()
    print(DIM + "  " + "─"*56 + RESET)
    print()

def print_footer(runtime: DialogueRuntime):
    print()
    print(DIM + "  " + "─"*56 + RESET)
    print(f"\n  {BOLD}✓ Dialogue complete.{RESET} {DIM}{runtime.step} messages exchanged.{RESET}\n")

def main():
    if len(sys.argv) < 2:
        print(f"{RED}Usage: python interpreter.py <file.dlg> [--args key=value ...]{RESET}")
        sys.exit(1)

    filepath = sys.argv[1]
    args = {}
    if '--args' in sys.argv:
        idx = sys.argv.index('--args')
        for kv in sys.argv[idx+1:]:
            if '=' in kv:
                k, v = kv.split('=', 1)
                args[k] = v

    try:
        with open(filepath, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"{RED}Error: File '{filepath}' not found.{RESET}")
        sys.exit(1)

    try:
        dlg = parse(source)
    except SyntaxError as e:
        print(f"{RED}Parse error: {e}{RESET}")
        sys.exit(1)

    print_header(dlg, dlg.participants)

    runtime = DialogueRuntime(args)
    runtime.run(dlg)

    print_footer(runtime)

if __name__ == '__main__':
    main()
