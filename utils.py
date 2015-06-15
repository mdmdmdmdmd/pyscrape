import urllib.request

import rarfile
import unidecode


def getrarlist(rarname, filelist, mediatypes):
    rarfile.NEED_COMMENTS = 0
    if not rarfile.is_rarfile(rarname):
        return False
    rararc = rarfile.RarFile(rarname)
    for rarentry in rararc.infolist():
        fn = rarentry.filename
        if fn[-3:] in mediatypes:
            filelist.append(fn)
    if len(filelist) == 0:
        return False
    return True

def geturl(url):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; rv:25.0) Gecko/20100101 Firefox/25.0')
    try:
        response = urllib.request.urlopen(req)
    except urllib.request.HTTPError:
        return False
    html = response.read()
    response.close()
    return html

def unicodetoascii(string):
    ger = string.replace('ü', 'ue')
    ger = ger.replace('ö', 'oe')
    ger = ger.replace('ä', 'ae')
    ger = ger.replace('Ü', 'Ue')
    ger = ger.replace('Ö', 'Oe')
    ger = ger.replace('Ä', 'Ae')
    result = dict()
    result['int'] = unidecode.unidecode(string)
    result['ger'] = unidecode.unidecode(ger)
    return result
