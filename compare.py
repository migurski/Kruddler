#!/usr/bin/env python2.7
from __future__ import print_function
import os, sys, re, urlparse, pprint, xml.etree.ElementTree, itertools
import feedparser, uritemplate, requests, bs4

class Post:
    ''' RSS Item.
    '''
    def __init__(self, link, image_url, text):
        self.link = link
        self.image_url = image_url
        self.text = text
    def __str__(self):
        return '<Post {}>'.format(self.link)

class Toot:
    ''' Mastodon status.
    
        https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#status
    '''
    def __init__(self, url, links):
        self.url = url
        self.links = links
    def __str__(self):
        return '<Toot {} ({})>'.format(self.url, len(self.links))
    def __contains__(self, post):
        for toot_link in self.links:
            joined = urlparse.urljoin(post.link, toot_link)
            if joined.startswith(post.link):
                return True
        return False

tumblr_url = os.environ['TUMBLR_URL']
mastodon_url = os.environ['MASTODON_BASE']
mastodon_token = os.environ['MASTODON_TOKEN']

# Current user
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#getting-the-current-user
mastodon_whoami_url = urlparse.urljoin(mastodon_url, '/api/v1/accounts/verify_credentials')

# Account statuses
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#getting-an-accounts-statuses
mastodon_statuses_url = urlparse.urljoin(mastodon_url, '/api/v1/accounts/{id}/statuses')

# OAuth header
mastodon_header = {'Authorization': 'Bearer {}'.format(mastodon_token)}

got3 = requests.get(tumblr_url)
tree3 = xml.etree.ElementTree.fromstring(got3.content)
tumblr_posts = list()

for child in tree3.find('channel').findall('item'):
    soup = bs4.BeautifulSoup(child.find('description').text, 'html.parser')
    link = child.find('link').text
    image_url = soup.find('img')['src']
    text = soup.get_text()
    text = ' '.join(soup.find_all(text=re.compile('.*')))
    tumblr_posts.append(Post(link, image_url, text))
    print(tumblr_posts[-1], file=sys.stderr)

got1 = requests.get(mastodon_whoami_url, headers=mastodon_header)
mastodon_id = got1.json().get('id')

url2 = uritemplate.expand(mastodon_statuses_url, dict(id=mastodon_id))
got2 = requests.get(url2, headers=mastodon_header)

mastodon_toots = list()

for status in got2.json():
    url = status['url']
    soup = bs4.BeautifulSoup(status['content'], 'html.parser')
    links = [a['href'] for a in soup.find_all('a')]
    mastodon_toots.append(Toot(url, links))
    print(mastodon_toots[-1])

for (post, toot) in itertools.product(tumblr_posts, mastodon_toots):
    if post in toot:
        print(post, toot)
        print(tumblr_posts.index(post))
        print(mastodon_toots.index(toot))
        untooted_posts = tumblr_posts[:tumblr_posts.index(post)]
        break

for post in untooted_posts:
    print(post.link, post.text)