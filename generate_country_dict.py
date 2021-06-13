from bs4 import BeautifulSoup

with open('factbook-2020/fields/279.html', encoding='utf8') as f:
    page = BeautifulSoup(f, 'html.parser')
