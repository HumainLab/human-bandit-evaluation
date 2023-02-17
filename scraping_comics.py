from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import requests
import os
import pickle
from argparse import ArgumentParser
from collections import OrderedDict
import time


def collected(comic_name, category):
    collected = False

    with open('/home/leqil/comicMount/comics/collected_comics.log', 'r') as file:
        lines = file.readlines()
        
    if len(lines) == 0:
        with open('/home/leqil/comicMount/comics/collected_comics.log', 'w') as file:
            file.writelines(comic_name + ': ' + category + '\n')
        return collected
    else:
        for idx, line in enumerate(lines):
            tokens = line.split(':')
            if tokens[0] == comic_name:
                collected = True
                lines[idx] = line.replace('\n', '') + ', ' + category + '\n'
                with open('/home/leqil/comicMount/comics/collected_comics.log', 'w') as file:
                    file.writelines(lines)
                return collected
    
        with open('/home/leqil/comicMount/comics/collected_comics.log', 'w') as file:
            lines.append(comic_name + ': ' + category + '\n')
            file.writelines(lines)
        return collected
    


def scrap_comics(category):
    go_comics_url = 'https://www.gocomics.com'


    if not os.path.exists('/home/leqil/comicMount/comics/' + category):
        os.makedirs('/home/leqil/comicMount/comics/' + category)

    print ('----', category, '----')
    category_urls = []
    category_url = go_comics_url + '/comics/' + category
    category_urls.append(category_url)
    
    category_req = Request(category_url)
    category_req.add_header('User-Agent', 'Mozilla/5.0')
    category_page = urlopen(category_req)
    
    category_html = category_page.read().decode("utf-8")
    category_soup = BeautifulSoup(category_html, "html.parser")
    category_total_pages = category_soup.select("[class=gc-pagination__item]")
    for page in category_total_pages:
        category_urls.append(go_comics_url + page['href'])
    
    category_urls = list(OrderedDict.fromkeys(category_urls))
    print (category_urls)
    
    for category_url in category_urls:
        print ('--', category_url, '--')
        category_req = Request(category_url)
        category_req.add_header('User-Agent', 'Mozilla/5.0')
        category_page = urlopen(category_req)
        
        time.sleep(1)
        category_html = category_page.read().decode("utf-8")
        category_soup = BeautifulSoup(category_html, "html.parser")
        current_page_comics = category_soup.select("[class=gc-blended-link\ gc-blended-link--primary]")
        
        
        for comic in current_page_comics:
            comic_name = comic['href'].split('/')[1]
            
            comic_dict = {}
            comic_dict['name'] = comic_name
            comic_dict['category'] = category
            
            current_comic_url = ''
            if not os.path.exists('/home/leqil/comicMount/comics/' + category + '/' + comic_name):
                os.makedirs('/home/leqil/comicMount/comics/' + category + '/' + comic_name)
            
            
                if not collected(comic_name, category):
                    comic_url = go_comics_url + '/' + comic_name

                    comic_req = Request(comic_url)
                    comic_req.add_header('User-Agent', 'Mozilla/5.0')
                    comic_page = urlopen(comic_req)
                    time.sleep(5)

                    comic_html = comic_page.read().decode("utf-8")
                    comic_soup = BeautifulSoup(comic_html, "html.parser")
                    comic_dict['html'] = comic_html

                    comic_earliest_url = ''
                    comic_current_year = 2021
                    comic_current_month = 12
                    comic_current_day = 31

                    for date_url_entry in comic_soup.select('[class=gc-blended-link\ gc-blended-link--primary]'):
                        date_url = date_url_entry['href']
                        tokens = date_url.split('/')

                        if len(tokens) == 5 and ('http' not in tokens[0]):
                            tmp_year = tokens[2]
                            try:
                                if int(tmp_year) <= comic_current_year:
                                    comic_current_year = int(tmp_year)
                                    tmp_month = tokens[3]
                                    comic_earliest_url = date_url
                                    if int (tmp_month) <= comic_current_month:
                                        comic_current_month = int(tmp_month)
                                        tmp_day = tokens[4]
                                        comic_earliest_url = date_url
                                        if int (tmp_day) <= comic_current_day:
                                            comic_current_day = int(tmp_day)
                                            comic_earliest_url = date_url
                            except:
                                print ('comic year extracting error: ', tokens)
                    print (comic_name, comic_earliest_url)
                    comic_dict['earliest_url'] = comic_earliest_url
                    current_comic_url = 'https://www.gocomics.com' + comic_earliest_url

                    while True:
                        time.sleep(5)
                        current_comic_req = Request(current_comic_url)
                        current_comic_req.add_header('User-Agent', 'Mozilla/5.0')
                        current_comic_page = urlopen(current_comic_req)

                        current_comic_html = current_comic_page.read().decode("utf-8")
                        current_comic_soup = BeautifulSoup(current_comic_html, "html.parser")

                        my_comic = current_comic_soup.select('[itemtype=http\:\/\/schema\.org\/CreativeWork]')[0]
                        comic_dict[current_comic_url] = {}
                        comic_dict[current_comic_url]['image_url'] = my_comic.get_attribute_list('data-image')[0]
                        comic_dict[current_comic_url]['likes'] = int(current_comic_soup.select('[class=js-like]')[0].get_text())
                        comic_dict[current_comic_url]['favorites'] = int(
                            current_comic_soup.select('[class=js-favorite]')[0].get_text())
                        try: 
                            comic_dict[current_comic_url]['comments'] = int(current_comic_soup.select(
                                '[class=gc-comment-toggle]')[0].get_text())
                        except:
                            comic_dict[current_comic_url]['comments'] = None
                        comic_dict[current_comic_url]['date'] = my_comic.get_attribute_list(
                            'data-formatted-date')[0].replace(', ', '_').replace(' ', '_')

                        #download the image, pickle once in a while
                        img_data = requests.get(comic_dict[current_comic_url]['image_url'] ).content
                        with open( '/home/leqil/comicMount/comics/' + category + '/' + comic_name + '/'+ 
                                  comic_dict[current_comic_url]['date'] +'.jpg', 'wb') as handler:
                            handler.write(img_data)


                        if len(current_comic_soup.select(
                        '[class=fa\ btn\ btn-outline-secondary\ btn-circle\ fa-caret-right\ sm\ disabled]')) == 1:
                            break

                        next_comic_date = current_comic_soup.select(
                            '[class=fa\ btn\ btn-outline-secondary\ btn-circle\ fa-caret-right\ sm]')[0]['href']
                        current_comic_url = 'https://www.gocomics.com' + next_comic_date
                #else:


                with open('/home/leqil/comicMount/comics/' + category + '/' + comic_name + '/' + comic_name + '.pickle', 'wb') as handle:
                    pickle.dump(comic_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
            else: 
                print ('/home/leqil/comicMount/comics/' + category + '/' + comic_name + '... already exists') # pass this comic, already has downloaded comcis + saved picle
                
def main():
    os.environ['https_proxy'] = 'http://proxy.cmu.edu:3128/'
    
    parser = ArgumentParser()
    parser.add_argument("-cat", "--category", dest="category")

    args = parser.parse_args()
    
    scrap_comics(args.category)
    
    
if __name__ == '__main__':
    main()