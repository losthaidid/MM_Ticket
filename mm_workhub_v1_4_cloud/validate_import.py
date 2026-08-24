from __future__ import annotations

import argparse
from importer import import_workbook
from db import fetch_all

parser = argparse.ArgumentParser(description='Validate an MM WorkHub workbook migration.')
parser.add_argument('workbook', help='Path to MM Tickets.xlsm/xlsx')
args = parser.parse_args()

stats = import_workbook(args.workbook, reset=True)
print('Imported:', stats)
print('Pending tickets:')
for row in fetch_all("""
SELECT ams_ticket, description, object_status, action_status
FROM tickets WHERE lower(coalesce(status,''))='pending'
ORDER BY ams_ticket
"""):
    print(f"- {row['ams_ticket']}: {row['object_status']} / {row['action_status']} — {row['description']}")
