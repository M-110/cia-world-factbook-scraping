import csv
import pandas as pd
import re

with open('factbook-2020\\fields\\rawdata_238.txt') as f:
    next(f)
    t = f.read()
    t = re.sub('\s{2,}', '\t', t)
    x = [g.split('\t')[1:3] for g in t.split('\n') if g]
