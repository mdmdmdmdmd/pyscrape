import os
import glob

import rarfile

import kodi


class Scrape(object):
    def __init__(self, rootpath, logger, scrapetype):  # , mode='kodi'):
        self._rootpath = rootpath
        self._logger = logger
        self._type = scrapetype  # 'movie', 'tv', ??? -- what type of media is to be expected in the root path
        # self._mode = mode  # 'kodi', ??? -- which system we scrape for, so far only kodi implemented

    def _getrarlist(self, rarname):
        rarfile.NEED_COMMENTS = 0
        if not rarfile.is_rarfile(rarname):
            return False
        rararc = rarfile.RarFile(rarname)
        filelist = []
        for rarentry in rararc.infolist():
            fn = rarentry.filename
            if fn[-4:] == '.mkv' or fn[-4:] == '.avi' or fn[-4:] == '.ogm':
                filelist.append(fn)
        if len(filelist) == 0:
            return False
        return filelist

    def _mediafiles(self, path):  # TODO: improve this (very confusing naming of vars)
        basefiles = []
        mediafiles = glob.glob(path + '/*.rar')
        if len(mediafiles) < 1:  # no rar files found, checking for mkv/avi/ogm
            mediafiles = glob.glob(path + '/*.mkv')  # TODO: add avi and ogm extensions
            if len(mediafiles) < 1:
                return False
            for basefile in mediafiles:
                basefiles.append(os.path.split(basefile))
        else:
            mediafiles.sort()
            rarname = os.path.split(mediafiles[0])
            rarbasename = rarname[1]
            rarname = path + '/' + rarname[1]
            filelist = self._getrarlist(rarname)
            if filelist:
                israr = True
                mediafiles = []
                for filename in filelist:
                    mediafiles.append(rarname + '/' + filename)
                    basefiles.append(filename)
            else:
                return False

    def _moviedirs(self, pathlist):
        for path in pathlist:
            if path[0] == '.':  # skip hidden dirs
                continue
            fullpath = self._module.fullpath(path)
            checked = self._module.checksubdir(fullpath)
            if not checked:  # TODO: change this back to continue!
                # continue
                break
            mediafiles = self._mediafiles(self._rootpath + path)
            break

    def _tvdirs(self, pathlist):
        pass

    def preparekodi(self, substpath, host, port, user, passwd):  # set kodi specific stuff, do this first before .run()
        database = kodi.Database(host, port, user, passwd)
        self._module = kodi.Kodi(database, substpath, self._logger)

    def run(self):
        if not self._module.init(self._type):
            self._logger.error('scrape: initialization of kodi module failed.')
            return False
        try:
            walklist = os.walk(self._rootpath)
        except:
            self._logger.error('scrape: can not read root path.')
            return False
        else:
            pathlist = None
            for root, dirs, files in walklist:
                pathlist = dirs
                break
            if self._type == 'movie':
                self._moviedirs(pathlist)
            elif self._type == 'tv':  # TODO: implement tv show scraping
                pass
            return True

    def resume(self):
        pass  # TODO: add resume mode (possibly using a sqlite db for state?)
