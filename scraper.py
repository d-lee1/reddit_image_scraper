import requests
import time
from urllib.parse import urlparse, urlsplit
from urllib.request import urlretrieve
import praw
import os
import sys
import platform
from pathlib import Path
import configparser
import re
import unicodedata
import colorama
from colorama import Fore, Style


# credit to this post
# https://stackoverflow.com/a/34325723
# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 50, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

class Crawler:
    submission_limit = 1000
    def __init__(self, config):
        if not config:
            print('config is empty')
            return
        self.config = config
        self.reddit = praw.Reddit('scraper', user_agent='wallpaper downloader')
        self.data = []

    def has_resolution(self, resolutions, string):
        for res in resolutions:
            if res[0] in string and res[1] in string:
                return True
        return False

    def get_images(self):
        if not 'subreddit' in self.config:
            print('missing subreddit key in config.')
            return
        subreddit = self.reddit.subreddit(self.config['subreddit'])  
        thread_type = self.config['thread_type'] if 'thread_type' in self.config else 'hot'
        amount = self.config['amount'] if self.config['amount'] else 25
        any_resolution = self.config['any_resolution'] if 'any_resolution' in self.config else False
        resolutions = self.config['resolutions'] if 'resolutions' in self.config else []
        score_threshold = self.config['score_threshold'] if 'score_threshold' in self.config else 2
        min_upvote_ratio = self.config['upvote_ratio'] if 'upvote_ratio' in self.config else 0.51
        if thread_type == 'hot':
            submissions = subreddit.hot(limit=self.submission_limit)
        elif thread_type == 'top':
            submissions = subreddit.top(limit=self.submission_limit)
        elif thread_type == 'controversial':
            submissions = subreddit.controversial(limit=self.submission_limit)
        elif thread_type == 'new':
            submissions = subreddit.new(limit=self.submission_limit)
        elif thread_type == 'rising':
            submissions = subreddit.rising(limit=self.submission_limit)
        else:
            print("{thread_type} is not a valid thread type on Reddit".format(thread_type=thread_type))
            return
        index = count = 0
        
        for submission in submissions:
            if count == amount:
                break
            title = submission.title
            score = submission.score
            upvote_ratio = submission.upvote_ratio
            url = submission.url
            created_utc = submission.created_utc
            if score >= score_threshold and upvote_ratio >= min_upvote_ratio and (any_resolution or self.has_resolution(resolutions, title)):
                req = requests.head(url)
                if 'Content-Type' not in req.headers or 'image' not in req.headers['Content-Type']:
                    continue
                content_type = req.headers['Content-Type']
                self.data.append({ 'title': title, 'url': url, 'score': score, 'upvote_ratio': upvote_ratio, 'content_type':  content_type })
                count += 1
            printProgressBar(count, amount, prefix='{subreddit} progress:'.format(subreddit=self.config['subreddit']), suffix='complete')
        if count != amount:
            print('\n')
            print(Fore.RED + 'Unable to retrieve all {amount} images for {subreddit}'.format(amount=amount, subreddit=self.config['subreddit']))

class Aggregator:
    # TODO
    def __init__(self):
        self.data = []
        self.to_download = []
        self.config_parser = configparser.ConfigParser(empty_lines_in_values=True, strict=False)
        self.config_parser.read('scraper.ini')
        if len(self.config_parser) == 0:
            print('failed to open or find scraper.ini')
            return
        self.configs = self.configure()
    
    def parse_resolution(self, resolutions):
        ret = []
        for res in resolutions:
            x,y = res.split('x')
            ret.append((x,y))
        return ret

    def configure(self):
        try:
            sections = self.config_parser.sections()
            for section in sections:
                entry = {}
                entry['subreddit'] = section
                for key in self.config_parser[section]:
                    if key == 'amount':
                        entry[key] = int(self.config_parser[section][key])
                    if key == 'upvote_ratio':
                        entry[key] = float(self.config_parser[section][key])
                    if key == 'upvote_threshold':
                        entry[key] = int(self.config_parser[section][key])
                    if key == 'resolutions':
                        entry[key] = self.config_parser[section][key].split()
                    if key == 'thread_type':
                        entry[key] = self.config_parser[section][key]
                    if key == 'any_resolution':
                        entry[key] = self.config_parser[section].getboolean(key)
                    if key == 'destination':
                        entry[key] = Path(self.config_parser[section][key])
                        if not entry[key].is_dir():
                            print('{path} is not a valid path'.format(path=r'{}'.format(self.config_parser[section][key])))
                            return
                        entry[key].mkdir(parents=True, exist_ok=True)
                self.data.append(entry)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise
    
    def slugify(self, value, allow_unicode=False):
        """
        Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
        Remove characters that aren't alphanumerics, underscores, or hyphens.
        Convert to lowercase. Also strip leading and trailing whitespace.
        """
        value = str(value)
        if allow_unicode:
            value = unicodedata.normalize('NFKC', value)
        else:
            value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower()).strip()
        return re.sub(r'[-\s]+', '-', value)

    def download_images(self):
        print("Getting images...")
        for config in self.data:
            c = Crawler(config)
            c.get_images()
            self.to_download.append((config['destination'], c.data))
        print("Downloading images...")
        i = total = 0
        total = sum(len(x) for _, x in self.to_download)
        error_log = ''
        for dest, items in self.to_download:
            for info in items:
                file_ext = info['content_type'].split('/')[-1]
                clean_title = self.slugify(info['title'])
                download_path = dest / (clean_title + '.' + file_ext)
                try:
                    urlretrieve(info['url'], download_path)
                except Exception as e:
                    if  hasattr(e, 'message'):
                        error_log += e.message + '\n'
                finally:
                    i += 1
                    printProgressBar(i, total, prefix='Downloading images progress:', suffix='complete')
        if error_log:
            print('\n')
            print(Fore.RED + 'Error(s) has occurred while downloading images.')
            print(Fore.RED + error_log)
a = Aggregator()
a.download_images()
