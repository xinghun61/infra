#!/usr/bin/python


import os
import sys
import json
import csv
import argparse

def to_json(in_csv_file, out_json_file):
  badges = []
  with open(in_csv_file) as csv_file:
    reader = csv.reader(csv_file)
    reader.next()  # Read the header
    for row in reader:
      name, lv1, lv2, lv3, asc, title, icon, desc = row
      badges.append({
        'badge_name': name,
        'level_1': int(lv1),
        'level_2': int(lv2),
        'level_3': int(lv3),
        'title': title,
        'description': desc,
        'icon': icon,
      })
  with open(out_json_file, 'w') as f:
    json.dump(badges, f)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('input_csv_file', nargs=1)
  parser.add_argument('output_json_file', nargs=1)
  args = parser.parse_args()
  return to_json(args.input_csv_file[0], args.output_json_file[0])


if __name__ == '__main__':
  sys.exit(main())
