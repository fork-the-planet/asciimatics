"""This module implements the widget for a multiple column list box"""
from __future__ import annotations
from re import match as re_match
from itertools import zip_longest
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union
from asciimatics.strings import ColouredText
from asciimatics.widgets.utilities import _enforce_width_ext
from asciimatics.widgets.baselistbox import _BaseListBox
if TYPE_CHECKING:
    from asciimatics.parsers import Parser


class MultiColumnListBox(_BaseListBox):
    """
    A MultiColumnListBox is a widget for displaying tabular data.

    It displays a list of related data in columns, from which the user can select a line.
    """

    def __init__(self,
                 height: int,
                 columns: List[Union[int, str]],
                 options: List[Tuple[List[str], int]],
                 titles: Optional[List[str]] = None,
                 label: Optional[str] = None,
                 name: Optional[str] = None,
                 add_scroll_bar: bool = False,
                 parser: Optional[Parser] = None,
                 on_change: Optional[Callable] = None,
                 on_select: Optional[Callable] = None,
                 space_delimiter: str = ' '):
        """
        :param height: The required number of input lines for this ListBox.
        :param columns: A list of widths and alignments for each column.
        :param options: The options for each row in the widget.
        :param titles: Optional list of titles for each column.  Must match the length of
            `columns`.
        :param label: An optional label for the widget.
        :param name: The name for the ListBox.
        :param add_scroll_bar: Whether to add optional scrollbar for large lists.
        :param parser: Optional parser to colour options and titles text.
        :param on_change: Optional function to call when selection changes.
        :param on_select: Optional function to call when the user actually selects an entry from
        :param space_delimiter: Optional parameter to define the delimiter between columns.
            The default value is blank space.

        The `columns` parameter is a list of integers or strings.  If it is an integer, this is
        the absolute width of the column in characters.  If it is a string, it must be of the
        format "[<align>]<width>[%]" where:

        * <align> is the alignment string ("<" = left, ">" = right, "^" = centre)
        * <width> is the width in characters
        * % is an optional qualifier that says the number is a percentage of the width of the
          widget.

        Column widths need to encompass any space required between columns, so for example, if
        your column is 5 characters, allow 6 for an extra space at the end.  It is not possible
        to do this when you have a right-justified column next to a left-justified column, so
        this widget will automatically space them for you.

        An integer value of 0 is interpreted to be use whatever space is left available after the
        rest of the columns have been calculated.  There must be only one of these columns.

        The number of columns is for this widget is determined from the number of entries in the
        `columns` parameter.  The `options` list is then a list of tuples of the form
        ([val1, val2, ... , valn], index).  For example, this data provides 2 rows for a 3 column
        widget:

            options=[(["One", "row", "here"], 1), (["Second", "row", "here"], 2)]

        The options list may be None and then can be set later using the `options` property on
        this widget.
        """
        if titles is not None and parser is not None:
            new_titles: Optional[List[Union[ColouredText, str]]] = [ColouredText(x, parser) for x in titles]
        else:
            new_titles = list(titles) if titles else None
        super().__init__(height,
                         options,
                         titles=new_titles,
                         label=label,
                         name=name,
                         parser=parser,
                         on_change=on_change,
                         on_select=on_select)
        self._columns: list[Union[int, float]] = []
        self._align = []
        self._spacing = []
        self._add_scroll_bar = add_scroll_bar
        self._space_delimiter = space_delimiter
        for i, column in enumerate(columns):
            if isinstance(column, int):
                self._columns.append(column)
                self._align.append("<")
            else:
                match = re_match(r"([<>^]?)(\d+)([%]?)", column)
                assert match
                self._columns.append(float(match.group(2)) / 100 if match.group(3) else int(match.group(2)))
                self._align.append(match.group(1) if match.group(1) else "<")
            if space_delimiter == ' ':
                self._spacing.append(1 if i > 0 and self._align[i] == "<" and self._align[i -
                                                                                          1] == ">" else 0)
            else:
                self._spacing.append(1 if i > 0 else 0)

    def _get_width(self, width: Union[float, int], max_width: int) -> int:
        """
        Helper function to figure out the actual column width from the various options.

        :param width: The size of column requested
        :param max_width: The maximum width allowed for this widget.
        :return: the integer width of the column in characters
        """
        if isinstance(width, float):
            return int(max_width * width)
        if width == 0:
            width = (max_width - sum(self._spacing) -
                     sum(self._get_width(x, max_width) for x in self._columns if x != 0))
        return width

    def _print_cell(self,
                    space: int,
                    text: Union[ColouredText, str],
                    align: str,
                    width: int,
                    x: int,
                    y: int,
                    foreground: Optional[int],
                    attr: Optional[int],
                    background: Optional[int]):
        # Sort out spacing first.
        assert self._frame
        if space:
            self._frame.canvas.print_at(self._space_delimiter * space, x, y, foreground, attr, background)

        # Now align text, taking into account double space glyphs.
        paint_text = text
        if self.string_len(str(text)) > width:
            paint_text, truncated = _enforce_width_ext(
                text[self._start_char:], width, self._frame.canvas.unicode_aware)
            if truncated:
                paint_text = paint_text[:-3] + "..."

        text_size = self.string_len(str(paint_text))
        if text_size < width:
            # Default does no alignment or padding.
            buffer_1 = buffer_2 = ""
            if align == "<":
                buffer_2 = " " * (width - text_size)
            elif align == ">":
                buffer_1 = " " * (width - text_size)
            elif align == "^":
                start_len = int((width - text_size) / 2)
                buffer_1 = " " * start_len
                buffer_2 = " " * (width - text_size - start_len)
            paint_text = paint_text.join([buffer_1, buffer_2])
        self._frame.canvas.paint(
            str(paint_text),
            x + space,
            y,
            foreground,
            attr,
            background,
            colour_map=paint_text.colour_map if hasattr(paint_text, "colour_map") else None)

    def update(self, frame_no: int):
        self._draw_label()

        # Calculate new visible limits if needed.
        height = self._h
        width = self._w
        delta_y = 0

        # Clear out the existing box content
        assert self._frame
        (colour, attr, background) = self._frame.palette["field"]
        for i in range(height):
            self._frame.canvas.print_at(" " * width,
                                        self._x + self._offset,
                                        self._y + i + delta_y,
                                        colour,
                                        attr,
                                        background)

        # Allow space for titles if needed.
        if self._titles:
            delta_y += 1
            height -= 1

        # Decide whether we need to show or hide the scroll bar and adjust width accordingly.
        if self._add_scroll_bar:
            self._add_or_remove_scrollbar(width, height, delta_y)
        if self._scroll_bar:
            width -= 1

        # Now draw the titles if needed.
        if self._titles:
            row_dx = 0
            colour, attr, background = self._frame.palette["title"]
            for i, [title, align, space] in enumerate(zip(self._titles, self._align, self._spacing)):
                assert isinstance(title, (str, ColouredText))
                cell_width = self._get_width(self._columns[i], width)
                self._print_cell(space,
                                 title,
                                 align,
                                 cell_width,
                                 self._x + self._offset + row_dx,
                                 self._y,
                                 colour,
                                 attr,
                                 background)
                row_dx += cell_width + space

        # Don't bother with anything else if there are no options to render.
        if len(self._options) <= 0:
            return

        # Render visible portion of the text.
        self._start_line = max(0, self._line - height + 1, min(self._start_line, self._line))
        for i, [row, _] in enumerate(self._options):
            if self._start_line <= i < self._start_line + height:
                colour, attr, background = self._pick_colours("field", i == self._line)
                row_dx = 0
                # Try to handle badly formatted data, where row lists don't
                # match the expected number of columns.
                for text, cell_width2, align2, space2 in zip_longest(
                        row, self._columns, self._align, self._spacing, fillvalue=""):
                    if cell_width2 == "":
                        break
                    assert isinstance(cell_width2, (int, float))
                    assert isinstance(space2, int)
                    cell_width = self._get_width(cell_width2, width)
                    self._print_cell(space2,
                                     text,
                                     align2,
                                     cell_width,
                                     self._x + self._offset + row_dx,
                                     self._y + i + delta_y - self._start_line,
                                     colour,
                                     attr,
                                     background)
                    row_dx += cell_width + space2

        # And finally draw any scroll bar.
        if self._scroll_bar:
            self._scroll_bar.update()

    def _find_option(self, search_value: str) -> Optional[int]:
        for row, value in self._options:
            # TODO: Should this be aware of a sort column?
            if row[0].startswith(search_value):
                return value
        return None

    def _max_len(self) -> int:
        """
        Max length of any entry in the options.
        """
        return max(max(len(y) for y in x[0]) for x in self._options)

    def _parse_option(self, option: List[str]) -> List[ColouredText]:
        """
        Parse a single option for ColouredText.

        :param option: the option to parse
        :returns: the option parsed and converted to ColouredText.
        """
        assert self._parser
        option_items = []
        for item in option:
            try:
                value = ColouredText(item.raw_text, self._parser)  # type: ignore
            except AttributeError:
                value = ColouredText(item, self._parser)
            option_items.append(value)
        return option_items

    @property
    def options(self):
        """
        The list of options available for user selection

        This is a list of tuples ([<col 1 string>, ..., <col n string>], <internal value>).
        """
        return self._options

    @options.setter
    def options(self, new_value):
        # Set net list of options and then force an update to the current value to align with the new options.
        self._options = self._parse_options(new_value)
        self.value = self._value
