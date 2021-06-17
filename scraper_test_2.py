from collections import defaultdict
from copy import copy
import os
from pathlib import Path
from typing import Optional, Tuple, Iterator, Dict, List, Union
import re

from bs4 import BeautifulSoup
import bs4
import numpy as np

# For type hinting
Page = bs4.BeautifulSoup
Tag = bs4.Tag

# Skip these pages because they dont' have many rows.
SKIP_LIST = ['factbook-2020/fields/205.html',
             'factbook-2020/fields/304.html',
             ]
dog = 0


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


def scrape_page(name: str, link: str) -> Dict[str, Dict[str, Union[str, float]]]:
    """Scrape a specific category's page and return its data.

    Args:
        name: the name of the category.
        link: the relative link to the category's html file.
    """
    # TODO: Add unique parser
    if name in ['sanitation, etc']:
        return subgroup_parser(name, link)
    return html_parser(name, link)


def subgroup_parser(name: str, link: str) -> Dict[str, Dict[str, float]]:
    """Scrape a category's page which involves subgroups and return its data.

    Args:
        name: the name of the category.
        link: the relative link to the category's html file.
    """
    with open(Path(link), encoding='utf8') as f:
        page = BeautifulSoup(f, 'html.parser')

    dataset = defaultdict(dict)
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
                    dataset[f'{name} {group} ({subgroup})'][row_id] = \
                        round(float(span.text[:span.text.find('%')]) / 100, 6)
    return dataset


def currency_page_parser(link: str):
    with open(link, encoding='utf8') as f:
        page = BeautifulSoup(f, 'html.parser')

    data = defaultdict(dict)
    for tag in page.findAll('tr'):
        if row_id := tag.get('id'):
            currency = tag.div.div.text.strip().replace('note: ', '')
            if 'per US dollar' in currency:
                currency = currency[:currency.find('per US dollar')]
            elif 'uses the euro' in currency:
                currency = 'euros (EUR)'
            data['Currency'][row_id] = currency.strip()

            try:
                exchange_rate = tag.select('span')[0].text.replace(',', '')
            except IndexError:
                if 'US dollar' in d['Currency'][row_id]:
                    exchange_rate = 1.0
                elif 'euros' in d['Currency'][row_id]:
                    exchange_rate = 0.82771
                else:
                    exchange_rate = float('nan')
            data['Exchange rate'][row_id] = float(exchange_rate)
    data['Currency']['US'] = 'the US dollar is used'
    data['Exchange rate']['US'] = 1.0
    data['Currency']['EC'] = 'the US dollar is used'
    data['Exchange rate']['EC'] = 1.0
    data['Currency']['TB'] = 'euros (EUR)'
    data['Exchange rate']['TB'] = 0.82771
    data['Currency']['GZ'] = 'new Israeli shekels (ILS)'
    data['Exchange rate']['GZ'] = 3.606
    return data


def html_parser(name: str, link: str) -> Dict[str, Dict[str, Union[str, float]]]:
    """Parse an html file and return the data."""
    # Get the category's html content.
    with open(Path(link), encoding='utf8') as f:
        page = BeautifulSoup(f, 'html.parser')

    # Get the subfields (columns) from the page and return their name and whether
    # each is a numeric type or text type.
    subfields = discover_all_subfields(name, page)

    if not subfields:
        raise ValueError('Subfields is empty')
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
    print(numeric_field_names)
    print(text_field_names)
    # If it contains both types of fields, raise an exception because
    # handling this is not yet implemented.
    # if numeric_field_names and text_field_names:
    #     raise ValueError(f"Numeric and text fields included in {page_name}.")

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
    if len(numeric_subfield_dict) == 1 and not text_subfield_dict:
        return {page_name: 'numeric'}
    elif len(text_subfield_dict) == 1 and not numeric_subfield_dict:
        return {page_name: 'text'}
    return numeric_subfield_dict | text_subfield_dict


