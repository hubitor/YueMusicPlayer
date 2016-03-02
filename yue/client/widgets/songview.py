import sys
isPython3 = sys.version_info[0]==3
if isPython3:
    unicode = str
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from yue.core.song import Song

class SongPositionView(QWidget):

    seek = pyqtSignal( int )
    next = pyqtSignal()
    prev = pyqtSignal()

    def __init__(self, parent=None):
        super(SongPositionView,self).__init__(parent);

        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0,0,0,0)

        self.slider = SongPositionSlider( self );
        self.slider.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        #self.slider.setTickInterval(15)
        #self.slider.setTickPosition(QSlider.TicksBelow)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setMinimumWidth(16)
        self.btn_prev.setMaximumWidth(32)
        self.btn_prev.clicked.connect(lambda:self.prev.emit())
        self.btn_prev.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Fixed)

        self.btn_next = QPushButton(">")
        self.btn_next.setMinimumWidth(16)
        self.btn_next.setMaximumWidth(32)
        self.btn_next.clicked.connect(lambda:self.next.emit())
        self.btn_next.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Fixed)

        self.hbox.addWidget(self.btn_prev)
        self.hbox.addWidget(self.slider)
        self.hbox.addWidget(self.btn_next)

    def setValue(self, v):
        if not self.slider.user_control:
            self.slider.setValue( v )

    def setMaximum(self, v):
        self.slider.setMaximum(v)

class SongPositionSlider(QSlider):

    def __init__(self, view, parent=None):
        super(SongPositionSlider,self).__init__(Qt.Horizontal,parent);

        self.user_control = False
        self.view = view;

        #self.actionTriggered.connect(self.actionEvent)
        self.sliderReleased.connect(self.on_release)
        self.sliderPressed.connect(self.on_press)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        pos = int(self.maximum()*(event.x()/self.width()))
        self.view.seek.emit( pos )

    def on_press(self):
        self.user_control = True

    def on_release(self):
        self.user_control = False
        self.view.seek.emit( self.value() )

def fmt_seconds( t ):
    m,s = divmod( t, 60)
    if m > 60:
        h,m = divmod(m,60)
        return "%d:%02d:%02d"%(h,m,s)
    else:
        return "%d:%02d"%(m,s)

