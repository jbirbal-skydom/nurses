import curses

from . import screen as scr
import numpy as np


class Widget:  # TODO:  Widget will inherit from EventListener as soon as we have one.
    """Widget class contains a buffer that can be pushed to the screen by calling `refresh`.  __getitem__ and __setitem__ call the respective
       buffer functions directly, so one can slice and write to a Widget as if it was a numpy array.
        ::args::
            top:                     upper coordinate of widget relative to screen
            left:                    left coordinate of widget relative to screen
            height:                  height of the widget
            width:                   width of the widget
            color_pair (optional):   a curses color_pair.  Default color of this widget.

        ::kwargs::
            transparency (optional): a boolean mask that indicates which cells in the buffer to write
            colors (optional):       an array of curses.color_pairs that indicate what color each cell in the buffer should be

        ::Note::
            If some part of the widget moves out-of-bounds of the screen only the part that overlaps the screen will be drawn.

            Coordinates are (y, x) (both a curses and a numpy convention) with y being vertical and increasing as you move down
            and x being horizontal and increasing as you move right.  Top-left corner is (0, 0)
    """
    def __init__(self, top, left, height, width, color_pair=None, **kwargs):
        self.sm = scr.ScreenManager()
        self.top = top
        self.left = left
        self.height = height
        self.width = width

        self.buffer = np.full((height, width), " ")

        if (colors := kwargs.get("colors")) is None:
            if color_pair is None:
                color_pair = self.sm.color(1)
            self.colors = np.full((height, width), color_pair)
        else:
            self.colors = colors

        if (transparency := kwargs.get("transparency")) is None:
            self.transparency = np.zeros_like(self.buffer, dtype=bool)
        else:
            self.transparency = transparency

        self.window = None

    @property
    def top(self):
        return self._top

    @top.setter
    def top(self, val):
        self._top = val
        self.has_moved = True

    @property
    def left(self):
        return self._left

    @left.setter
    def left(self, val):
        self._left = val
        self.has_moved = True

    @property
    def ul(self):
        return self.top, self.left

    @ul.setter
    def ul(self, val):
        self.top, self.left = val

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, val):
        self._height = val
        self.has_resized = True

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, val):
        self._width = val
        self.has_resized = True

    @property
    def bounds(self):
        scr_hgt, scr_wth = self.sm.screen.getmaxyx()
        height, width = self.height, self.width
        y, x = self.top, self.left

        scr_t = max(0, y)
        scr_l = max(0, x)
        win_t = max(0, -y)
        win_l = max(0, -x)
        h = min(scr_hgt - scr_t, y + height)
        w = min(scr_wth - scr_l - 1, x + width)

        return scr_t, scr_l, win_t, win_l, h, w

    def refresh(self):
        scr_t, scr_l, win_t, win_l, h, w = self.bounds

        if h <= 0 or w <= 0:
            return  # Widget is off screen or otherwise not-displayable.

        bounds = slice(win_t, win_t + h), slice(win_l, win_l + w)

        window = self.window
        if self.has_moved or self.has_resized:
            self.has_moved = self.has_resized = False
            if window is not None:
                window.erase()    # TODO: This needs to be bit more sophisticated:
                window.refresh()  # If another widget has already written to this area, then we don't need to erase it.
            self.window = window = curses.newwin(h, w + 1, scr_t, scr_l)
        window.erase()

        it = np.nditer((self.transparency[bounds], self.buffer[bounds], self.colors[bounds]), ["multi_index"])
        for trans, pix, color in it:
            if trans: continue
            y, x = it.multi_index
            window.addstr(y, x, str(pix), color)
        window.refresh()

    def __getitem__(self, key):
        return self.buffer[key]

    def __setitem__(self, key, item):
        """Mirrors np.array __setitem__ except in cases where item is a string.
           In that case, we'll break the string into a tuple or tuple of tuples.
           This convenience will allow one to update text on a widget more directly:
                my_widget[2:4, :13] = "Hello, World!\nI'm a widget!"
        """
        if isinstance(item, str):
            if "\n" in item:
                item = np.array(tuple(map(tuple, item.splitlines())))
                if item.shape != self[key].shape:
                    # Attempt to fit the text by making it vertical.
                    item = item.T
            elif len(item) > 1:
                item = tuple(item)

        self.buffer[key] = item

    def border(self, style="light", color=None):
        """Draw a border on the edges of the widget.
           style can be one of ["light", "heavy", "double", "curved"]
        """
        styles = {
            "light": "┌┐│─└┘",
            "heavy": "┏┓┃━┗┛",
            "double": "╔╗║═╚╝",
            "curved": "╭╮│─╰╯"
        }

        ul, ur, v, h, ll, lr = styles[style]

        self[0] = h
        self[-1] = h
        self[:, 0] = v
        self[:, -1] = v
        self[0, 0] = ul
        self[0, -1] = ur
        self[-1, 0] = ll
        self[-1, -1] = lr

        if color is not None:
            c = self.colors
            c[0] = c[-1] = c[:, 0] = c[:, -1] = color
