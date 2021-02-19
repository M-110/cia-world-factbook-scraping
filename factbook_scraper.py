from bs4 import BeautifulSoup

with open(r'D:\Downloads\factbook-2020\factbook-2020\docs\notesanddefs.html') as page:
    page = BeautifulSoup(page, 'html.parser')
    
cols = page.findAll('div', {'class': 'appendix-entry-name'})
for col in cols:
    text = col.text.strip()
    links = col.select('a')
    if links:
        print(text, links[0]['href'])
        
"all_data = {'field name' : {coutry_code : value} ...}"