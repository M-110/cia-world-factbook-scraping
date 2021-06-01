from collections import defaultdict
from copy import copy
from pathlib import Path
from typing import Optional, Tuple, Iterator, Dict, List, Union
import re

from bs4 import BeautifulSoup
import bs4
import numpy as np

# For type hinting
Page = bs4.BeautifulSoup
Tag = bs4.Tag


def get_all_pages_from_index(index_page: str) -> List[Tuple[str, str]]:
    """Get a list of links from the index page.

    Args:
        index_page: location of the 'notesanddefs.html' file.

    Returns:
        List of tuples containing the relative link and the name of the page.
        For example:
            [('factbook-2020/fields/288.html', 'Land use'),
             ('factbook-2020/fields/402.html', 'Languages')]
    """
    with open(index_page, encoding='utf8') as f:
        index = BeautifulSoup(f, 'html.parser')

    pages = []
    for category in index.select('div.category'):
        if not (links := category.select('a')):
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
    # Get the category's html content.
    with open(Path(link), encoding='utf8') as f:
        page = BeautifulSoup(f, 'html.parser')

    # Get the subfields (columns) from the page and return their name and whether
    # each is a numeric type or text type.
    subfields = discover_all_subfields(name, page)

    if not subfields:
        raise ValueError('Subfields is empty')
    # TODO: Specific type.
    # Parse the page for the given subfields and return a
    return get_subfields_data(page, subfields)


# region scanning subfields for names/types

def discover_all_subfields(page_name: str, page: Page, threshold: int = 50) -> Dict[str, str]:
    """Searches a page and returns the name and type of subfields as a dict.
    
    If there are multiple subfields in a category, it will add the name
    of that subfield to the title of the category in parentheses. So for Area,
    if there are subfields for land, water and total, they will be titled
    'Area (Land)', 'Area (Water)' and 'Area (Total)'.

    Args:
        page_name: The category title for the page.
        page: BeautifulSoup instance containing html of the category's page.
        threshold: Minimum number of countries that must have a subfield for it
            to be included. Subfields that don't reach this threshold will
            be ignored.
      
    Returns:
        Dict[subfield name, subfield type]
                
    Example return:
        {'Area (Total)': 'Numeric', 'Area (Land)': 'Numeric' 'Area (Water)': 'Numeric'}
    """
    country_rows = (tag for tag in page.findAll('tr') if tag.has_attr('id'))

    numeric_field_names: Dict[str, int] = {}
    text_field_names: Dict[str, int] = {}

    # Iterate through each row and update the numeric_field_names and
    # text_field_names dictionaries. This is to track the count of
    # each subfield.
    for row in country_rows:
        for field in row.select('div'):
            discover_numeric_subfields(field, numeric_field_names)
            discover_text_subfields(field, text_field_names)

    # If it contains both types of fields, raise an exception because
    # handling this is not yet implemented.
    if numeric_field_names and text_field_names:
        raise ValueError(f"Numeric and text fields included in {page_name}.")

    numeric_subfield_dict: Dict[str, str] = create_subfield_dict(page_name,
                                                                 numeric_field_names,
                                                                 'numeric',
                                                                 threshold)

    text_subfield_dict: Dict[str, str] = create_subfield_dict(page_name,
                                                              text_field_names,
                                                              'text',
                                                              threshold)

    # If there is only one field, just use the page's category name as the
    # subfield name.
    if len(numeric_subfield_dict) == 1:
        return {page_name: 'numeric'}
    elif len(text_subfield_dict) == 1:
        return {page_name: 'text'}

    if numeric_subfield_dict:
        return numeric_subfield_dict
    else:
        return text_subfield_dict


def discover_numeric_subfields(field: Tag, numeric_field_names: Dict[str, int]):
    """Update numeric_field_names dict with count of each numeric field.
    
    Args:
        field: BeautifulSoup tag object representing an individual field in a
            country's row.
                
        numeric_field_names: Dictionary containing the current count of values
            for each numeric subfield name.
    """
    for numeric_field in field.select('div.numeric'):
        field_name = numeric_field.find('span', {'class': 'subfield-name'})
        if field_name is None:
            numeric_field_names['NO NAME'] = numeric_field_names.get('NO NAME', 0) + 1
            continue
        name = field_name.text
        numeric_field_names[name] = numeric_field_names.get(name, 0) + 1


def discover_text_subfields(field: Tag, text_field_names: Dict[str, int]):
    """Update text_field_names dict with count of each text field.
    
    Args:
        field: BeautifulSoup tag object representing an individual field in a
            country's row.
                
        text_field_names: Dictionary containing the current count of values
            for each text subfield name.
    """
    for text_field in field.select('div.text'):
        field_name = text_field.find('span', class_='subfield-name')
        if field_name is None:
            text_field_names['NO NAME'] = text_field_names.get('NO NAME', 0) + 1
            continue
        name = field_name.text
        text_field_names[name] = text_field_names.get(name, 0) + 1


def create_subfield_dict(page_name: str, field_names_dict: Dict[str, int],
                         field_type: str, threshold: int) -> Dict[str, str]:
    """Returns a dictionary containing subfield name and type for each subfield
    with more entries than the threshold.
    
    Args:
        page_name: Category name of the page.
        field_names_dict: Dictionary containing the field names and the number of
            references.
        field_type: Type of values in the field, 'numeric' or 'text'.
        threshold: Minimum threshold of reference counts for a field to be
            included in the subfield dict that is returned.
    Returns:
        Dict[str, str] in the form:
            {'Category Name (Subfield Name)': 'Subfield Type']
    """
    return {f'{page_name} ({clean_name(field)})': field_type
            for field, count in field_names_dict.items()
            if count > threshold}


