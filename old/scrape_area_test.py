from bs4 import BeautifulSoup
from typing import Optional, Tuple
page = None
with open('../factbook-2020/fields/341.html') as page:
    page = BeautifulSoup(page, 'html.parser')
    
#cols = page.findAll('div', {'class': 'appendix-entry-name'})
#for col in cols:
#    text = col.text.strip()
#    links = col.select('a')
#    if links:
#        print(text, links[0]['href'])
        
"all_data = {'field name' : {coutry_code : value} ...}"

a = page.find('tr', {'id': 'CO'}).findAll('span', {'class': 'subfield-number'})

b = page.find('tr', {'id': 'CO'})\
        .find('div', {'id': 'field-area'})\
        .findAll('div', {'class': 'subfield'})
        
def to_float(string_: str) -> float:
    string_ = string_.replace(',', '').replace(' ', '')
    float_string = ''
    for char in string_.strip():
        if char.isdigit() or char == '.':
            float_string += char
        else:
            break
    return float(float_string)

def discover_fields(page):
    pass
    

def clean_name(string_: str) -> str:
    return string_.strip().replace(':', '')
    

def get_values(page: BeautifulSoup, symbol: str) -> dict:
    subfields = page.find('tr', {'id': symbol})\
                    .find('div', {'id': 'field-area'})\
                    .findAll('div', {'class': 'subfield'})
    output = {}
    for subfield in subfields:
        name, value = convert_numeric(subfield)
        output[f'{name} area'] = value
    return output
        
def convert_numeric(subfield) -> Tuple[str, float]:
    name_field = subfield.find('span', {'class': 'subfield-name'})
    if name_field:
        name = clean_name(name_field.text)
    else:
        name = None
    value_field = subfield.find('span', {'class': 'subfield-number'}).text
    value = to_float(value_field)
    return name, value
    
    
a = get_values(page, 'AX')

print(a)