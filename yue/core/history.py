
# single instance pattern
# contains boolean : save history true false
# mimic update pattern

from .search import SearchGrammar, BlankSearchRule, sql_search, ParseError
from yue.core.song import Song
from yue.core.sqlstore import SQLTable, SQLView
from calendar import timegm
import time

import sys
isPython3 = sys.version_info[0]==3
if isPython3:
    unicode = str

class History(object):
    """docstring for Library"""
    __instance = None
    def __init__(self, sqlstore):
        super(History, self).__init__()
        fields = [
            ("date","INTEGER"),
            ("uid","INTEGER"),
            ("column","text"),
            ("value","text"),
        ]

        self.db = SQLTable( sqlstore ,"history", fields)


        #SELECT s.uid, h.date, h.column, h.value, a.artist, b.album, s.title
        #FROM songs s, artists a, albums b, history h
        #WHERE s.uid=h.uid AND a.uid = s.artist AND b.uid = s.album

        viewname = "history_view"
        colnames = [ "uid", "date", "column", "value", "artist", "album", "title" ]
        cols = [ 's.uid', 'h.date', 'h.column', 'h.value', 'a.artist', 'b.album', 's.title']
        cols = ', '.join(cols)
        tbls = "songs s, artists a, albums b, history h"
        where = "s.uid=h.uid AND a.uid = s.artist AND b.uid = s.album"
        sql = """CREATE VIEW IF NOT EXISTS {} as SELECT {} FROM {} WHERE {}""".format(viewname,cols,tbls,where)

        self.view = SQLView( sqlstore, viewname, sql, colnames)
        self.sqlstore = sqlstore
        self.enabled_log = False
        self.enabled_update = False


        self.grammar = HistorySearchGrammar( )

    @staticmethod
    def init( sqlstore ):
        History.__instance = History( sqlstore )

    @staticmethod
    def instance():
        return History.__instance

    def setLogEnabled(self, b):
        """ enable recording of playback events"""
        self.enabled_log = bool(b)

    def setUpdateEnabled(self, b):
        """ enable recording of record changes """
        self.enabled_update = bool(b)

    def isLogEnabled(self):
        return self.enabled_log

    def isUpdateEnabled(self):
        return self.enabled_update

    def __len__(self):
        return self.db.count()

    def size(self):
        return self.db.count()

    def update(self,c, uid,**kwargs):

        if not self.enabled_update:
            return

        date = timegm(time.localtime(time.time()))
        data = {
            "date" : date,
            "uid"  : uid,
        }
        for col,val in kwargs.items():
            # don't record changes for path, since that will overwrite
            # the path on import - bad!
            if col == Song.path:
                continue;
            data['column'] = col
            data['value'] = str(val)
            self.db._insert(c,**data)

    def incrementPlaycount(self, c, uid, date):

        if not self.enabled_log:
            return

        kwargs = {
            "date" : date,
            "uid"  : uid,
            "column" : Song.playtime
        }
        self.db._insert(c,**kwargs)

    def export(self):

        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()
            c.execute("SELECT date,uid,column,value FROM history ORDER BY date ASC")

            item = c.fetchone()
            while item is not None:
                yield dict(zip(self.db.column_names,item))
                item = c.fetchone()

    def delete(self,records_lst):
        """ delete a record, or a list of records
        """
        lst = records_lst
        if isinstance(records_lst,dict):
            lst = [records_lst, ]

        with self.sqlstore.conn:
            c = self.sqlstore.conn.cursor()

            for record in lst:
                self._delete(c,record)

    def _delete(self,c,record):
        date = record['date']
        uid = record['uid']
        c.execute("DELETE from history where uid=? and date=?",(uid,date))

    def search(self, rule , case_insensitive=True, orderby=None, reverse = False, limit = None):

        if rule is None:
            rule = BlankSearchRule();
        elif isinstance(rule,(str,unicode)):
            rule = self.grammar.ruleFromString( rule )
        else:
            raise ParseError("invalid rule type: %s"%type(rule))
        if isinstance(rule,(str,unicode)):
            raise ParseError("fuck. invalid rule type: %s"%type(rule))
        if orderby is not None:
            if not isinstance( orderby, (list,tuple)):
                orderby = [ orderby, ]

        echo = False
        return sql_search( self.view, rule, case_insensitive, orderby, reverse, limit, echo )


class HistorySearchGrammar(SearchGrammar):
    """docstring for HistorySearchGrammar"""

    def __init__(self):
        super(HistorySearchGrammar, self).__init__()

        # [ "uid", "date", "column", "value", "artist", "album", "title" ]
        self.text_fields = {'column', 'artist','album','title'}
        self.date_fields = {'date',}

        self.columns = {self.all_text, "uid", "date", 'column', 'artist','album','title', }
        self.col_shortcuts = {
                                "art"    : "artist", # copied from Song
                                "artist" : "artist",
                                "abm"    : "album",
                                "alb"    : "album",
                                "album"  : "album",
                                "ttl"    : "title",
                                "tit"    : "title",
                                "title"  : "title",
                                "data"   : "column",
                            }

    def translateColumn(self,colid):
        if colid in self.col_shortcuts:
            return self.col_shortcuts[colid]
        if colid in self.columns:
            return colid
        raise ParseError("Invalid column name `%s`"%colid)