# endregion

# region parsing subfields for data

def get_subfields_data(page: Page, subfields: Dict[str, str]
                       ) -> Dict[str, Dict[str, Union[str, float]]]:
    """Parse the page and return all the data from the given subfields.
    
    Args:
        page: BeautifulSoup instance containing html of the category's page.
        subfields: Dictionary of subfield names and their corresponding type.
        
    Returns:
        Dictionary containing the data on the page in the form:
        {'Subfield Name': {'Country Name': 'Subfield Value'}}
    """
    subfield_type: str = list(subfields.values())[0]
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
    return dataset


def parse_subfield(subfield: Tag, subfield_type: str) -> Union[str, float]:
    """Returns the field value as either a string or float depending on the
    given subfield_type."""
    if subfield_type == 'text':
        return parse_text_subfield(subfield)
    elif subfield_type == 'numeric':
        return parse_numeric_subfield(subfield)


def parse_text_subfield(subfield: Tag) -> str:
    """Returns a string containing the value in the given row's subfield."""
    try:
        subfield_copy = copy(subfield)
        for content in subfield_copy.find_all('span'):
            content.extract()
        text = subfield_copy.text
    except AttributeError:
        text = ''.join(subfield.findAll(text=True))
    # Remove any excess whitespace
    if not (output := re.sub(r'\s+', ' ', text).strip()):
        raise ValueError(f'Could not find any text in {subfield}')
    return output


def parse_numeric_subfield(subfield: Tag) -> float:
    """Returns a float containing the value in the given row's subfield."""
    try:
        # Some numbers are put in the notes instead for some reason.
        subfield_number = subfield.find(class_='subfield-number') or subfield.find(class_='subfield-note')
        number = subfield_number.text
    except AttributeError as e:
        print(f'**Attribute error for {subfield.get("id")!r}: ', e)
        print(f'\t {subfield}')
        return np.nan
    return str_to_float(number)


# endregion

# region helper functions

def str_to_float(text: str) -> float:
    """Strip text of non-numeric characters and return as a float.
    
    If % is included, divide value by 100.
    """
    text = text.replace(' ', '').replace(',', '')
    new_text = ''
    for char in text:
        if not (char.isdigit() or char in ['.', '-', '<', '>']):
            break
        new_text += char
    try:
        if '<' in new_text:
            number = float(new_text.replace('<', ''))
        else:
            number = float(new_text)
    except ValueError:
        if text.lower() in ['na', 'nan'] or 'na' in text.lower()[:2]:
            value = np.nan
        elif 'note' in text.lower():
            value = np.nan
        else:
            value = 0
        print(f'**Could not convert {text} to float. Returning {value}')
        return value
    if '%' in text:
        number = round(number / 100, 6)

    return number


def clean_name(string_: str) -> str:
    """"Returns string without extra white space and ':'."""
    return string_.strip().replace(':', '')


# endregion

if __name__ == "__main__":
    all_pages = get_all_pages_from_index('factbook-2020\\docs\\notesanddefs.html')
    for i in range(175, 200):
        target = all_pages[i]
        print(f'From {target} ({i})')
        cat = scrape_page(*target)
        print(cat)
        print(f'Subfields ({len(cat.keys())}): ', list(cat.keys()))
    print(f'From {target}')
    # with open('factbook-2020\\docs\\notesanddefs.html', encoding='utf8') as file:
    #     page = BeautifulSoup(file, 'html.parser')
    # 
    # with open('factbook-2020\\fields\\238.html') as file:
    #     page2 = BeautifulSoup(file, 'html.parser')

    # a = discover_subfields('Current Balance', page2, 50)
    # print(a)

# TODO LIST
"""
Problems to fix:
    17 Citizenship - Convert yes/no?
  X 21 Communications - Skip this
    29 Crude oil - production fix billion/million etc
  ##30 Account balance - two fields, no names, ugh
  ##33 Debt - ^^same problem
  X 37 Dependant areas note - Skip this
  ##41 Drinking water source: complicated set of sub-sub categories
  ##42 Afghanistan and Akotiri have multiple subfields instead of 1 like the others
  ##55 Numeric and text fields included
  ##59 Values given from multiple years, too many numerics ***Maybe raw data files can help with these
  ##60 Poorly formatted inconsistency
  ##61 Values given from multiple years, too many numerics
    66 fix billion/million etc
  ##67 Values given from multiple years, too many numerics
  ##70 Values given from multiple years, too many numerics
  ##71 Values given from multiple years, too many numerics
  X 74 Only two values, skip
  ##76 Values given from multiple years, too many numerics
  ##84 Values given from multiple years, too many numerics
  ##91 Values given from multiple years, too many numerics
  ##100 Numeric and text fields included
  ##106 Numeric and text fields included (maybe skip first text field?)
  X 111 Only three values, skip
    112 Mix of numbers and string descriptions, maybe just make this a string page?
  X 113 Only a few values, skip
    116 Mix of numbers and string descriptions
  ##122 Values given from multiple years, too many numerics
  X 139 Only a few values, skip
    143 Dhekelia population is a long description instead of a number
  ##148 Values given from multiple years, too many numerics
  ##156 Values given from multiple years, too many numerics
    158 Complicated, subfield within subfield
  ##169 Formatting weird. Text is outside of the subfield name span.
  X 170 Only a few values, skip
  ##171 Values given from multiple years, too many numerics
    174 Mix of numbers and string descriptions
    
    
    
  
  
  Other issues:
    Numeric values with <X are being replaced with X. Maybe this isn't accurate
  
  
  
Last thing I was doing:
    Going through numbers to check for errors.
"""
