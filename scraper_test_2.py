from bs4 import BeautifulSoup
import bs4
from typing import Optional, Tuple, Iterator, Dict, List, Union
from pathlib import Path
from collections import defaultdict
import re
import numpy as np

Page = bs4.BeautifulSoup



with open('factbook-2020\\fields\\279.html') as file:
    page = BeautifulSoup(file, 'html.parser')
with open('factbook-2020\\fields\\199.html') as file:
    page2 = BeautifulSoup(file, 'html.parser')
    
    
def clean_name(string_: str) -> str:
    """"Returns string without extra white space and ':'."""
    return string_.strip().replace(':', '')



# TODO: Rename discover all subfields
def discover_subfields(page_name: str, page: Page, threshold: int = 50) -> Dict[str, str]:
    """Searches a page and returns the name and type of subfields as a dict.
    
    If there are multiple subfields in a category, it will add the name
    of that subfield to the title of the category in parentheses. So for Area,
    if there are subfields for land, water and total, they will be titled
    'Area (Land)', 'Area (Water)' and 'Area (Total)'.

    Args:
        page_name: The category title for the page.
        page: BeautifulSoup instance containing html of a category's page.
        threshold: minimum number of countries that must have this subfield 
                   to count it.
      
    Returns:
        Dict[subfield name, subfield type]
                
    Example return:
        {'Area (Total)': 'Numeric', 'Area (Land)': 'Numeric' 'Area (Water)': 'Numeric'}
    """
    country_rows = (tag for tag in page.findAll('tr') if tag.has_attr('id'))
    
    numeric_field_names: Dict[str, int] = {}
    text_field_names: Dict[str, int]  = {}
    
    for row in country_rows:
        #for field in row.select('div', {'id': 'field-area'}):
        for field in row.select('div'):
            # Scan Numeric
            discover_numeric_subfields(field, numeric_field_names)
            discover_text_subfields(field, text_field_names)
    
    if numeric_field_names and text_field_names:
        raise ValueError(f"Numeric and text fields included in {page_name}.")
            
    numeric_subfield_dict: Dict[str, str] = create_subfield_dict(page_name,
                                                                 numeric_field_names,
                                                                 'numeric')
    
    text_subfield_dict: Dict[str, str] = create_subfield_dict(page_name,
                                                              text_field_names,
                                                              'text')
    if len(numeric_subfield_dict) == 1:
        return {page_name: 'numeric'}
    elif len(text_subfield_dict) == 1:
        return {page_name: 'text'}
    
    if numeric_subfield_dict:
        return numeric_subfield_dict
    else:
        return text_subfield_dict
       

def discover_numeric_subfields(field, numeric_field_names: Dict[str, int]):
    """Update numeeric_field_names dict with count of each numeric field."""
    for numeric_field in field.select('div.numeric'):
        field_name = numeric_field.find('span', {'class': 'subfield-name'})
        if field_name is None:
            numeric_field_names['NO NAME'] = numeric_field_names.get('NO NAME', 0) + 1
            continue
        name = field_name.text
        numeric_field_names[name] = numeric_field_names.get(name, 0) + 1


def discover_text_subfields(field, text_field_names: Dict[str, int]):
    """Update text_field_names dict with count of each text field."""
    for text_field in field.select('div.text'):
        field_name = text_field.find('span', class_='subfield-name')
        if field_name is None:
            text_field_names['NO NAME'] = text_field_names.get('NO NAME', 0) + 1
            continue
        name = field_name.text
        text_field_names[name] = text_field_names.get(name, 0) + 1
         

def create_subfield_dict(page_name: str, field_names_dict: Dict[str, int],
                         field_type: str) -> Dict[str, str]:
    """Returns dict containing subfield name and type for each subfield
    with more entries than the threshold."""
    return {f'{page_name} ({clean_name(field)})': field_type
            for field, count in field_names_dict.items()
            if count > 50}


