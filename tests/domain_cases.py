from app.catalog import SPEC
from app.domain.calculate import calculate_rows
from app.domain.decision import decide_rows
from app.domain.prepare import prepare_rows
from app.intake.service import load

CLEAN = [{'ticket_id': 'T1',
  'passenger_id': 'P1',
  'action': 'REFUND',
  'original_fare_cents': '10000',
  'taxes_cents': '2000',
  'change_fee_cents': '0',
  'refundable': 'Y',
  'new_fare_cents': '0',
  'invoice_cents': '-12000'},
 {'ticket_id': 'T2',
  'passenger_id': 'P2',
  'action': 'REFUND',
  'original_fare_cents': '8000',
  'taxes_cents': '1500',
  'change_fee_cents': '500',
  'refundable': 'N',
  'new_fare_cents': '0',
  'invoice_cents': '-1000'},
 {'ticket_id': 'T3',
  'passenger_id': 'P3',
  'action': 'REISSUE',
  'original_fare_cents': '10000',
  'taxes_cents': '2000',
  'change_fee_cents': '800',
  'refundable': 'Y',
  'new_fare_cents': '12000',
  'invoice_cents': '2800'},
 {'ticket_id': 'T4',
  'passenger_id': 'P4',
  'action': 'REISSUE',
  'original_fare_cents': '7000',
  'taxes_cents': '1500',
  'change_fee_cents': '500',
  'refundable': 'N',
  'new_fare_cents': '8000',
  'invoice_cents': '8500'},
 {'ticket_id': 'T5',
  'passenger_id': 'P5',
  'action': 'REFUND',
  'original_fare_cents': '5000',
  'taxes_cents': '1000',
  'change_fee_cents': '5000',
  'refundable': 'Y',
  'new_fare_cents': '0',
  'invoice_cents': '-1000'},
 {'ticket_id': 'T6',
  'passenger_id': 'P6',
  'action': 'REISSUE',
  'original_fare_cents': '5000',
  'taxes_cents': '1000',
  'change_fee_cents': '300',
  'refundable': 'Y',
  'new_fare_cents': '4000',
  'invoice_cents': '300'}]


def row(**changes):
    item = dict(CLEAN[0])
    item.update(changes)
    return item


def calc(rows):
    items, issues = prepare_rows(rows)
    return calculate_rows(items), issues


def run(rows):
    items, issues = prepare_rows(rows)
    return decide_rows(calculate_rows(items)), issues


def run_profile(profile):
    return run(load(profile)["rows"])
