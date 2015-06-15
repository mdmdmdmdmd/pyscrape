import os
import glob
import re

import requests
import tmdbsimple
import bs4

import kodi
import containers
import utils


class Scrape(object):
    def __init__(self, rootpath, logger, scrapetype, addguesses=False):  # , mode='kodi'):
        self._rootpath = rootpath
        self._logger = logger
        self._type = scrapetype  # 'movie', 'tv', ??? -- what type of media is to be expected in the root path
        # self._mode = mode  # 'kodi', ??? -- which system we scrape for, so far only kodi implemented
        self._addguesses = addguesses
        self._tmdbapikey = ''  # TODO: make this an option perhaps?
        self._tmdbconfig = None
        self._module = None

    @staticmethod
    def _mediafiles(path, movie):
        mediatypes = ['mkv', 'avi', 'ogm']
        movie.mediafiles = glob.glob(path + '/*.rar')
        if len(movie.mediafiles) < 1:  # no rar files found, checking for mkv/avi/ogm
            for mediatype in mediatypes:
                mediafiles = glob.glob(path + '/*.' + mediatype)
                if len(mediafiles) < 1:
                    continue
                for basefile in mediafiles:
                    movie.mediafiles.append(basefile)
                    movie.basefiles.append(os.path.split(basefile))
            if len(movie.mediafiles) < 1:
                return False
        else:
            movie.mediafiles.sort()
            rarname = os.path.split(movie.mediafiles[0])
            movie.rarbasename = rarname[1]
            rarname = path + '/' + rarname[1]
            filelist = []
            if not utils.getrarlist(rarname, filelist, mediatypes):
                return False
            if filelist:
                movie.israr = True
                movie.mediafiles = []
                for filename in filelist:
                    movie.mediafiles.append(rarname + '/' + filename)
                    movie.basefiles.append(filename)
            else:
                return False
        return True

    @staticmethod
    def _getnfoimdbid(path):
        nfofiles = glob.glob(path + '/*.nfo')
        amountfiles = len(nfofiles)
        if amountfiles != 1:
            return None
        # nfofile = os.path.split(nfofiles[0])[1]
        idpattern = re.compile('imdb....?/title/(tt[0-9]*)', re.IGNORECASE)
        with open(nfofiles[0], 'r', encoding='cp1252', errors='ignore') as nfocontent:
            for nfoline in nfocontent:
                match = re.findall(idpattern, nfoline)
                if match:
                    return match[0]
        return None

    @staticmethod
    def _getpathmeta(path, movie):
        taglist = ['proper', 'readnfo', 'proof', 'limited', '1080p', '720p', 'dvd5', 'dvd9', 'german', 'french',
                   'multi', 'hdtv', 'ac3', 'dts', 'extended', 'directors', 'dts-hd', '3d', 'dvdrip', 'remastered',
                   'internal', 'swedish', 'dubbed', 'subbed', 'theatrical', 'real', 'unrated', 'multisubs', 'retail',
                   'dc', 'repack', 'rerip', 'uncut', 'dutch', 'restored', 'alternate', 'ws', 'int', 'reconstructed',
                   'dsr', 'pdtv' 'dvdrip']
        tags = path.split('.')
        for(count, tag) in enumerate(tags):
            if tag.lower() in taglist:
                del tags[count:]
                if tags[-1].isnumeric() and len(tags[-1]) == 4:
                    movie.year = tags[-1]
                    del tags[-1]
                movie.title = ' '.join(tags).lower()
                return True
        return False

    @staticmethod
    def _comparenfopath(movie, tmdbmovie):
        try:
            tmdbinfo = tmdbmovie.info(language='en')
        except requests.exceptions.HTTPError:
            return False
        conv = utils.unicodetoascii(tmdbinfo['title'].lower())
        titles = [tmdbinfo['title'].lower(), conv['int'], conv['ger']]
        if movie.title.lower() in titles:
            if movie.year is not None:
                if int(tmdbinfo['release_date'][0:4]) != int(movie.year):
                    movie.year = tmdbinfo['release_date'][0:4]  # prefer the year from TMDB if title matches perfectly
            else:
                movie.year = tmdbinfo['release_date'][0:4]  # no year in path, so take year from TMDB
            movie.title = tmdbinfo['title']
            return True
        else:
            return False

    @staticmethod
    def _guessmovie(movie):
        search = tmdbsimple.Search().movie(query=movie.title, page=1, language='en')
        if search is not None:
            if len(search['results']) > 0:
                movie.title = search['results'][0]['title']
                movie.year = search['results'][0]['release_date'][:4]
                movie.imdbid = search['results'][0]['id']
                return True
        return False

    @staticmethod
    def _gettmdbimages(posterurls, tmdbconfig, tmdbmovie, person=False, personid=None):
        try:
            if person:
                tmdbperson = tmdbsimple.People(personid)
                posterlist = tmdbperson.images(language='en')
            else:  # poster / fanart
                posterlist = tmdbmovie.images(language='en')
        except requests.exceptions.HTTPError:
            return False
        if person:
            for poster in posterlist['profiles']:
                posterurls.append(tmdbconfig['images']['base_url'] + 'original' + poster['file_path'])
            if len(posterurls) > 0:
                return True
            else:
                return False
        parameter = {'fanart': {'arttype': 'backdrops', 'arttypesize': 'backdrop_sizes', 'artsize': 'w780'},
                     'poster': {'arttype': 'posters', 'arttypesize': 'poster_sizes', 'artsize': 'w500'}}
        modes = ('fanart', 'poster')
        for mode in modes:
            listlen = len(tmdbconfig['images'][parameter[mode]['arttypesize']])
            previewsize = None
            for (count, size) in enumerate(tmdbconfig['images'][parameter[mode]['arttypesize']]):
                if size == parameter[mode]['artsize']:
                    previewsize = count
                    break
            if previewsize is None:
                previewsize = listlen - 2
            urls = [[], []]
            for (count, size) in enumerate([tmdbconfig['images'][parameter[mode]['arttypesize']][listlen - 1],
                                            tmdbconfig['images'][parameter[mode]['arttypesize']][previewsize]]):
                for poster in posterlist[parameter[mode]['arttype']]:
                    urls[count].append(tmdbconfig['images']['base_url'] + size + poster['file_path'])
            posterurls[mode] = urls
        return True

    def _gettmdbmeta(self, movie, guessed, tmdbmovie=None):
        if tmdbmovie is None:  # got no tmdbmovie, need to recreate it
            try:
                tmdbmovie = tmdbsimple.Movies(movie.imdbid)
            except requests.exceptions.HTTPError:
                return False
        try:
            tmdbinfo = tmdbmovie.info(language='en')
            tmdbcert = tmdbmovie.releases(language='en')
            tmdbcredits = tmdbmovie.credits(language='en')
            tmdbvideos = tmdbmovie.videos(language='en')
        except requests.exceptions.HTTPError:
            return False
        if guessed:  # overwrote movie.imdbid with TMDB id, now have to correct it to the actual IMDB id
            movie.imdbid = tmdbinfo['imdb_id']
        self._gettmdbimages(movie.images, self._tmdbconfig, tmdbmovie)
        movie.tagline = tmdbinfo['tagline']
        movie.runtime = str(int(tmdbinfo['runtime']) * 60)
        movie.originaltitle = tmdbinfo['original_title']
        for studio in tmdbinfo['production_companies']:
            movie.studios.append(studio['name'])
        for country in tmdbinfo['production_countries']:
            movie.countries.append(country['name'])
        for genre in tmdbinfo['genres']:
            movie.genres.append(genre['name'])
        if tmdbinfo['belongs_to_collection'] is not None:
            movie.set = tmdbinfo['belongs_to_collection']['name']
        for country in tmdbcert['countries']:
            if country['iso_3166_1'] == 'US':
                movie.cert = 'Rated: ' + country['certification']
                break
        for crew in tmdbcredits['crew']:
            if crew['department'] == 'Writing':
                imageurls = []
                if not self._gettmdbimages(imageurls, self._tmdbconfig, None, True, crew['id']):
                    movie.writers.append(['', crew['name']])
                else:
                    movie.writers.append([imageurls[0], crew['name']])
            if crew['department'] == 'Directing':
                imageurls = []
                if not self._gettmdbimages(imageurls, self._tmdbconfig, None, True, crew['id']):
                    movie.directors.append(['', crew['name']])
                else:
                    movie.directors.append([imageurls[0], crew['name']])
        for cast in tmdbcredits['cast']:
            imageurls = []
            if not self._gettmdbimages(imageurls, self._tmdbconfig, None, True, cast['id']):
                movie.actors.append(['', cast['character'], cast['name']])
            else:
                movie.actors.append([imageurls[0], cast['character'], cast['name']])
        if len(tmdbvideos['results']) > 0:
            for result in tmdbvideos['results']:
                if result['site'] == 'YouTube' and result['type'] == 'Trailer':
                    movie.trailer = result['key']
                    # add 'plugin://plugin.video.youtube/?action=play_video&videoid=' +  to kodi.py
                    break
        return True

    @staticmethod
    def _getimdbmeta(movie):
        imdbmain = utils.geturl('http://akas.imdb.com/title/' + movie.imdbid)
        if not imdbmain:
            return False
        soup = bs4.BeautifulSoup(imdbmain)
        movie.plot = soup.find('div', itemprop='description').p.contents[0].strip()
        movie.outline = soup.find('p', itemprop='description').string.strip()
        movie.rating = soup.find('span', itemprop='ratingValue').string.strip()
        movie.votes = soup.find('span', itemprop='ratingCount').string.strip()
        # for entry in soup.find_all('div', class_='txt-block'):
        #     if entry.find(text='Taglines:') is not None:
        #         movie.tagline = list(entry.stripped_strings)[1]
        #     if entry.find(text='Runtime:') is not None:
        #         movie.runtime = str(int(entry.find('time')['datetime'][2:-1]) * 60)
        #         break
        match = soup.find_all('a', href=re.compile('\/chart\/top\?tt'))
        if match:
            movie.top250 = match[0].find('strong').string.split('#')[1]
        # restudio = '"/company/[^>]+>[^<]*<[^>]*>([^<]+)</span>'
        # ismatch = getregex(str(imdbmain, encoding='utf-8'), restudio)
        # if ismatch:
        #     moviestudio = ismatch
        # recountries = '"/country/[^>]+>([^<]+)</a>'
        # ismatch = getregex(str(imdbmain, encoding='utf-8'), recountries, re.IGNORECASE, True)
        # if ismatch:
        #     for country in ismatch:
        #         moviecountries.append(country)
        return True

    def _moviedirs(self, pathlist):
        for path in pathlist:
            self._logger.info('scrape: scraping: ' + path)
            movie = containers.Movie()
            if path[0] == '.':  # skip hidden dirs
                self._logger.warning('scrape: skipping hidden dir: ' + path)
                continue
            fullpath = self._module.fullpath(path)
            pathid = self._module.checksubdir(fullpath)
            if not pathid:
                self._logger.warning('scrape: skipping because of missing pathid: ' + path)
                continue
            if not self._mediafiles(self._rootpath + path, movie):
                self._logger.warning('scrape: skipping because no media files could be found: ' + path)
                continue
            if self._module.checkmovie(path, movie.basefiles, movie.israr, movie.rarbasename):
                self._logger.warning('scrape: skipping because movie exists already in db: ' + path)
                continue #  movie exists already in db
            movie.imdbid = self._getnfoimdbid(self._rootpath + path)
            if movie.imdbid is None and not self._addguesses:
                self._logger.warning('scrape: skipping because of missing IMDB id and not allowed to guess: ' + path)
                continue
            if not self._getpathmeta(path, movie):
                self._logger.warning('scrape: skipping because of invalid path name: ' + path)
                continue
            guessed = False
            if movie.imdbid is not None:
                # got IMDB id from _getnfoimdbid(), check if it matches title from path:
                try:
                    tmdbmovie = tmdbsimple.Movies(movie.imdbid)
                except requests.exceptions.HTTPError:
                    self._logger.warning('scrape: skipping because connection to TMBD failed: ' + path)
                    continue
                if not self._comparenfopath(movie, tmdbmovie):
                    # movie title from path didnt match with what we got from TMDB so we try to guesstimate IMDB id:
                    if self._addguesses:
                        if not self._guessmovie(movie):
                            self._logger.warning('scrape: skipping because movie name could not be guessed[1]: ' + path)
                            continue
                        else:
                            guessed = True
                    else:
                        self._logger.warning('scrape: skipping because path and nfo dont match and not allowed to '
                                             'guess: ' + path)
                        continue
            elif self._addguesses:
                # no IMDB id from _getnfoimdbid() so we try to guesstimate IMDB id:
                if not self._guessmovie(movie):
                    self._logger.warning('scrape: skipping because movie name could not be guessed[2]: ' + path)
                    continue
                else:
                    guessed = True
            else:
                # not allowed to guess, give up:
                self._logger.warning('scrape: skipping because IMDB id could not be determinded and not allowed to '
                                     'guess: ' + path)
                continue
            if guessed:
                if not self._gettmdbmeta(movie, guessed):
                    self._logger.warning('scrape: skipping because TMDB meta data could not be retrieved[1]: ' + path)
                    continue
            else:
                if not self._gettmdbmeta(movie, guessed, tmdbmovie):
                    self._logger.warning('scrape: skipping because TMDB meta data could not be retrieved[2]: ' + path)
                    continue
            if not self._getimdbmeta(movie):
                self._logger.warning('scrape: skipping because IMDB meta data could not be retrieved: ' + path)
                continue
            if not self._module.addmovie(movie, path):
                self._logger.warning('scrape: skipping because movie could not be added to the db: ' + path)

    def _tvdirs(self, pathlist):
        pass

    def preparekodi(self, substpath, host, port, user, passwd):  # set kodi specific stuff, do this first before .run()
        database = kodi.Database(host, port, user, passwd)
        self._module = kodi.Kodi(database, substpath, self._logger)

    def run(self):
        if self._module is None:
            self._logger.error('scrape: no module for scraping prepared.')
            return False
        if not self._module.init(self._type):
            self._logger.error('scrape: initialization of {0} module failed.'.format(self._module.name))
            return False
        try:
            walklist = os.walk(self._rootpath)
        except os.error:
            self._logger.error('scrape: can not read root path.')
            return False
        else:
            pathlist = None
            for root, dirs, files in walklist:
                pathlist = dirs
                break
            # return False
            tmdbsimple.API_KEY = self._tmdbapikey
            try:
                self._tmdbconfig = tmdbsimple.Configuration().info()
            except requests.exceptions.HTTPError:
                self._logger.error('scrape: could not get TMDB config.')
                return False
            if self._type == 'movie':
                self._moviedirs(pathlist)
            elif self._type == 'tv':  # TODO: implement tv show scraping
                pass
            return True

    def resume(self):
        pass  # TODO: add resume mode (possibly using a sqlite db for state?)
