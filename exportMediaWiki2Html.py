#!/usr/bin/python3

# Author: Timotheus Pokorra <timotheus.pokorra@solidcharity.com>
# source hosted at https://github.com/SolidCharity/exportMediaWiki2HTML
# licensed under the MIT license
# Copyright 2020-2021 Timotheus Pokorra

from urllib import parse
import requests
import json
import re
import os
from pathlib import Path
from shutil import copy, copytree
from pprint import pprint
from collections import defaultdict
import argparse

description = """
Export MediaWiki pages to HTML
Call like this:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org

   Optionally pass the page id of the page you want to download, eg. for debugging:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --page=180

   Optionally pass the category id, all pages with that category will be exported:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --category=22

   Optionally pass the username and password:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --username=myuser --password=topsecret
"""
parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument('-l','--url', help='The url of the wiki',required=True)
parser.add_argument('-u','--username', help='Your user name',required=False)
parser.add_argument('-p','--password', help='Your password',required=False)
parser.add_argument('-c','--category', help='The category to export',required=False)
parser.add_argument('-g','--page', help='The page to export',required=False)
parser.add_argument('-n', '--numberOfPages', help='The number of pages to export, or max', required=False, default=500)
parser.add_argument('-o', '--exportPath', help='Where to export to', required=False)
parser.add_argument('--image', help='String used to indicate if a link is to an image', required=False, default='Image')
parser.add_argument('--file', help='String used to indicate if a link is to a file', required=False, default='File')
parser.add_argument('--removeEditLinks', help='Remove edit links',required=False, default=False)
parser.add_argument('--removeSrcset', help='Remove srcset image attributes',required=False, default=True)
parser.add_argument('--fixShortUrl', help='Wheter the wiki is configured to use shortUrls or not. Used to fix internal links',required=False, default=False)
parser.add_argument('--enableIndex', help='Creates index file with a link to all downloaded pages',required=False, default=True)
parser.add_argument('--debug', help='Enables debug output',required=False, default=False)
args = parser.parse_args()

file_path = os.path.abspath(os.path.dirname(__file__)) + '/'

# load templates
header = Path(file_path + 'templates/header.html').read_text()
footer = Path(file_path + 'templates/footer.html').read_text()

###############
# Handle arguments
###############

if args.exportPath:
  export_path = args.exportPath
  if export_path[-1] != '/':
    export_path = export_path + '/'
else:
  export_path = file_path + 'export/'

Path(export_path + "img/").mkdir(parents=True, exist_ok=True)

if args.removeEditLinks:
  removeEditLinks = True
else:
  removeEditLinks = False

if args.removeSrcset:
  removeSrcset = True
else:
  removeSrcset = False

if args.fixShortUrl:
  fixShortUrl = True
else:
  fixShortUrl = False

if args.enableIndex:
  enableIndex = True
else:
  enableIndex = False

if args.image[-1] == ':':
  imageIndicator = args.image
else:
  imageIndicator = args.image + ':'

if args.file[-1] == ':':
  fileIndicator = args.file
else:
  fileIndicator = args.file + ':'

if args.numberOfPages != "max":
  try:
    int(args.numberOfPages)
    numberOfPages = str(args.numberOfPages)
  except ValueError:
      print("Provided number of pages is invalid")
      exit(-1)
else:
  numberOfPages = "max"

if args.debug:
  debug = True
else:
  debug = False

url = args.url
if not url.endswith('/'):
  url = url + '/'

api_url = f'{url}api.php'

pageOnly = -1
categoryOnly = -1
if args.category is not None:
  categoryOnly = int(args.category)
if args.page is not None:
  pageOnly = int(args.page)

###############
# Helper functions
###############

downloadedimages = []
def DownloadImage(filename, urlimg):
  if not filename in downloadedimages:
    if debug:
      print(f'Downloading {filename}')
    if '/thumb/' in urlimg:
      urlimg = urlimg.replace('/thumb/', '/')
      urlimg = urlimg[:urlimg.rindex('/')]
    response = S.get(url + urlimg)
    content = response.content
    f = open(export_path + "img/" + filename, "wb")
    f.write(content)
    f.close()
    downloadedimages.append(filename)

downloadedPages = []
def PageTitleToFilename(title):
    temp = re.sub('[^A-Za-z0-9\u0400-\u0500]+', '_', title)
    return temp.replace("(","_").replace(")","_").replace("__", "_")

pagesPerCategory = defaultdict(list)

# fetch page content from API
def getPageContent(pageName):
  params = {
    'action': 'parse',
    'prop': 'text|categories',
    'formatversion': '2',
    'format': 'json',
    'page': pageName
  }

  response = S.get(api_url, params = params)

  if debug:
    pprint(response.json())

  if not 'parse' in response.json():
    print("Error while fetching from api")
    pprint(response.json())
    return None, None

  if 'text' in response.json()['parse']:
    return (response.json()['parse']['text'], response.json()['parse']['categories'])

  return None, None

