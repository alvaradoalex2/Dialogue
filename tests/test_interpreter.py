# tests/test_interpreter.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from interpreter import parse, DialogueRuntime

def run(filename, args={}):
    """Helper: parse a .dlg file and return the message log."""
    path = os.path.join(os.path.dirname(__file__), '..', filename)
    with open(path) as f:
        source = f.read()
    dlg = parse(source)
    rt = DialogueRuntime(args)
    rt.run(dlg)
    return rt.message_log  # list of (sender, receiver, message) tuples

# ── Hello World ──────────────────────────────────────────────
def test_hello_world_message_count():
    log = run('hello_world.dlg')
    assert len(log) == 2

def test_hello_world_participants():
    log = run('hello_world.dlg')
    assert log[0][0] == 'user'
    assert log[0][1] == 'greeter'

def test_hello_world_greeting_content():
    log = run('hello_world.dlg')
    assert 'Hello' in log[0][2]
    assert 'Greetings' in log[1][2]

# ── Calculator ───────────────────────────────────────────────
def test_calculator_multiply():
    log = run('calculator.dlg', {'operation': 'multiply', 'a': '7', 'b': '6'})
    assert any('42' in msg for _, _, msg in log)

def test_calculator_add():
    log = run('calculator.dlg', {'operation': 'add', 'a': '10', 'b': '5'})
    assert any('15' in msg for _, _, msg in log)

def test_calculator_divide_by_zero():
    log = run('calculator.dlg', {'operation': 'divide', 'a': '5', 'b': '0'})
    assert any('Error' in msg for _, _, msg in log)
    assert any('Abort' in msg for _, _, msg in log)

# ── Temperature Converter ────────────────────────────────────
def test_temp_celsius_to_fahrenheit():
    log = run('temperature.dlg', {'value': '100', 'unit': 'C'})
    assert any('212' in msg for _, _, msg in log)

def test_temp_fahrenheit_to_celsius():
    log = run('temperature.dlg', {'value': '32', 'unit': 'F'})
    assert any('0' in msg for _, _, msg in log)

def test_temp_invalid_unit():
    log = run('temperature.dlg', {'value': '100', 'unit': 'K'})
    assert any('InvalidUnit' in msg for _, _, msg in log)

# ── FizzBuzz ─────────────────────────────────────────────────
def test_fizzbuzz_message_count():
    n = 15
    log = run('fizzbuzz.dlg', {'n': str(n)})
    # Start + (Check + Response)*n + Done + Complete
    assert len(log) == 1 + n * 2 + 2

def test_fizzbuzz_fizz_at_3():
    log = run('fizzbuzz.dlg', {'n': '3'})
    assert log[-3][2] == 'Fizz'  # response to Check(3)

def test_fizzbuzz_buzz_at_5():
    log = run('fizzbuzz.dlg', {'n': '5'})
    assert log[-3][2] == 'Buzz'

def test_fizzbuzz_fizzbuzz_at_15():
    log = run('fizzbuzz.dlg', {'n': '15'})
    assert log[-3][2] == 'FizzBuzz'

# ── Authentication ───────────────────────────────────────────
def test_auth_succeeds():
    log = run('authenticate.dlg', {'username': 'alice'})
    assert any('Token' in msg for _, _, msg in log)

def test_auth_message_flow():
    log = run('authenticate.dlg', {'username': 'alice'})
    senders = [s for s, _, _ in log]
    assert senders == ['client', 'auth', 'db', 'auth']

# ── Auction ──────────────────────────────────────────────────
def test_auction_has_winner():
    log = run('auction.dlg', {'item': 'Vase', 'reserve': '100'})
    assert any('Winner' in msg for _, _, msg in log)

def test_auction_opens_with_item():
    log = run('auction.dlg', {'item': 'Vase', 'reserve': '100'})
    assert 'OpenBidding' in log[0][2]
    assert 'Vase' in log[0][2]