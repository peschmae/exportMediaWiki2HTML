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
args = parser.parse_args()

file_path = os.path.abspath(os.path.dirname(__file__)) + '/'

# load templates
header = Path(file_path + 'templates/header.html').read_text()
footer = Path(file_path + 'templates/footer.html').read_text()

if args.exportPath:
  export_path = args.exportPath
else:
  export_path = file_path + 'export'

Path(export_path + "/img").mkdir(parents=True, exist_ok=True)

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

url = args.url
if not url.endswith('/'):
  url = url + '/'

pageOnly = -1
categoryOnly = -1
if args.category is not None:
  categoryOnly = int(args.category)
if args.page is not None:
  pageOnly = int(args.page)

def quote_title(title):
  return parse.quote(page['title'].replace(' ', '_'))

downloadedimages = []
def DownloadImage(filename, urlimg):
  if not filename in downloadedimages:
    if '/thumb/' in urlimg:
      urlimg = urlimg.replace('/thumb/', '/')
      urlimg = urlimg[:urlimg.rindex('/')]
    response = S.get(url + urlimg)
    content = response.content
    f = open(export_path + "/img/" + filename, "wb")
    f.write(content)
    f.close()
    downloadedimages.append(filename)

downloadedPages = []
def PageTitleToFilename(title):
    temp = re.sub('[^A-Za-z0-9\u0400-\u0500]+', '_', title)
    return temp.replace("(","_").replace(")","_").replace("__", "_")

S = requests.Session()

if args.username is not None and args.password is not None:
  LgUser = args.username
  LgPassword = args.password

  # Retrieve login token first
  PARAMS_0 = {
      'action':"query",
      'meta':"tokens",
      'type':"login",
      'format':"json"
  }
  R = S.get(url=url + "/api.php", params=PARAMS_0)
  DATA = R.json()
  LOGIN_TOKEN = DATA['query']['tokens']['logintoken']

  # Main-account login via "action=login" is deprecated and may stop working without warning. To continue login with "action=login", see [[Special:BotPasswords]]
  PARAMS_1 = {
      'action':"login",
      'lgname':LgUser,
      'lgpassword':LgPassword,
      'lgtoken':LOGIN_TOKEN,
      'format':"json"
  }

  R = S.post(url + "/api.php", data=PARAMS_1)
  DATA = R.json()
  if "error" in DATA:
    print(DATA)
    exit(-1)

if categoryOnly != -1:
  url_allpages = url + "/api.php?action=query&list=categorymembers&format=json&cmpageid=" + str(categoryOnly) + "&cmlimit=" + numberOfPages
else:
  url_allpages = url + "/api.php?action=query&list=allpages&format=json&aplimit=" + numberOfPages
response = S.get(url_allpages)
data = response.json()
if "error" in data:
  print(data)
  if data['error']['code'] == "readapidenied":
    print()
    print("get login token here: " + url + "/api.php?action=query&meta=tokens&type=login")
    print("and then call this script with parameters: myuser topsecret mytoken")
    exit(-1)
if categoryOnly != -1:
  pages = data['query']['categorymembers']
else:
  pages = data['query']['allpages']

for page in pages:
    if (pageOnly > -1) and (page['pageid'] != pageOnly):
        continue
    print(page)
    quoted_pagename = quote_title(page['title'])
    url_page = url + "api.php?page=" + quoted_pagename + "&action=parse&prop=text&formatversion=2&format=json"
    response = S.get(url_page)

    if not 'parse' in response.json():
      print("Error while fetching from api")
      print(response.json())
      continue

    if 'text' in response.json()['parse']:
      content = response.json()['parse']['text']
    else:
      content = "<p>No content on this page</p>"

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
      content = content.replace('href="/', 'href="' + url + 'index.php?title=')

    while url + "index.php?title=" in content:
        pos = content.find(url + "index.php?title=")
        posendquote = content.find('"', pos)
        linkedpage = content[pos:posendquote]
        linkedpage = linkedpage[linkedpage.find('=') + 1:]
        downloadName = linkedpage.replace('%27', '_')

        if linkedpage.startswith(fileIndicator) or linkedpage.startswith(imageIndicator):
          if linkedpage.startswith(fileIndicator):
              linkType = fileIndicator
          if linkedpage.startswith(imageIndicator):
              linkType = imageIndicator
          origlinkedpage = linkedpage[linkedpage.find(':')+1:]
          linkedpage = parse.unquote(origlinkedpage)
          imgpos = content.find('src="/images/', posendquote)

          if imgpos > posendquote:
            imgendquote = content.find('"', imgpos+len(linkType))
            imgpath = content[imgpos+len(linkType) - 1:imgendquote]

          if not downloadName in downloadedimages:
            DownloadImage(downloadName, imgpath)

          if downloadName in downloadedimages:
            content = content.replace(url+"index.php?title="+linkType+origlinkedpage, "img/"+downloadName)
            content = content.replace(imgpath, "img/"+downloadName)
          else:
            print("Error: not an image? " + linkedpage)
            exit(-1)

        elif "&amp;action=edit&amp;redlink=1" in linkedpage:
          content = content[:pos] + "article_not_existing.html\" style='color:red'" + content[posendquote+1:]
        elif "#" in linkedpage:
          linkWithoutAnchor = linkedpage[0:linkedpage.find('#')]
          linkWithoutAnchor = PageTitleToFilename(linkWithoutAnchor)
          content = content[:pos] + linkWithoutAnchor + ".html#" + linkedpage[linkedpage.find('#')+1:] + content[posendquote:]
        else:
          linkedpage = PageTitleToFilename(linkedpage)
          content = content[:pos] + linkedpage + ".html" + content[posendquote:]

    #content = content.replace('<div class="mw-parser-output">'.encode("utf8"), ''.encode("utf8"))
    content = re.sub("(<!--).*?(-->)", '', content, flags=re.DOTALL)

    pageFilename = PageTitleToFilename(page['title']) + '.html'
    with open(export_path + pageFilename, "wb") as f:
      f.write(header.replace('#TITLE#', page['title']).encode("utf8"))
      f.write(content.encode('utf8'))
      f.write(footer.encode("utf8"))
      f.close()

    downloadedPages.append((pageFilename, page['title']))

if enableIndex:
  # Write index file for easier overview
  with open(export_path + "index.html", "wb") as f:
    f.write(header.replace('#TITLE#', 'Index').encode("utf8"))

    f.write('<ul>\n'.encode('utf8'))

    for (filename, pageTitle) in downloadedPages:
      f.write(f'<li><a href="{filename}">{pageTitle}</a></li>\n'.encode('utf8'))

    f.write('</ul>\n'.encode('utf8'))
    f.write(footer.encode("utf8"))
    f.close()

copy(file_path + 'templates/page-not-found.html', export_path + 'article_not_existing.html')
if not Path(export_path + 'css/').exists():
  copytree(file_path + 'templates/css/', export_path + 'css/')

