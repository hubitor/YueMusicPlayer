#! python34 $this

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

import os, sys
dirpath = os.path.dirname(os.path.abspath(__file__))
dirpath = os.path.dirname(dirpath)
sys.path.insert(0,dirpath)

isPython3 = sys.version_info[0]==3
if isPython3:
    unicode = str

import yue
from yue.client.widgets.LargeTable import LargeTable, TableDualColumn, TableColumnImage
from yue.client.widgets.LineEdit import LineEdit

from yue.core.song import Song
from yue.core.search import ParseError
from yue.core.sqlstore import SQLStore
from yue.core.library import Library

from yue.client.ui.ingest_dialog import IngestProgressDialog
from yue.client.ui.movefile_dialog import MoveFileProgressDialog
from yue.client.ui.rename_dialog import RenameDialog
from yue.client.explorer.source import DirectorySource,SourceListView

"""
TODO:
    ability for smart file renaming / moving

    changing the name of a directory, or renaming a file
    requires updating the database if the file is in the data base

    on linux this is easy since paths are case sensitive, and slashes
    always go one direciton

    on windows paths are not case sensitive and slashes can go either
    direction

    in sql, i can run a wildcard search by executing, for example:
        SELECT * FROM table WHERE 'D:_Music%'

        % : 0 or more characters
        _ : 1 character
        [\\/] : match a set of characters

    I need to introduce a Library search function which queries files
    that have paths which match a string. The semantics are different
    per platform.

    there is an additional filter, files exactly in a directory,
    or paths that start with a directory prefix. this could mean a total
    of one or two functions, depending on implementation

"""


class LineEdit_Path(LineEdit):

    def __init__(self,parent,table):
        super(LineEdit_Path,self).__init__(parent)
        self.table = table

    def keyReleaseEvent(self,event=None):
        super(LineEdit_Path,self).keyReleaseEvent(event)
        if event.key() == Qt.Key_Down:
            self.table.clearSelection( )
            self.table.setSelection( [0,] )
            self.table.updateTable(0)
            self.table.setFocus()

    def keyReleaseEnter(self,text):
        self.parent().chdir( self.text(), True )

class ResourceManager(object):
    """docstring for ResourceManager"""
    _instance = None

    DIRECTORY = 1
    FILE = 2
    SONG = 3

    def __init__(self):
        super(ResourceManager, self).__init__()
        self.resources = {}
        self.resources[ResourceManager.FILE]      = QPixmap(':/img/app_file.png')
        self.resources[ResourceManager.SONG]      = QPixmap(':/img/app_song.png')
        self.resources[ResourceManager.DIRECTORY] = QPixmap(':/img/app_folder.png')

    def get(self,kind):
        return self.resources[kind]

    def width(self):
        return self.resources[ResourceManager.FILE].width()

class FileTable(LargeTable):
    """
    """

    def __init__(self, view, parent=None):
        self.rm = ResourceManager()

        super(FileTable,self).__init__(parent)

        self.setLastColumnExpanding( True )
        self.showColumnHeader( False )
        self.showRowHeader( False )

        self.view = view

        self.position_stack = []

    def initColumns(self):

        self.columns.append( TableColumnImage(self,'isDir') )
        self.columns[-1].setTextTransform( self.item2img )
        self.columns[-1].width = self.rm.width() + 4 # arbitrary pad, image is centered

        self.columns.append( TableDualColumn(self,'name',"File Name") )
        self.columns[-1].setSecondaryTextTransform(lambda r,item : str(r['size']))

    def mouseReleaseRight(self,event):

        items = self.getSelection()

        is_files = all(not item['isDir'] for item in items)


        contextMenu = QMenu(self)

        # file manipulation options

        act = contextMenu.addAction("Rename", lambda : self.parent().action_rename( items[0] ))
        act.setDisabled( len(items)!=1 )

        act = contextMenu.addAction("New Folder", lambda : self.parent().action_newfolder())
        act.setDisabled( len(items)!=1 )


        contextMenu.addAction("Cut", lambda : self.parent().action_cut( items ))
        act = contextMenu.addAction("Paste", lambda : self.parent().action_paste( ))
        act.setDisabled( not self.parent().canPaste() )

        contextMenu.addSeparator()

        # library options

        if len(items) == 1 and not is_files:
            act = contextMenu.addAction("Import Directory", lambda : self.parent().action_ingest( items ))
            act.setDisabled( not self.parent().canIngest() )
        else:
            act = contextMenu.addAction("Import", lambda : self.parent().action_ingest( items ))
            act.setDisabled( not is_files or not self.parent().canIngest())


        action = contextMenu.exec_( event.globalPos() )

    def mouseDoubleClick(self,row,col,event):

        if event.button() == Qt.LeftButton:
            item = self.view[row]

            if item['name'] == '..':
                self.parent().chdir( self.view.parent(self.view.pwd()) )
                if self.position_stack:
                    idx = self.position_stack.pop()
                    self.scrollTo( idx )
                    self.setSelection([idx,])
            elif item['isDir']:

                self.position_stack.append(row)
                self.scrollTo( 0 )
                self.parent().chdir( item['name'] )

    def sortColumn(self,*args):
        pass

    def item2img(self,item,isDir):
        if isDir:
            return self.rm.get(ResourceManager.DIRECTORY)
        ext = os.path.splitext(item['name'])[1]
        if self.parent().supportedExtension( ext ):
            return self.rm.get(ResourceManager.SONG)
        return self.rm.get(ResourceManager.FILE)