def get_pages_from_index(index_page: str) -> List[Tuple[str, str]]:
    """Get a list of links from the index page.
    
    Args:
        index_page: location of the 'notesanddefs.html' file.
        
    Returns:
        List of tuples containing the relative link and the name of the page.
        For example: 
            [('../fields/288.html', 'Land use'),
             ('../fields/402.html', 'Languages')]
    """
    pages = []
    with open(index_page, encoding='utf8') as f:
        index = BeautifulSoup(f, 'html.parser')
        
    for category in index.select('div.category'):
        links = category.select('a')
        if not links:
            continue
        link = links[0]['href'].replace('..', 'factbook-2020')
        name = category.text.strip()
        pages.append((name, link))
    return pages
        
def scrape_page(name: str, link: str):
    """Scrape a specific category's page and return its data.
    
    Args:
        name: the name of the category.
        link: the relative link to the category's html file.
    """
    with open(Path(link), encoding='utf8') as f:
        page = BeautifulSoup(f, 'html.parser')
    subfields = discover_subfields(name, page)
    if not subfields:
        raise ValueError('Subfields is empty')
    return get_subfields_data(page, subfields)
    
def get_subfields_data(page: Page, subfields: dict) -> Dict[str, Union[str, float]]:
    """Get the data.
    """
    subfield_type: str =  list(subfields.values())[0]
    all_rows = page.findAll('tr')
    dataset = defaultdict(dict)
    for row in all_rows:
        if not (row_id := row.get('id')):
            continue
        for subfield in row.select('div.subfield'):
            if len(subfields) > 1:
                for subfield_name in subfields:
                    if clean_name(subfield.find(class_='subfield-name').text) in subfield_name:
                        dataset[subfield_name][row_id] = parse_subfield(subfield, subfield_type)
            else:
                dataset[list(subfields)[0]][row_id] = parse_subfield(subfield, subfield_type)
    print(dataset)
    return dataset
        
def parse_subfield(subfield, subfield_type: str):
    """Returns the data using two parsers depending on subfield type."""
    if subfield_type == 'text':
        return parse_text_subfield(subfield)
    elif subfield_type == 'numeric':
        return parse_numeric_subfield(subfield)
        

def parse_text_subfield(subfield):
    try:
        text = subfield.find(class_='text').span.text
    except AttributeError:
        text = ''.join(subfield.findAll(text=True))
    # Remove any excess whitespace
    if not (output := re.sub(r'\s+', ' ', text).strip()):
        print('****Could not return.')
        print('**********', subfield)
        raise ValueError('Could not find any text')
    return output

def parse_numeric_subfield(subfield):
    try:
        # Some numbers are put in the notes intead for some reason.
        subfield_number = subfield.find(class_='subfield-number') or subfield.find(class_='subfield-note')
        number = subfield_number.text
    except AttributeError as e:
        print(f'**Attribute error for {subfield.get("id")!r}: ', e)
        print(f'\t {subfield}')
        return np.nan
    return str_to_float(number)
    
def str_to_float(text: str) -> float:
    """Strip text of non-numeric characters and return as a float.
    
    If % is included, divide value by 100.
    """
    text = text.replace(' ', '').replace(',', '')
    new_text = ''
    for char in text:
        if not (char.isdigit() or char == '.' or char == '-'):
            break
        new_text += char
    try:
        number = float(new_text)
    except ValueError as e:
        if text.lower() in ['na', 'nan']:
            value = np.nan
        else:
            value = 0
        print(f'**Could not convert {text} to float. Returning {value}')
        return value
    if '%' in text:
        number =  round(number / 100, 6)
        
    return number
    

dog = get_pages_from_index('factbook-2020\\docs\\notesanddefs.html')

#target = dog[11]
#cat = scrape_page(*target)
#print(cat.keys())
#print(len(dog))
#print(f'From {target}')
with open('factbook-2020\\docs\\notesanddefs.html', encoding='utf8') as file:
    page = BeautifulSoup(file, 'html.parser')

a = discover_subfields('Broadcast', page2, 50)
print(a)


"""
TODO:
   #14 Capital - multiple text subfields*****
    17 Citizenship - Convert yes/no?
    18 Civil aircraft prefix - Remove (2016)
  ##21 Communcations - note ???????????????? ************
   #22 Constrituion - multiple textsbufields *****
   #24 Country name - multiple textsubfields *****
   #25 Credit ratings - multiple textsubfields, remove (DATE)
   #30 Account balance - fix float conversion, billion million etc.
   #33 Debt - "                                               "
  ##37 Dependant areas note ???????????????
   
   

    
"""