class CurrentSongView(QWidget):
    def __init__(self, parent=None):
        super(CurrentSongView,self).__init__(parent);

        self.song = Song.new()
        self.playlist_index  = 0
        self.playlist_length = 0
        self.equalizer_enabled = False

        self.offseta = 0
        self.offsett = 0
        self.offsetb = 0
        self.offseta_max = -1
        self.offsett_max = -1
        self.offsetb_max = -1
        self.region_width = 0

        self.text_time = ""

        fh = QFontMetrics(self.font()).height()
        self.padt = 2
        self.padb = 2
        self.padtb = self.padt+self.padb
        self.setFixedHeight( (fh+self.padtb) * 4)

        self.menu_callback = None;

        self.setMouseTracking(True)
        self.disable_autoscroll = False

        self.timer_autoscroll = QTimer(self)
        self.timer_autoscroll.timeout.connect(self.on_timeout_event)
        self.timer_autoscroll.setSingleShot(False)
        self.timer_autoscroll.setInterval(125)
        self.timer_autoscroll.start(125)

        self.scroll_index = 0;
        self.scroll_speed = 2 # pixels per step

    def setPosition(self, position ):
        length = self.song[Song.length]
        remaining = length - position

        self.text_time = "%s/%s - %s"%(
                fmt_seconds(position),
                fmt_seconds(length),
                fmt_seconds(remaining) )

        self.update()

    def setCurrentSong(self, song):
        self.song = song

        self.offseta = 0
        self.offsett = 0
        self.offsetb = 0
        self.offseta_max = -1
        self.offsett_max = -1
        self.offsetb_max = -1

        self.scroll_index = 0

        self.setPosition( 0 )

        if not self.timer_autoscroll.isActive():
            self.timer_autoscroll.start(125)

    def setPlaylistInfo(self,index,length):
        self.playlist_index  = index
        self.playlist_length = length
        self.update()

    def setEQEnabled(self,b):
        self.equalizer_enabled = b
        self.update()

    def on_timeout_event(self):
        if self.disable_autoscroll:
            return

        if self.scroll_index == 0:
            if self.offseta < self.offseta_max and \
               self.offseta_max > self.region_width:
                self.offseta += self.scroll_speed
            else:
                self.offseta = 0

                if self.offsett_max > self.region_width:
                    self.scroll_index = 1
                elif self.offsetb_max > self.region_width:
                    self.scroll_index = 2
                #elif self.offseta_max > self.region_width:
                #    self.timer_autoscroll.stop()

        elif self.scroll_index == 1:
            if self.offsett < self.offsett_max and \
               self.offsett_max > self.region_width:
                self.offsett += self.scroll_speed
            else:
                self.offsett = 0

                if self.offsetb_max > self.region_width:
                    self.scroll_index = 2
                elif self.offseta_max > self.region_width:
                    self.scroll_index = 0
                #elif self.offsett_max > self.region_width:
                #    self.timer_autoscroll.stop()

        elif self.scroll_index == 2:
            if self.offsetb < self.offsetb_max and \
               self.offsetb_max > self.region_width:
                self.offsetb += self.scroll_speed
            else:
                self.offsetb = 0

                if self.offseta_max > self.region_width:
                    self.scroll_index = 0
                elif self.offsett_max > self.region_width:
                    self.scroll_index = 1
                #elif self.offsetb_max > self.region_width:
                #    self.timer_autoscroll.stop()

        self.update()

    def mouseMoveEvent(self,event):

        h=self.height()/4
        p=int(event.y()/h)

        if p==0:
            self.offseta = int((self.offseta_max*1.5) * (event.x()/self.width()))
            self.offsett = 0
            self.offsetb = 0
        if p==1:
            self.offseta = 0
            self.offsett = int((self.offsett_max*1.5) * (event.x()/self.width()))
            self.offsetb = 0
        if p==2:
            self.offseta = 0
            self.offsett = 0
            self.offsetb = int((self.offsetb_max*1.5) * (event.x()/self.width()))
        self.update()

    def enterEvent(self,event):
        self.disable_autoscroll = True
        self.update()

    def leaveEvent(self,event):
        self.disable_autoscroll = False
        self.scroll_index = 0;
        self.offseta = 0
        self.offsett = 0
        self.offsetb = 0
        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()

        painter = QPainter(self)
        fh = painter.fontMetrics().height()

        fw1 = painter.fontMetrics().width('0')
        fw3 = (fw1+1)*3
        fwt = painter.fontMetrics().width(self.text_time)

        if self.offseta_max < 0:
            self.offseta_max = painter.fontMetrics().width(self.song[Song.artist])
            self.offsett_max = painter.fontMetrics().width(self.song[Song.title])
            self.offsetb_max = painter.fontMetrics().width(self.song[Song.album])

        rh = fh + self.padtb
        padl = 2;
        padr = 2;
        padlr = padl+padr

        row1h = fh + self.padt
        row2h = row1h+self.padtb+fh
        row3h = row2h+self.padtb+fh
        row4h = row3h+self.padtb+fh

        text = ""
        if 0<= self.playlist_index < self.playlist_length:
            text = "%d/%d"%(self.playlist_index,self.playlist_length)
        pltextlen = len(text)
        painter.drawText(padl,row1h-fh,w-padlr-fw3,fh,Qt.AlignRight,text)

        if self.equalizer_enabled:
            painter.drawText(padl,row2h-fh,w-padlr-fw3,fh,Qt.AlignRight,"EQ")

        #painter.drawText(padl,row3h-fh,w-padlr-fw3,fh,Qt.AlignRight,"33")

        text = "%d"%self.song[Song.play_count]
        painter.drawText(padl,row4h-fh,w-padlr-fw3,fh,Qt.AlignRight,text)
        painter.drawText(padl,row4h,self.text_time)

        rw = w - padl - padr - fwt - 2*fw3
        #painter.drawRect(2*padl+fwt,row4h-fh,rw,fh)
        recth=4*rh-self.padtb
        painter.drawRect(w-fw3,self.padt,fw3-padr,recth)
        recths = int(recth*(self.song[Song.rating]/10))
        rectho = recth-recths
        painter.fillRect(w-fw3+1,self.padt+rectho+1,fw3-padr-1,recths-1,QBrush(QColor(0,0,200)))

        painter.setClipping(True)
        self.region_width = w-(fw1+1)*pltextlen - fw3
        painter.setClipRegion(QRegion(0,0,self.region_width,row4h))

        painter.drawText(padl-self.offseta,row1h,self.song[Song.artist])
        painter.drawText(padl-self.offsett,row2h,self.song[Song.title])
        painter.drawText(padl-self.offsetb,row3h,self.song[Song.album])

    def setMenuCallback(self,cbk):
        """
        callback as a function which accepts a menu and a song
        and returns nothing. the function should add actions to
        the given song
        """
        self.menu_callback = cbk

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.RightButton and self.menu_callback is not None:
            menu = QMenu(self)
            self.menu_callback(menu,self.song)
            menu.exec_( event.globalPos() )