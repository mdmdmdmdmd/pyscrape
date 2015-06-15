class Movie(object):
    def __init__(self):
        self.imdbid = None
        self.basefiles = []
        self.mediafiles = None
        self.israr = False
        self.rarbasename = None
        self.title = None
        self.year = None
        self.plot = ''
        self.outline = ''
        self.tagline = ''
        self.rating = ''
        self.votes = ''
        self.writers = []
        self.images = dict()
        self.runtime = ''
        self.cert = ''
        self.top250 = ''
        self.genres = []
        self.directors = []
        self.originaltitle = ''
        self.studios = []
        self.trailer = ''
        self.countries = []
        self.actors = []
        self.set = ''
        # TODO: put the following into kodi.py:
        # self.fileid = ''
        # self.pathid = ''
        # self.setid = ''
