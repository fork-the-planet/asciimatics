"""This module defines a dropdown list widget"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
from wcwidth import wcswidth
from asciimatics.event import KeyboardEvent, MouseEvent, Event
from asciimatics.screen import Screen
from asciimatics.widgets.divider import Divider
from asciimatics.widgets.layout import Layout
from asciimatics.widgets.listbox import ListBox
from asciimatics.widgets.temppopup import _TempPopup
from asciimatics.widgets.text import Text
from asciimatics.widgets.utilities import _enforce_width
from asciimatics.widgets.widget import Widget
if TYPE_CHECKING:
    from asciimatics.effects import Effect


class _DropdownPopup(_TempPopup):
    """
    An internal Frame for selecting an item from a drop-down list..
    """

    def __init__(self, parent: "DropdownList"):
        """
        :param parent: The widget that spawned this pop-up.
        """
        # Decide which way to present the list - up or down from the parent widget.
        assert parent.frame
        location = parent.get_location()
        if parent.frame.screen.height - location[1] < 3:
            height = min(len(parent.options) + 4, location[1] + 2)
            start_line = location[1] - height + 2
            reverse = True
        else:
            start_line = location[1] - 1
            height = min(len(parent.options) + 4, parent.frame.screen.height - location[1] + 1)
            reverse = False

        if parent.fit:
            width = min(max(map(lambda x: wcswidth(x[0]), parent.options)) + 4, parent.width)
        else:
            width = parent.width
        # Construct the Frame
        super().__init__(parent.frame.screen, parent, location[0], start_line, width, height)

        # Build the widget to display the time selection.
        layout = Layout([1], fill_frame=True)
        self.add_layout(layout)
        self._field = Text()
        self._field.disabled = True
        divider = Divider()
        divider.disabled = True
        self._list = ListBox(Widget.FILL_FRAME, [(f" {i[0]}", i[1]) for i in parent.options],
                             add_scroll_bar=len(parent.options) > height - 4,
                             on_select=self.close,
                             on_change=self._link)
        layout.add_widget(self._list if reverse else self._field, 0)
        layout.add_widget(divider, 0)
        layout.add_widget(self._field if reverse else self._list, 0)
        self.fix()

        # Set up the correct time.
        self._list.value = parent.value

    def _link(self):
        # pylint: disable=protected-access
        self._field.value = self._list.options[self._list._line][0]

    def _on_close(self, cancelled: bool):
        if not cancelled:
            self._parent.value = self._list.value


class DropdownList(Widget):
    """
    This widget allows you to pick an item from a temporary pop-up list.
    """

    __slots__ = ["_on_change", "_child", "_options", "_line", "_fit"]

    def __init__(self,
                 options: List[Tuple[str, int]],
                 label: Optional[str] = None,
                 name: Optional[str] = None,
                 on_change: Optional[Callable] = None,
                 fit: Optional[bool] = None,
                 **kwargs):
        """
        :param options: The options for each row in the widget.
        :param label: An optional label for the widget.
        :param name: The name for the widget.
        :param on_change: Optional function to call when the selected time changes.
        :param fit: Shrink width of dropdown to fit the width of options. Default False.

        The `options` are a list of tuples, where the first value is the string to be displayed
        to the user and the second is an interval value to identify the entry to the program.
        For example:

            options=[("First option", 1), ("Second option", 2)]

        Also see the common keyword arguments in :py:obj:`.Widget`.
        """
        super().__init__(name, **kwargs)
        self._label = label
        self._on_change = on_change
        self._child: Optional[Effect] = None
        self._options = options
        self._line = 0 if len(options) > 0 else None
        self._value = options[self._line][1] if self._line is not None else None
        self._fit = fit

    @property
    def options(self):
        """
        The set of allowed options for the drop-down list.
        """
        return self._options

    @options.setter
    def options(self, new_value):
        self._options = new_value
        self.value = self._value

    @property
    def fit(self) -> Optional[bool]:
        """
        Whether to shrink to largest element width or not.
        """
        return self._fit

    def update(self, frame_no: int):
        self._draw_label()

        # This widget only ever needs display the current selection - the separate Frame does all
        # the clever stuff when it has the focus.
        text = "" if self._line is None else self._options[self._line][0]
        (colour, attr, background) = self._pick_colours("field", selected=self._has_focus)
        if self._fit:
            width = min(max(map(lambda x: wcswidth(x[0]), self._options)) + 1, self.width - 3)
        else:
            width = self.width - 3

        # For unicode output, we need to adjust for any double width characters.
        assert self._frame
        output = _enforce_width(text, width, self._frame.canvas.unicode_aware)
        output_tweak = wcswidth(output) - len(output)

        self._frame.canvas.print_at(f"[ {output:{width - output_tweak}}]",
                                    self._x + self._offset,
                                    self._y,
                                    colour,
                                    attr,
                                    background)

    def reset(self):
        pass

    def process_event(self, event: Optional[Event]) -> Optional[Event]:
        if event is not None:
            if isinstance(event, KeyboardEvent):
                if event.key_code in [Screen.ctrl("M"), Screen.ctrl("J"), ord(" ")]:
                    event = None
            elif isinstance(event, MouseEvent):
                if event.buttons != 0:
                    if self.is_mouse_over(event, include_label=False):
                        event = None
            if event is None:
                self._child = _DropdownPopup(self)
                assert self.frame and self.frame.scene
                self.frame.scene.add_effect(self._child)

        return event

    def required_height(self, offset: int, width: int):
        return 1

    @property
    def value(self):
        """
        The current value for this DropdownList.
        """
        return self._value

    @value.setter
    def value(self, new_value):
        # Only trigger change notification after we've changed selection
        old_value = self._value
        self._value = new_value
        for i, [_, value] in enumerate(self._options):
            if value == new_value:
                self._line = i
                break
        else:
            self._value = self._line = None
        if old_value != self._value and self._on_change:
            self._on_change()
