
"""

example of using clipping instructions in kivy

a red rectangle is drawn across the entire widget. Stencil instructions
are used to create a rectangle mask so that only a portion of
the rectangle is displayed

"""
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

#from kivy.graphics.scissor_instructions import ScissorPush,ScissorPop
from kivy.graphics.stencil_instructions import StencilPush,StencilUse, \
    StencilUnUse,StencilPop

# https://kivy.org/docs/api-kivy.graphics.stencil_instructions.html

class TestWidget(Widget):

    def __init__(self, **kwargs):
        super(TestWidget, self).__init__(**kwargs)

        with self.canvas.before:
            StencilPush()
            self.rect_mask = Rectangle() # see self.resize()
            StencilUse()

        with self.canvas:
            Color(.5,0,0,.5)
            self.rect_main = Rectangle(pos=(self.x,self.y),size=self.size)

        with self.canvas.after:
            StencilUnUse()
            StencilPop()

        self.bind(size=self.resize)

    def resize(self,*args):

        self.rect_mask.pos = (self.x + self.width//4,self.y)
        self.rect_mask.size = (self.width/2,self.height)

        self.rect_main.pos = self.pos
        self.rect_main.size = self.size

class TestApp(App):

    def build(self):
        return TestWidget()

def main():

    TestApp().run()

if __name__ == '__main__':
    main()