# Downloads images, and replaces links with relative references
def cleanupContent(content):
  pos = 0

  if removeEditLinks:
    while '<span class="mw-editsection">' in content:
      pos = content.find('<span class="mw-editsection">')
      pos_end_bracket = content.find(']', pos)
      pos_end_edit = content.find('</span>', pos_end_bracket)
      content = content[:pos] + content[pos_end_edit:]

  if removeSrcset:
    content = re.sub('srcset=\"[a-zA-Z0-9:;-_\.\s\(\)\-\,\/%]*\"', '', content, flags=re.IGNORECASE)

  if fixShortUrl and 'href="/' in content:
    content = content.replace('href="/', f'href="{url}index.php?title=')

  #pprint(content)

  while f'{url}index.php?title=' in content:
      pos = content.find(f'{url}index.php?title=')
      posendquote = content.find('"', pos)
      linkedpage = content[pos:posendquote]
      linkedpage = linkedpage[linkedpage.find('=') + 1:]

      if linkedpage.startswith(fileIndicator) or linkedpage.startswith(imageIndicator):
        downloadName = linkedpage.replace('%27', '_')
        if linkedpage.startswith(fileIndicator):
            linkType = fileIndicator
            downloadName = downloadName.replace(fileIndicator, '')
        if linkedpage.startswith(imageIndicator):
            linkType = imageIndicator
            downloadName = downloadName.replace(imageIndicator, '')
        origlinkedpage = linkedpage[linkedpage.find(':')+1:]
        linkedpage = parse.unquote(origlinkedpage)
        imgpos = content.find('src="/images/', posendquote)

        if imgpos > posendquote:
          imgendquote = content.find('"', imgpos+len(linkType))
          imgpath = content[imgpos+len(linkType) - 1:imgendquote]
        else:
          imgpath = linkedpage.replace('%27', '_')

        if not downloadName in downloadedimages:
          DownloadImage(downloadName, imgpath)

        if downloadName in downloadedimages:
          content = content.replace(f'{url}index.php?title={linkType}{origlinkedpage}', f'img/{downloadName}')
          content = content.replace(imgpath, f'img/{downloadName}')
        else:
          print("Error: not an image? " + linkedpage)
          exit(-1)

      elif "&amp;action=edit&amp;redlink=1" in linkedpage:
        content = content[:pos] + 'article_not_existing.html" style="color:red;"' + content[posendquote+1:]
      elif "#" in linkedpage:
        linkWithoutAnchor = linkedpage[0:linkedpage.find('#')]
        linkWithoutAnchor = PageTitleToFilename(linkWithoutAnchor)
        content = content[:pos] + linkWithoutAnchor + ".html#" + linkedpage[linkedpage.find('#')+1:] + content[posendquote:]
      else:
        linkedpage = PageTitleToFilename(parse.unquote(linkedpage))
        content = content[:pos] + linkedpage + ".html" + content[posendquote:]

  content = re.sub("(<!--).*?(-->)", '', content, flags=re.DOTALL)

  return content


###############
# Here starts the logic
###############

S = requests.Session()

if args.username is not None and args.password is not None:
  if debug:
    print(f'Trying to login using {args.username}')
  LgUser = args.username
  LgPassword = args.password

  # Retrieve login token first
  params_login_token = {
      'action':"query",
      'meta':"tokens",
      'type':"login",
      'format':"json"
  }
  R = S.get(url=api_url, params=params_login_token)
  DATA = R.json()
  LOGIN_TOKEN = DATA['query']['tokens']['logintoken']

  # Main-account login via "action=login" is deprecated and may stop working without warning. To continue login with "action=login", see [[Special:BotPasswords]]
  params_login = {
      'action':"login",
      'lgname':LgUser,
      'lgpassword':LgPassword,
      'lgtoken':LOGIN_TOKEN,
      'format':"json"
  }

  R = S.post(api_url, data=params_login)
  DATA = R.json()
  if "error" in DATA:
    print(DATA)
    exit(-1)

if categoryOnly != -1:
  params_all_pages = {
    'action': 'query',
    'list': 'categorymembers',
    'format': 'json',
    'cmpageid': categoryOnly,
    'cmlimit': numberOfPages
  }
else:
  params_all_pages = {
    'action': 'query',
    'list': 'allpages',
    'format': 'json',
    'aplimit': numberOfPages
  }

response = S.get(api_url, params=params_all_pages)
data = response.json()

