
import os

import sys
isPython3 = sys.version_info[0]==3
if isPython3:
    unicode = str

from .search import sql_search, ruleFromString
#from kivy.logger import Logger
#from kivy.storage.dictstore import DictStore

#from yue.settings import Settings
from yue.core.song import read_tags
from yue.core.sqlstore import SQLTable, SQLView

try:
    # 3.x name
    import configparser
except ImportError:
    # 2.x name
    import ConfigParser as configparser
import codecs

class Library(object):
    """docstring for Library"""
    __instance = None
    def __init__(self, sqlstore):
        super(Library, self).__init__()

        artists = [
            ("uid","INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("artist","text"),
            ("count","INTEGER DEFAULT 0")
        ]

        albums = [
            ("uid","INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("artist","INTEGER"),
            ("album","text"),
            ("count","INTEGER DEFAULT 0")
        ]
        album_foreign_keys = [
            "FOREIGN KEY(artist) REFERENCES artists(uid)",
        ]

        #composers = [
        #    ("uid","INTEGER PRIMARY KEY AUTOINCREMENT"),
        #    ("composer","text")
        #]

        songs_columns = [
            ('uid','integer PRIMARY KEY AUTOINCREMENT'),
            ('path',"text"),
            #('artist',"text"),
            ('artist',"INTEGER"),
            ('composer',"text DEFAULT ''"),
            #('album','text'),
            ('album','INTEGER'),
            ('title','text'),
            ('genre',"text DEFAULT ''"),
            ('year','integer DEFAULT 0'),
            ('country',"text DEFAULT ''"),
            ('lang',"text DEFAULT ''"),
            ('comment',"text DEFAULT ''"),
            ('album_index','integer DEFAULT 0'),
            ('length','integer DEFAULT 0'),
            ('last_played','integer DEFAULT 0'),
            ('playcount','integer DEFAULT 0'),
            ('rating','integer DEFAULT 0'),
        ]
        songs_foreign_keys = [
            "FOREIGN KEY(artist) REFERENCES artists(uid)",
            "FOREIGN KEY(album) REFERENCES albums(uid)",
        ]

        self.sqlstore = sqlstore
        self.artist_db = SQLTable( sqlstore ,"artists", artists)
        self.album_db = SQLTable( sqlstore ,"albums", albums, album_foreign_keys)
        self.song_db = SQLTable( sqlstore ,"songs", songs_columns, songs_foreign_keys)

        colnames = [ x[0] for x in songs_columns ]

        viewname = "library"
        cols = "s.uid, s.path, a.artist, s.composer, b.album, s.title, s.genre, s.year, s.country, s.lang, s.comment, s.album_index, s.length, s.last_played, s.playcount, s.rating"
        tbls = "songs s, artists a, albums b"
        where = "s.artist=a.uid AND s.album=b.uid"
        sql = """CREATE VIEW IF NOT EXISTS {} as SELECT {} FROM {} WHERE {}""".format(viewname,cols,tbls,where)


        self.song_view = SQLView( sqlstore, "library", sql, colnames)

    @staticmethod
    def init( sqlstore ):
        Library.__instance = Library( sqlstore )

    @staticmethod
    def instance():
        return Library.__instance

    def __len__(self):
        return self.song_db.count()

    def insert(self,**kwargs):

        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            return self._insert(c, **kwargs)

    def _insert(self,c, **kwargs):
        kwargs['artist'] = self.artist_db._get_id_or_insert(c,artist=kwargs['artist'])
        kwargs['album'] = self.album_db._get_id_or_insert(c,album=kwargs['album'],artist=kwargs['artist'])
        c.execute("UPDATE artists SET count=count+1 WHERE uid=?",(kwargs['artist'],))
        c.execute("UPDATE albums SET count=count+1 WHERE uid=?",(kwargs['album'],))
        return self.song_db._insert(c,**kwargs)

    def update(self,uid,**kwargs):
        """ update song values in the database """
        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            self._update_one(c, uid, **kwargs)
            c.execute("DELETE FROM artists WHERE count=0")
            c.execute("DELETE FROM albums WHERE count=0")

    def update_many(self,songs):
        """ update song values in the database """
        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            for song in songs:
                self._update_one(c, song['uid'], **songs)
            c.execute("DELETE FROM artists WHERE count=0")
            c.execute("DELETE FROM albums WHERE count=0")

    def _update_one(self,c, uid, **kwargs):
        info = list(self.song_db._select_columns(c,['artist','album'],uid=uid))[0]
        old_art_id = info['artist']
        old_abm_id = info['album']

        # cannot change uid
        if 'uid' in kwargs:
            del kwargs['uid']

        # altering artist, album requires updating count of songs
        # and removing artists that no longer exist.
        if 'artist' in kwargs:
            new_art_id = self.artist_db._get_id_or_insert(c,artist=kwargs['artist'])
            c.execute("UPDATE artists SET count=count+1 WHERE uid=?",(new_art_id,))
            c.execute("UPDATE artists SET count=count-1 WHERE uid=?",(old_art_id,))
            # update field as integer, not string
            kwargs['artist'] = new_art_id
            old_art_id = new_art_id

        if 'album' in kwargs:
            new_abm_id = self.album_db._get_id_or_insert(c,album=kwargs['album'], artist=old_art_id)
            c.execute("UPDATE albums SET count=count+1 WHERE uid=?",(new_abm_id,))
            c.execute("UPDATE albums SET count=count-1 WHERE uid=?",(old_abm_id,))
            # update field as integer, not string
            kwargs['album'] = new_abm_id

        # update all remaining fields
        if kwargs:
            self.song_db._update(c, uid, **kwargs)

    def increment(self,uid,field,value=1):
        """
        increment an integer field for a song
        e.g.
            self.increment(uid,'playcount')
        """
        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            c.execute("UPDATE songs SET %s=%s%+d WHERE uid=?"%(field,field,value),(uid,))

    def loadTestData(self,inipath,force=False):
        """
        read an ini file containing names and locations of songs.

        force: reload ini even if library db exists

        each section should be an unique integer starting at 1

        example:

        [1]
        artist=David Bowie
        title=....
        album=....
        path=/path/to/file

        [2]
        artist=David Bowie
        title=....
        album=....
        path=/path/to/file
        """

        #if not force and os.path.exists(Settings.instance().db_path):
        #    # delete the library to load the test file
        #    Logger.info('Library Found - not loading test data')
        #    return

        try:
            self.song_view.get(1)
            return
        except:
            pass
        if not os.path.exists(inipath):
            #Logger.critical('test library not found: %s'%inipath)
            return

        #Logger.info('loading test library: %s'%inipath)

        config = configparser.ConfigParser()
        config.readfp(codecs.open(inipath,"r","utf-8"))

        def get_default(section,option,default):
            if config.has_option(section,option):
                return config.get(section,option)
            return default

        for section in config.sections():
            print(section)
            song = {
                "artist" : get_default(section,"artist","Unkown Artist"),
                "album"  : get_default(section,"album" ,"Unkown Album"),
                "title"  : get_default(section,"title" ,"Unkown Title"),
                "path"   : get_default(section,"path"  ,""),

            }
            self.insert(**song)

        #Logger.info('loading test library: %s'%inipath)

    def loadPath(self,songpath):
        """ does not check for duplicates """
        #Logger.info("library: load song path: %s"%songpath)
        song = read_tags( songpath )
        return self.insert(**song)

    def songFromId(self,uid):
        return self.song_view.get(uid)

    def toPathMap(self):
        """
        the current kivy datastore impl for find() is to scan the entire store
        for a key value pair that matches a given filter.

        this pre-computes a dictionary of path -> uid, to quickly test if
        a given path exists in the db.
        """
        m = {}
        for song in self.song_view.iter():
            m[song['path']] = song['uid']
        return m

    def iter(self):
        return self.song_view.iter()

    def search(self, rule , case_insensitive=True, orderby=None, reverse = False):

        if isinstance(rule,(str,unicode)):
            rule = ruleFromString( rule )
        return sql_search( self.song_view, rule, case_insensitive, orderby, reverse )

    def getArtists(self):
        """ get a list of artists within the database."""
        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            cols = ['uid','artist','count']
            return self.artist_db._select_columns(c, cols)

    def getAlbums(self,artistid):
        """ return all albums associated with a given artist id """
        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            cols = ['uid','album','count']
            return self.album_db._select_columns(c, cols, artist=artistid)


