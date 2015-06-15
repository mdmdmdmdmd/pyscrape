import oursql
from urllib import parse


class Database(object):
    def __init__(self, host, port, user, passwd):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd


class Kodi(object):
    def __init__(self, database, substpath, logger):
        self.name = 'kodi'
        self._database = database
        self._logger = logger
        self._cur = None
        self._rootpathid = None
        self._substpath = substpath

    def _sqlprepare(self):
        try:
            conn = oursql.connect(host=self._database.host, user=self._database.user, passwd=self._database.passwd,
                                  port=self._database.port, autoping=True, autoreconnect=True)
        except:
            self._logger.error('kodi: connection to mysql server failed.')
            return False
        else:
            self._cur = conn.cursor()
            return True

    def _sqlexecute(self, sqlcmd, expected=-1, fetch=False):
        if self._cur is None:
            self._logger.error('kodi: trying to query disconnected mysql server.')
            return False
        if fetch:
            try:
                self._cur.execute(sqlcmd)
                rows = self._cur.fetchall()
                # rowcount = len(rows)
            except:
                return False
            else:
                return rows
        else:
            try:
                self._cur.execute(sqlcmd)
                rowcount = self._cur.rowcount
            except:
                return False
            if rowcount != expected and expected != -1:
                # if more rows were affected than we intended, something went wrong :(
                # -1 means we dont expect any specific amount of rows
                return False
            return True

    def _checkdir(self, path, rootpath=None):
        if rootpath is None:
            sqlcmd_getroot = 'SELECT idPath FROM path WHERE strPath="{0}"'.format(path)
        else:
            sqlcmd_getroot = 'SELECT idPath FROM path WHERE strPath="{0}" AND idParentPath="{1}"'.format(path, rootpath)
        rows = self._sqlexecute(sqlcmd_getroot, expected=1, fetch=True)
        if not rows:
            if rootpath is None:
                sqlcmd_setroot = 'INSERT INTO path (strPath, strContent, strScraper, strHash, strSettings, ' \
                                 'dateAdded) VALUES ("{0}", NULL, NULL, NULL, NULL, NULL)'.format(path)
            else:
                sqlcmd_setroot = 'INSERT INTO path (strPath, strContent, strScraper, strHash, strSettings, ' \
                                 'dateAdded, idParentPath) VALUES ("{0}", NULL, NULL, NULL, NULL, NULL, ' \
                                 '{1})'.format(path, rootpath)
            rows = self._sqlexecute(sqlcmd_setroot, expected=1)
            if not rows:
                return False
            return self._cur.lastrowid
        elif len(rows) == 1:
            return rows[0][0]
        else:  # TODO: got more than 1 result, possible db corruption, should we remove duplicates?
            return rows[0][0]  # for now return the same as when we would have received just 1 result

    def init(self, scrapetype):
        # connect to mysql server:
        if not self._sqlprepare():
            return False
        # figure out kodi api number from the db:
        if scrapetype == 'movie' or scrapetype == 'tv':
            dbname = 'MyVideos'
        else:  # TODO: implement other types?
            dbname = ''
        result = self._sqlexecute('SHOW DATABASES LIKE "{0}%"'.format(dbname), fetch=True)  # get all databases
        if not result:
            return False
        apilist = []
        for entry in result:
            apilist.append(int(''.join(element for element in entry[0] if element.isdigit())))  # get just the digits
        apilist.sort()
        # switch to the right database:
        if not self._sqlexecute('USE {0}'.format(dbname + str(apilist[-1]))):
            return False
        # check if the root path exists in the db or else add it:
        result = self._checkdir(self._substpath)
        if not result:
            return False
        self._rootpathid = result
        return True

    def checksubdir(self, path):
        return self._checkdir(path, self._rootpathid)

    def fullpath(self, path):
        return self._substpath + path + '/'

    def checkmovie(self, path, filenames, israr, rarname):
        substpath = self._substpath + path + '/'
        for filename in filenames:
            if israr:
                filename = 'rar://' + parse.quote(substpath, safe='') + rarname + '/' + filename
            sqlcmd_getmovie = 'SELECT idMovie FROM movieview WHERE strPath="{0}" AND strFilename="{1}"'.format(
                substpath, filename)
            rows = self._sqlexecute(sqlcmd_getmovie, 1, True)
            if rows:
                return True
        return False

    def addmovie(self, movie, path):
        print(movie.imdbid)
        return True

    def cleanup(self):
        pass  # TODO: close mysql connection and ???
