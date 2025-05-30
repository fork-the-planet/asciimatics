"""This module implements a base class for popups"""
from __future__ import annotations
from collections import defaultdict
from abc import abstractmethod
from typing import TYPE_CHECKING, Optional
from asciimatics.event import KeyboardEvent, MouseEvent, Event
from asciimatics.exceptions import InvalidFields
from asciimatics.screen import Screen
from asciimatics.widgets.frame import Frame
if TYPE_CHECKING:
    from asciimatics.widgets.widget import Widget


class _TempPopup(Frame):
    """
    An internal Frame for creating a temporary pop-up for a Widget in another Frame.
    """

    def __init__(self, screen: Screen, parent: Widget, x: int, y: int, w: int, h: int):
        """
        :param screen: The Screen being used for this pop-up.
        :param parent: The widget that spawned this pop-up.
        :param x: The X coordinate for the desired pop-up.
        :param y: The Y coordinate for the desired pop-up.
        :param w: The width of the desired pop-up.
        :param h: The height of the desired pop-up.
        """
        # Construct the Frame
        super().__init__(screen, h, w, x=x, y=y, has_border=True, can_scroll=False, is_modal=True)

        # Set up the new palette for this Frame
        assert parent.frame
        self.palette = defaultdict(lambda: parent.frame.palette["focus_field"])  # type: ignore
        self.palette["selected_field"] = parent.frame.palette["selected_field"]
        self.palette["selected_focus_field"] = parent.frame.palette["selected_focus_field"]
        self.palette["invalid"] = parent.frame.palette["invalid"]

        # Internal state for the pop-up
        self._parent = parent

    def process_event(self, event: Optional[Event]) -> Optional[Event]:
        # Look for events that will close the pop-up - e.g. clicking outside the Frame or Enter key.
        cancelled = False
        if event is not None:
            if isinstance(event, KeyboardEvent):
                if event.key_code in [Screen.ctrl("M"), Screen.ctrl("J"), ord(" ")]:
                    event = None
                elif event.key_code == Screen.KEY_ESCAPE:
                    event = None
                    cancelled = True
            elif isinstance(event, MouseEvent) and event.buttons != 0:
                if self._outside_frame(event):
                    event = None

        # Remove this pop-up if we're done; otherwise bubble up the event.
        if event is None:
            try:
                self.close(cancelled)
            except InvalidFields:
                # Nothing to do as we've already prevented the Effect from being removed.
                pass
        return super().process_event(event)

    def close(self, cancelled: bool = False):
        """
        Close this temporary pop-up.

        :param cancelled: Whether the pop-up was cancelled (e.g. by pressing Esc).
        """
        assert self._scene
        self._on_close(cancelled)
        self._scene.remove_effect(self)

    @abstractmethod
    def _on_close(self, cancelled):
        """
        Method to handle any communication back to the parent widget on closure of this pop-up.

        :param cancelled: Whether the pop-up was cancelled (e.g. by pressing Esc).

        This method can raise an InvalidFields exception to indicate that the current selection is
        invalid and so the pop-up cannot be dismissed.
        """
