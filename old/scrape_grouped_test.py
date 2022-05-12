from collections import defaultdict

from bs4 import BeautifulSoup

with open('../factbook-2020/fields/398.html') as f:
    page = BeautifulSoup(f, 'html.parser')

d = defaultdict(dict)
for tag in page.findAll('tr'):
    if row_id := tag.get('id'):
        group, subgroup = None, None
        for span in tag.select('span'):
            if 'subfield-group' in span.get('class'):
                group = span.text.replace(':', '')
                continue
            if 'subfield-name' in span.get('class'):
                subgroup = span.text.replace(':', '')
                continue
            elif 'subfield-number' in span.get('class'):
                d[f'Sanitation Facility Access {group} ({subgroup})'][row_id] = \
                    round(float(span.text[:span.text.find('%')]) / 100, 6)

with open('../factbook-2020/fields/249.html') as f:
    page = BeautifulSoup(f, 'html.parser')

d = defaultdict(dict)
for tag in page.findAll('tr'):
    if row_id := tag.get('id'):
        group, subgroup = None, None
        for span in tag.select('span'):
            if 'subfield-group' in span.get('class'):
                group = span.text.replace(':', '')
                continue
            if 'subfield-name' in span.get('class'):
                subgroup = span.text.replace(':', '')
                continue
            elif 'subfield-number' in span.get('class'):
                try:
                    d[f'Sanitation Facility Access {group} ({subgroup})'][row_id] = \
                        round(float(span.text[:span.text.find('%')]) / 100, 6)
                except ValueError:
                    d[f'Sanitation Facility Access {group} ({subgroup})'][row_id] = span.text

with open('../factbook-2020/fields/284.html') as f:
    page = BeautifulSoup(f, 'html.parser')

d = defaultdict(dict)
for tag in page.findAll('tr'):
    if row_id := tag.get('id'):
        currency = tag.div.div.text.strip().replace('note: ', '')
        if 'per US dollar' in currency:
            currency = currency[:currency.find('per US dollar')]
        elif 'uses the euro' in currency:
            currency = 'euros (EUR)'
        d['Currency'][row_id] = currency.strip()
        
        try:
            exchange_rate = tag.select('span')[0].text.replace(',', '')
        except IndexError:
            if 'US dollar' in d['Currency'][row_id]:
                exchange_rate = 1.0
            elif 'euros' in d['Currency'][row_id]:
                exchange_rate = 0.82771
            else:
                exchange_rate = float('nan')
        d['Exchange rate'][row_id] = float(exchange_rate)
d['Currency']['US'] = 'the US dollar is used'
d['Exchange rate']['US'] = 1.0
d['Currency']['EC'] = 'the US dollar is used'
d['Exchange rate']['EC'] = 1.0
d['Currency']['TB'] = 'euros (EUR)'
d['Exchange rate']['TB'] = 0.82771
d['Currency']['GZ'] = 'new Israeli shekels (ILS)'
d['Exchange rate']['GZ'] = 3.606