def discover_numeric_subfields(field: Tag, numeric_field_names: Dict[str, int]):
    """Update numeric_field_names dict with count of each numeric field.
    
    Args:
        field: BeautifulSoup tag object representing an individual field in a
            country's row.
                
        numeric_field_names: Dictionary containing the current count of values
            for each numeric subfield name.
    """
    for numeric_field in field.select('div.numeric') or field.select('span.subfield-number'):
        field_name = numeric_field.find('span', {'class': 'subfield-name'})
        if field_name is None:
            numeric_field_names['NO NAME'] = numeric_field_names.get('NO NAME', 0) + 1
            continue
        name = field_name.text
        if '(' in name:
            name = name[:name.find('(') + 1].strip()
        numeric_field_names[name] = numeric_field_names.get(name, 0) + 1

    if len(numeric_field_names) > 1 and numeric_field_names.get('NO NAME'):
        del numeric_field_names['NO NAME']


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
        if '(' in name:
            name = name[:name.find('(') + 1].strip()
        text_field_names[name] = text_field_names.get(name, 0) + 1

    if len(text_field_names) > 1 and text_field_names.get('NO NAME'):
        del text_field_names['NO NAME']


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
    all_rows = page.findAll('tr')
    dataset = defaultdict(dict)

    for row in all_rows:
        if not (row_id := row.get('id')):
            continue
        for subfield in row.select('div.subfield'):
            if len(subfields) > 1:
                for subfield_name, subfield_type in subfields.items():
                    try:
                        if clean_name(subfield.find(class_='subfield-name').text) in subfield_name:
                            dataset[subfield_name][row_id] = parse_subfield(subfield, subfield_type)
                    except AttributeError:
                        print(f'No text found in {subfield}')
                        break
            else:
                subfield_type = list(subfields.values())[0]
                dataset[list(subfields)[0]][row_id] = parse_subfield(subfield, subfield_type)
                break
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
        print(f'Could not find any text in {subfield}, returning "NA".')
        output = 'NA'
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
    text = (text.replace(' ', '')
            .replace(',', '')
            .replace('$', '')
            .replace('approximately', '')
            .strip())
    multiplier = (1E12 if 'trillion' in text else
                  1E9 if 'billion' in text else
                  1E6 if 'million' in text else
                  1)
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
            value = np.nan
        print(f'**Could not convert {text} to float. Returning {value}')
        return value
    if '%' in text:
        number = round(number / 100, 6)

    return number * multiplier


def clean_name(string_: str) -> str:
    """"Returns string without extra white space, ':' and removes parentheses."""
    string_ = string_[:string_.find('(')]
    return string_.replace(':', '').strip()


# endregion

if __name__ == "__main__":
    all_pages = get_all_pages_from_index('factbook-2020\\docs\\notesanddefs.html')
    for i in [158]:
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
    CURRENTLY: 41, 59, 158


    SKIP:
        21, 37, 74, 111, 113, 139, 170
    
    -----------------------------------
        
    (FIXED: Only using most recent data) Multiple year values given:
        30, 33, 59, 61, 67, 70, 71, 76, 84, 91, 122, 148, 156, 171
        
    Formatting Complications:
        41, sub-sub categories
        (FIXED) 42, inconsistent subfields (afghanistan and akotiri)
        59, exchange has a string and numeric uncategorized field
        158, sub-subfield
        (FIXED)169, text outside of span
        
    (FIXED) Mix of number and string descriptions:
        55 (3 nubmber subfields, but two are called text), 59, 100 (total is always number), X106 (definition is a string),
         X112, X116, X174
        
    One-off:
        (FIXED)143, Dhekelia population is a long description rather than number
        
    (FIXED) Billion/million fix:
        29, 66
        
  
  Other issues:
    Numeric values with <X are being replaced with X. Maybe this isn't accurate
  
  
  
Last thing I was doing:
    I need to implement a rawdata parser which will be used if a txt file exists
    for the page.
"""
