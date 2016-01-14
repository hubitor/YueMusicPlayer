

path = r"D:\Music\Japanese\6ft.Down\[2010] Invitation to Anesthesia\01 Fanatic For Rejection.mp3"


from kivy.properties import BooleanProperty
from kivy.graphics import Color, Rectangle, Line

from kivy.core.audio import SoundLoader

#sound = SoundLoader.load(path)
#sound.bind(on_play=)
#
#if sound:
#    print("Sound found at %s" % sound.source)
#    print("Sound is %.3f seconds" % sound.length)
#    sound.play()

# https://kivy.org/docs/api-kivy.uix.screenmanager.html
class SoundManager(object):
    """docstring for SoundManager"""
    __instance = None
    def __init__(self):
        super(SoundManager, self).__init__()
        self.sound = None
        self.volume = 0.5
        self.current_position = 0
        # todo use a mutex to control mode_stop
        # when True, stop was issued by the user, intended for 'pause'
        # when false, stop was issued by end-of-file
        self.mode_stop = False

    @staticmethod
    def init():
        SoundManager.__instance = SoundManager()

    @staticmethod
    def instance():
        return SoundManager.__instance

    def load(self,path):

        self.sound = SoundLoader.load(path)
        if self.sound is not None:
            self.sound.volume = self.volume
            self.sound.bind(on_play=self.on_play)
            self.sound.bind(on_stop=self.on_stop)

    def play(self):
        if self.sound is not None:
            self.sound.play()
            self.seek(self.current_position)

    def pause(self):
        """
        kivy audio does not enable pausing, instead the current position
        is recorded when the audio is stopped.
        """
        if self.sound is not None:
            if self.sound.state == 'play':
                self.mode_stop = True
                self.current_position = self.position()
                self.sound.stop()

    #def stop(self):
    #    if self.sound is not None:
    #        self.sound.stop()

    def seek(self,pos):
        if self.sound is not None:
            self.sound.seek(pos)

    def position(self):
        """ return current position in seconds (float)"""
        if self.sound is not None:
            return self.sound.get_pos()
        return 0.0

    def setVolume(self,volume):
        if self.sound is not None:
            self.volume = volume
            self.sound.volume = volume

    def playpause(self):
        """ toggle state of audio
        """
        if self.sound is not None:
            if self.sound.state == 'play':
                self.pause()
            else:
                self.play()

    def on_play(self,*args):
        print("play")

    def on_stop(self,*args):
        # if mode stop is True, stop was issued by a user 'pause'
        # otherwise stop was automatic 'end-of-file'
        if self.mode_stop:
            print("stop by user")
            self.mode_stop = False
        else:
            print("end of file")


