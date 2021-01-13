from collections import defaultdict
import curses

from ..observable import Observable


_attr_to_callbacks = defaultdict(list)
def bind_to(*attrs):
    """Decorator that binds a method to attributes.
    """
    def decorator(func):
        for attr in attrs:
            _attr_to_callbacks[attr].append(func.__name__)
        return func
    return decorator


class Observer(type):
    def __prepare__(name, bases):
        _attr_to_callbacks.clear()
        return {"bind_to": bind_to}

    def __new__(meta, name, bases, methods):
        del methods["bind_to"]

        # Attributes bound to callbacks that aren't `Observable` are made so:
        for attr, callbacks in _attr_to_callbacks.items():
            if attr not in methods:
                for base in bases:
                    if attr in base.__dict__:
                        if not isinstance(base.__dict__[attr], Observable):
                            prop = methods[attr] = Observable(base.__dict__[attr])
                        else:
                            prop = base.__dict__[attr]
                        break
                else:
                    prop = methods[attr] = Observable()
            elif not isinstance(methods[attr], Observable):
                prop = methods[attr] = Observable(methods[attr])
            else:
                prop = methods[attr]

            for callback in callbacks:
                prop.bind(name, callback)

        _attr_to_callbacks.clear()

        return super().__new__(meta, name, bases, methods)


