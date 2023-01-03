#!/usr/bin/env python3
# -*- coding: utf-8 -*-
''' Post images from Tumblr to Mastadon.

Compatible with AWS Lambda and assumes an image-only Tumblr feed.
'''
from __future__ import print_function
import os, sys, re, urllib.parse, pprint, itertools, json, time
import feedparser, uritemplate, requests, bs4

# External configuration from environment variables.
# Good information about the Mastodon OAuth dance is here:
# https://tinysubversions.com/notes/mastodon-bot/index.html
tumblr_url = os.environ['TUMBLR_URL']           # e.g. http://migurski.tumblr.com/rss
mastodon_url = os.environ['MASTODON_BASE']      # e.g. https://mastodon.social
mastodon_token = os.environ['MASTODON_TOKEN']   # alpha-numeric string

class Post:
    ''' Tumblr RSS Item with a link, image URL, and text.
    '''
    def __init__(self, link, image_url, text):
        self.link = link
        self.image_url = image_url
        self.text = text
    def __str__(self):
        return '<Post {}>'.format(self.link)

class Toot:
    ''' Mastodon status with a URL and links from inside the text.
    
        https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#status
    '''
    def __init__(self, url, links):
        self.url = url
        self.links = links
    def __str__(self):
        return '<Toot {} ({})>'.format(self.url, len(self.links))
    def __contains__(self, post):
        ''' Return true if the Post is linked within this Toot.
        
            Allow for optional Tumblr trailing slugs.
        '''
        for toot_link in self.links:
            joined = urllib.parse.urljoin(post.link, toot_link)
            if joined.startswith(post.link):
                return True
        return False

# Current user:
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#getting-the-current-user
mastodon_whoami_url = urllib.parse.urljoin(mastodon_url, '/api/v1/accounts/verify_credentials')

# Account statuses:
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#getting-an-accounts-statuses
mastodon_statuses_url = urllib.parse.urljoin(mastodon_url, '/api/v1/accounts/{id}/statuses')

# Uploading a media attachment:
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#media
mastodon_media_url = urllib.parse.urljoin(mastodon_url, '/api/v2/media')

# Posting a new status:
# https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md#posting-a-new-status
mastodon_status_url = urllib.parse.urljoin(mastodon_url, '/api/v1/statuses')

# OAuth header
mastodon_header = {'Authorization': 'Bearer {}'.format(mastodon_token)}

def load_posts(tumblr_url):
    ''' Load recent posts from a Tumblr RSS URL and return list of Post objects.
    
        These are assumed to be in reverse-chronological order.
    '''
    tumblr_rss_url = urllib.parse.urljoin(tumblr_url, '/rss')
    
    tumblr_posts = list()
    got = requests.get(tumblr_rss_url)
    feed = feedparser.parse(got.content)
    
    for entry in feed.entries:
        soup = bs4.BeautifulSoup(getattr(entry, 'summary', ''), 'html.parser')
        link = entry.link
        try:
            image_url = soup.find('img')['src']
        except TypeError:
            print('No img in', link)
            continue
        text = soup.get_text()
        text = ' '.join(soup.find_all(text=re.compile('.*')))
        tumblr_posts.append(Post(link, image_url, text))
        print(tumblr_posts[-1], file=sys.stderr)
    
    return tumblr_posts

def load_toots(mastodon_whoami_url, mastodon_statuses_url, mastodon_header, max_count=50):
    ''' Load recent toots from a Mastodon instance and return list of Toot objects.
    
        These are assumed to be in reverse-chronological order.
    '''
    got1 = requests.get(mastodon_whoami_url, headers=mastodon_header)
    mastodon_id = got1.json().get('id')

    mastodon_toots = list()
    url = uritemplate.expand(mastodon_statuses_url, dict(id=mastodon_id))
    
    while len(mastodon_toots) < max_count:
        print('Get', url, '...', file=sys.stderr)
        got2 = requests.get(url, headers=mastodon_header)

        for status in got2.json():
            url = status['url']
            soup = bs4.BeautifulSoup(status['content'], 'html.parser')
            links = [a['href'] for a in soup.find_all('a')]
            mastodon_toots.append(Toot(url, links))
            print(mastodon_toots[-1], file=sys.stderr)
        
        if 'next' in got2.links:
            url = got2.links['next']['url']
        else:
            break
    
    return mastodon_toots

def toot_post(post, mastodon_media_url, mastodon_status_url, mastodon_header):
    ''' Toot a single Post to Mastodon with a media attachment.
    '''
    suffix = u'\n\n{}'.format(post.link)
    text = u'{}{}'.format(post.text.strip(), suffix).strip()
    if len(text) > 500:
        cutoff = 499 - len(suffix)
        text = u'{}…{}'.format(post.text.strip()[:cutoff], suffix).strip()
    image = requests.get(post.image_url)
    pprint.pprint(dict(text=text, image=post.image_url), stream=sys.stderr)
    
    # Create a new media attachment with the post image
    file = os.path.basename(post.image_url), image.content, image.headers['Content-Type']
    posted1 = requests.post(mastodon_media_url, files=dict(file=file), headers=mastodon_header)

    media_id, media_url = posted1.json().get('id'), posted1.json().get('url')
    print('Media', media_id, '-', media_url, file=sys.stderr)
    
    # *shrug*
    if posted1.status_code != 200:
        raise RuntimeError()
    
    # Create a new status with the attachment
    body = json.dumps(dict(media_ids=[media_id], status=text))
    headers = {'Content-Type': 'application/json'}
    headers.update(mastodon_header)
    posted2 = requests.post(mastodon_status_url, data=body, headers=headers)

    status_id, status_url = posted2.json().get('id'), posted2.json().get('url')
    print('Status', status_id, '-', status_url, file=sys.stderr)

def main():
    ''' Toot the first untooted Post from Tumblr to Mastadon.
    '''
    tumblr_posts = load_posts(tumblr_url)
    mastodon_toots = load_toots(mastodon_whoami_url, mastodon_statuses_url, mastodon_header)
    untooted_posts = []
    
    if not tumblr_posts or not mastodon_toots:
        raise RuntimeError('Suspiciously, tumblr_posts or mastodon_toots are missing')

    for (post, toot) in itertools.product(tumblr_posts, mastodon_toots):
        if post in toot:
            print(post, '=', toot, file=sys.stderr)
            untooted_posts = tumblr_posts[:tumblr_posts.index(post)]
            break
    
    if len(untooted_posts) == 0:
        print('No untooted post', file=sys.stderr)
        return

    if len(untooted_posts) == len(tumblr_posts):
        raise RuntimeError('Suspiciously, all posts are untooted')

    print('Untooted:', file=sys.stderr)
    for post in untooted_posts:
        print('-', post.link, post.text, file=sys.stderr)
    
    post = untooted_posts.pop()
    print('Tooting', post, '...', file=sys.stderr)
    toot_post(post, mastodon_media_url, mastodon_status_url, mastodon_header)

def lambda_handler(event, context):
    return main()

if __name__ == '__main__':
    exit(main())