if "error" in data:
  pprint(data)
  if data['error']['code'] == "readapidenied":
    print()
    print(f'get login token here: {url}/api.php?action=query&meta=tokens&type=login')
    print("and then call this script with parameters: myuser topsecret mytoken")
    exit(-1)

if categoryOnly != -1:
  pages = data['query']['categorymembers']
else:
  pages = data['query']['allpages']

while 'continue' in data and (numberOfPages == 'max' or len(pages) < int(numberOfPages)):
  if categoryOnly != -1:
    params_all_pages['cmcontinue'] = data['continue']['cmcontinue']
  else:
    params_all_pages['apcontinue'] = data['continue']['apcontinue']

  response = S.get(api_url, params=params_all_pages)

  data = response.json()

  if "error" in data:
    pprint(data)
    if data['error']['code'] == "readapidenied":
      print()
      print(f'get login token here: {url}/api.php?action=query&meta=tokens&type=login')
      print("and then call this script with parameters: myuser topsecret mytoken")
      exit(-1)

  if categoryOnly != -1:
    pages.extend(data['query']['categorymembers'])
  else:
    pages.extend(data['query']['allpages'])

for page in pages:
  if (pageOnly > -1) and (page['pageid'] != pageOnly):
      continue
  print(page)

  content, categories = getPageContent(page['title'])
  if content is None:
    content = '<p>No content on this page</p>'

  content = cleanupContent(content)

  pageFilename = PageTitleToFilename(page['title']) + '.html'
  with open(export_path + pageFilename, "wb") as f:
    f.write(header.replace('#TITLE#', page['title']).encode("utf8"))
    if enableIndex:
      f.write('<a href="./index.html">Back to index</a>\n'.encode("utf8"))
    f.write(content.encode('utf8'))

    # Add category page links to bottom
    if isinstance(categories, list):
      f.write('<nav><ul>'.encode("utf8"))
      for categoryItem in categories:
        category = categoryItem['category']
        categoryPageName = PageTitleToFilename(f'Kategorie:{category}') + '.html'
        f.write(f'<li><a href="{categoryPageName}">{category}</a></li>\n'.encode('utf8'))
      f.write('</ul></nav>'.encode("utf8"))

    f.write(footer.encode("utf8"))
    f.close()

  downloadedPages.append((pageFilename, page['title']))
  if isinstance(categories, list):
    for categoryItem in categories:
      category = categoryItem.get('category')
      if debug:
        pprint(category)

      pagesPerCategory[category].append((pageFilename, page['title']))

###############
# Create index page
###############
if enableIndex:
  # Write index file for easier overview
  with open(export_path + "index.html", "wb") as f:
    f.write(header.replace('#TITLE#', 'Index').encode("utf8"))

    for key in sorted(pagesPerCategory.keys()):
      f.write(f'<details>\n<summary>{key}</summary>\n<ul>\n'.encode('utf8'))
      for (filename, pageTitle) in pagesPerCategory[key]:
        f.write(f'<li><a href="{filename}">{pageTitle}</a></li>\n'.encode('utf8'))
      f.write('</ul>\n</details>'.encode('utf8'))

    f.write(f'<details>\n<summary>All pages</summary>\n<ul>\n'.encode('utf8'))
    f.write('<ul>\n'.encode('utf8'))
    for (filename, pageTitle) in downloadedPages:
      f.write(f'<li><a href="{filename}">{pageTitle}</a></li>\n'.encode('utf8'))
    f.write('</ul>\n'.encode('utf8'))
    f.write('</ul>\n</details>'.encode('utf8'))

    f.write(footer.encode("utf8"))
    f.close()

###############
# Create category pages
###############
for key in sorted(pagesPerCategory.keys()):
  print(f'Creating category page for: {key}')
  pageName = PageTitleToFilename(f'Kategorie:{key}') + '.html'
  with open(export_path + pageName, "wb") as f:
    f.write(header.replace('#TITLE#', key).encode("utf8"))

    content, *_ = getPageContent(f'Kategorie:{key}')
    if content is None:
      content = '<p>No content on this page</p>'
    content = cleanupContent(content)

    if enableIndex:
      f.write('<a href="./index.html">Back to index</a>\n'.encode("utf8"))
    f.write(content.encode('utf8'))

    f.write('<ul>\n'.encode('utf8'))
    for (filename, pageTitle) in pagesPerCategory[key]:
      f.write(f'<li><a href="{filename}">{pageTitle}</a></li>\n'.encode('utf8'))
    f.write('</ul>'.encode('utf8'))

    f.write(footer.encode("utf8"))
    f.close()

copy(file_path + 'templates/page-not-found.html', export_path + 'article_not_existing.html')
if not Path(export_path + 'css/').exists():
  copytree(file_path + 'templates/css/', export_path + 'css/')