class ExplorerView(QWidget):
    """docstring for MainWindow"""
    def __init__(self, controller):

        super(ExplorerView, self).__init__()
        self.vbox = QVBoxLayout(self)

        self.controller = controller

        self.source = DirectorySource()
        self.view = SourceListView(self.source,self.source.root())

        self.tbl_file = FileTable( self.view, self )
        self.tbl_file.addRowHighlightComplexRule( self.indexInLibrary , QColor(128,128,224))

        self.txt_path = LineEdit_Path(self,self.tbl_file)
        #self.txt_path.textEdited.connect(self.onTextChanged)

        self.vbox.addWidget( self.txt_path )
        self.vbox.addWidget( self.tbl_file.container )

        self.tbl_file.setData(self.view)
        self.txt_path.setText(self.view.pwd())

        self.dialog = None
        self.cut_items = None
        self.cut_root = ""

        self.list_library_files = set()

    def indexInLibrary(self,idx):
        return self.view[idx]['name'] in self.list_library_files

    def chdir(self,path, clear_stack=False):
        pwd = self.view.pwd()

        try:
            if clear_stack:
                self.tbl_file.position_stack=[]
            self.view.chdir(path)
        except OSError as e:
            sys.stderr.write(str(e))
            QMessageBox.critical(self,"Access Error","Error Opening `%s`"%path)
            # reopen the original current directory.
            self.view.chdir( pwd )

        songs = Library.instance().searchDirectory(self.view.pwd(),False)
        self.list_library_files = set( os.path.split(song[Song.path])[1] \
                                       for song in songs )

        self.txt_path.setText(self.view.pwd())
        self.tbl_file.update()

    def supportedExtension(self,ext):
        return ext == ".mp3"

    def action_rename(self, item):
        diag = RenameDialog(item['name'],parent=self)
        if diag.exec_():
            print(diag.text())

    def action_newfolder(self):

        diag = RenameDialog("New Folder","Create Folder",parent=self)
        if diag.exec_():
            print(diag.text())

    def action_ingest(self, items):

        paths = [ self.view.realpath(item['name']) for item in items ]
        self.dialog = IngestProgressDialog(self.controller, paths, self)
        self.dialog.setOnCloseCallback(self.onDialogExit)
        self.dialog.start()
        self.dialog.show()

    def onDialogExit(self):
        self.dialog = None
        print("complete")

    def canIngest( self ):
        return self.dialog is None

    def action_cut(self, items):
        self.cut_items = [ self.view.realpath(item['name']) for item in items ]
        self.cut_root = self.view.pwd()

    def action_paste(self):
        # TODO: create a progress dialog to initiate the move

        self.dialog = MoveFileProgressDialog(self.view.pwd(), self.cut_items, self)
        self.dialog.setOnCloseCallback(self.onDialogExit)
        self.dialog.start()
        self.dialog.show()

    def canPaste( self ):
        return self.cut_items is not None and self.cut_root != self.view.pwd()