class Widget(metaclass=Observer):
    """
    The base window for nurses.  A fancy wrapper around a curses window.

    Parameters
    ----------
    top, left, height, width: optional
        Upper and left-most coordinates of widget relative to parent, and dimensions of the widget. Fractional arguments
        are interpreted as percentage of parent, and parent width or height will be added to negative arguments.
        (the defaults are 0, 0, parent's max height, parent's max width)
    color: optional
       A curses color_pair, the default color of this widget. (the default is `curses.color_pair(0)`)

    Other Parameters
    ----------------
    transparent: optional
        If true, widget will overlay other widgets instead of overwrite them (whitespace will be "see-through"). (the default is `False`)

    Notes
    -----
    Coordinates are (y, x) (both a curses and a numpy convention) with y being vertical and increasing as you move down
    and x being horizontal and increasing as you move right.  Top-left corner is (0, 0)

    If some part of the widget moves out-of-bounds of the screen only the part that overlaps the screen will be drawn.

    Currently widget size is limited by screen size.
    """
    types = { }  # Registry of subclasses of Widget

    def __init_subclass__(cls):
        Widget.types[cls.__name__] = cls

        if not cls.on_press.__doc__:
            cls.on_press.__doc__ = Widget.on_press.__doc__

    def __init__(self, *args, pos_hint=(None, None), size_hint=(None, None), color=0, parent=None, transparent=False, **kwargs):
        self.children = [ ]
        self.group = defaultdict(list)
        self.window = None

        self.parent = parent
        self.is_transparent = transparent
        self.color = color

        top, left, height, width, *rest = args + (None, None) if len(args) == 2 else args or (0, 0, None, None)
        self.top = top
        self.left = left
        self.height = height
        self.width = width
        self.pos_hint = pos_hint
        self.size_hint = size_hint

        for attr in tuple(kwargs):
            # This allows one to set class attributes with keyword-arguments. TODO: Document this.
            if hasattr(self, attr):
                setattr(self, attr, kwargs.pop(attr))

        super().__init__(*rest, **kwargs)

    bind_to("top")
    def _set_pos_hint_y(self):
        self.pos_hint = None, self.pos_hint[1]

    bind_to("left")
    def _set_pos_hint_x(self):
        self.pos_hint = self.pos_hint[0], None

    bind_to("height")
    def _set_size_hint_y(self):
        self.size_hint = None, self.size_hint[1]

    bind_to("width")
    def _set_size_hint_x(self):
        self.size_hint = self.size_hint[0], None

    def update_geometry(self):
        """Set or reset the widget's geometry based on size or pos hints if they exist.
        """
        if not self.has_root:
            return

        h, w = self.parent.height, self.parent.width

        top, left = self.pos_hint

        if top is not None:
            self.top = self.convert(top, h)

        if left is not None:
            self.left = self.convert(left, w)

        self.pos_hint = top, left

        height, width = self.size_hint

        if height is not None:
            self.height = self.convert(height, h)
        if width is not None:
            self.width = self.convert(width, w)

        if self.height is None:
            self.height = h
        if self.width is None:
            self.width = w - 1

        self.size_hint = height, width

        if self.window is None:
            self.window = curses.newwin(self.height, self.width + 1)
        else:
            self.window.resize(self.height, self.width + 1)
        self.update_color(self.color)

        for child in self.children:
            child.update_geometry()

    @property
    def bottom(self):
        return self.top + self.height

    @property
    def right(self):
        return self.left + self.width

    @property
    def has_root(self):
        if self.parent is None:
            return False
        return self.parent.has_root

    @property
    def root(self):
        if self.parent is None:
            return None
        return self.parent.root

    def walk(self, start=None):
        if start is None:
            start = self.root

        for child in start.children:
            yield from self.walk(child)
        yield start

    @property
    def is_in_front(self):
        return self.parent and self.parent.children[-1] is self

    @property
    def is_in_back(self):
        return self.parent and self.parent.children[0] is self

    def pull_to_front(self, widget):
        """Given a widget or an index of a widget, widget is moved to top of widget stack (so it is drawn last).
        """
        widgets = self.children
        if isinstance(widget, int):
            widgets.append(widgets.pop(widget))
        else:
            widgets.remove(widget)
            widgets.append(widget)

    def push_to_back(self, widget):
        """Given a widget or an index of a widget, widget is moved to bottom of widget stack (so it is drawn first).
        """
        widgets = self.children
        if isinstance(widget, int):
            widgets.insert(0, widgets.pop(widget))
        else:
            widgets.remove(widget)
            widgets.insert(0, widget)

    def add_widget(self, widget):
        self.children.append(widget)
        widget.parent = self
        widget.update_geometry()

    def new_widget(self, *args, group=None, create_with=None, **kwargs):
        """
        Create a new widget and append to widget stack.  Can group widgets if providing a hashable group.
        To create a new subclassed widget use `create_with=MyWidget` or `create_with="MyWidget"` (pass the class or the class' name).
        """
        if create_with is None:
            create_with = Widget
        elif isinstance(create_with, str):
            create_with = Widget.types[create_with]

        widget = create_with(*args, parent=self, **kwargs)

        self.add_widget(widget)
        if group is not None:
            self.group[group].append(widget)

        return widget

    @property
    def overlay(self):
        return self.window.overlay if self.is_transparent else self.window.overwrite

    def refresh(self):
        """Redraw children's windows.
        """
        # Notably, we don't use curses.panels as they aren't available for windows-curses...
        # ...upside is we don't error when moving a widget off-screen.
        h, w = self.height, self.width
        for widget in self.children:
            widget.refresh()
            y, x = widget.top, widget.left
            src_t, des_t = (-y, 0) if y < 0 else (0, y)
            src_l, des_l = (-x, 0) if x < 0 else (0, x)
            des_h = min(h - 1, des_t + widget.height)
            des_w = min(w - 1, des_l + widget.width - 1)  # -1 compensates for the extra width of widget's window

            widget.overlay(self.window, src_t, src_l, des_t, des_l, des_h, des_w)

    @staticmethod
    def convert(pos, bounds):
        """Utility function that converts a fractional or negative position to an absolute one.
        """
        if isinstance(pos, float):
            pos = round(pos * bounds)
        return pos + bounds if pos < 0 else pos

    def dispatch(self, key):
        for widget in reversed(self.children):
            if widget.on_press(key) or widget.dispatch(key):
                return True

    def on_press(self, key):
        """
        Called when a key is pressed and no widgets above this widget have handled the press.
        A press is handled when a widget's `on_press` method returns True.
        """
        try:
            return super().on_press(key)
        except AttributeError:
            pass

    def update_color(self, color):
        self.color = color
        self.window.attrset(color)
