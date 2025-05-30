"""
This module implements renderers that play content to the screen.
"""
from abc import abstractmethod
import json
from io import BufferedReader
from typing import List, Optional, Tuple, Iterable
from types import TracebackType
from asciimatics.renderers.base import DynamicRenderer
from asciimatics.screen import Screen
from asciimatics.parsers import AnsiTerminalParser, Parser


class AbstractScreenPlayer(DynamicRenderer):
    """
    Abstract renderer to play terminal text with support for ANSI control codes.
    """

    def __init__(self, file: BufferedReader, height: int, width: int):
        """
        :param height: required height of the renderer.
        :param width: required width of the renderer.
        """
        super().__init__(height, width, clear=False)
        self._file = file
        self._parser: Parser = AnsiTerminalParser()
        self._current_colours = [Screen.COLOUR_WHITE, Screen.A_NORMAL, Screen.COLOUR_BLACK]
        self._show_cursor = False
        self._cursor_x = 0
        self._cursor_y = 0
        self._save_cursor_x = 0
        self._save_cursor_y = 0
        self._counter = 0.0
        self._next = 0
        self._buffer: Optional[str] = None
        self.reset()

    def reset(self):
        self._parser = AnsiTerminalParser()
        self._current_colours = [Screen.COLOUR_WHITE, Screen.A_NORMAL, Screen.COLOUR_BLACK]
        self._show_cursor = False
        self._cursor_x = 0
        self._cursor_y = 0
        self._save_cursor_x = 0
        self._save_cursor_y = 0
        self._counter = 0.0
        self._next = 0
        self._buffer = None
        self._parser.reset("", self._current_colours)
        self._clear()
        self._file.seek(0)
        self._canvas.reset()

    def __enter__(self) -> "AbstractScreenPlayer":
        """
        Create context for use as a context manager.
        """
        return self

    def __exit__(self,
                 exc_type: Optional[type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]):
        """
        Clear up the resources for this context.
        """
        if self._file:
            self._file.close()

    def _render_all(
            self
    ) -> Iterable[Tuple[List[str], List[List[Tuple[Optional[int], Optional[int], Optional[int]]]]]]:
        return [self._render_now()]

    @abstractmethod
    def _render_now(self):
        """
        Render the next iteration.
        """

    def _play_content(self, text: str):
        """
        Process new raw text.

        :param text: the raw text to be processed.
        """
        lines = text.split("\n")
        for i, line in enumerate(lines):
            self._parser.append(line)
            for _, command, params in self._parser.parse():
                # logging.debug("Command: {} {}".format(command, params))
                if command == Parser.DISPLAY_TEXT:
                    # Just display the text...  allowing for line wrapping.
                    if self._cursor_x + len(params) >= self._canvas.width:
                        part_1 = params[:self._canvas.width - self._cursor_x]
                        part_2 = params[self._canvas.width - self._cursor_x:]
                        self._print_at(part_1, self._cursor_x, self._cursor_y)
                        self._print_at(part_2, 0, self._cursor_y + 1)
                        self._cursor_x = len(part_2)
                        self._cursor_y += 1
                        if self._cursor_y - self._canvas.start_line >= self._canvas.height:
                            self._canvas.scroll()
                    else:
                        self._print_at(params, self._cursor_x, self._cursor_y)
                        self._cursor_x += len(params)
                elif command == Parser.CHANGE_COLOURS:
                    # Change current text colours.
                    self._current_colours = params
                elif command == Parser.NEXT_TAB:
                    # Move to next tab stop - hard-coded to default of 8 characters.
                    self._cursor_x = (self._cursor_x // 8) * 8 + 8
                elif command == Parser.MOVE_RELATIVE:
                    # Move cursor relative to current position.
                    self._cursor_x += params[0]
                    self._cursor_y += params[1]
                    if self._cursor_y < self._canvas.start_line:
                        self._canvas.scroll(self._cursor_y - self._canvas.start_line)
                elif command == Parser.MOVE_ABSOLUTE:
                    # Move cursor relative to specified absolute position.
                    if params[0] is not None:
                        self._cursor_x = params[0]
                    if params[1] is not None:
                        self._cursor_y = params[1] + self._canvas.start_line
                elif command == Parser.DELETE_LINE:
                    # Delete some/all of the current line.
                    if params == 0:
                        self._print_at(" " * (self._canvas.width - self._cursor_x),
                                       self._cursor_x,
                                       self._cursor_y)
                    elif params == 1:
                        self._print_at(" " * self._cursor_x, 0, self._cursor_y)
                    elif params == 2:
                        self._print_at(" " * self._canvas.width, 0, self._cursor_y)
                elif command == Parser.DELETE_CHARS:
                    # Delete n characters under the cursor.
                    for x in range(self._cursor_x, self._canvas.width):
                        if x + params < self._canvas.width:
                            cell = self._canvas.get_from(x + params, self._cursor_y)
                        else:
                            cell = None
                        if cell is None:
                            cell = (ord(" "),
                                    self._current_colours[0],
                                    self._current_colours[1],
                                    self._current_colours[2])
                        self._canvas.print_at(chr(cell[0]),
                                              x,
                                              self._cursor_y,
                                              colour=cell[1],
                                              attr=cell[2],
                                              bg=cell[3])
                elif command == Parser.SHOW_CURSOR:
                    # Show/hide the cursor.
                    self._show_cursor = params
                elif command == Parser.SAVE_CURSOR:
                    # Save the cursor position.
                    self._save_cursor_x = self._cursor_x
                    self._save_cursor_y = self._cursor_y
                elif command == Parser.RESTORE_CURSOR:
                    # Restore the cursor position.
                    self._cursor_x = self._save_cursor_x
                    self._cursor_y = self._save_cursor_y
                elif command == Parser.CLEAR_SCREEN:
                    # Clear the screen.
                    self._canvas.clear_buffer(self._current_colours[0],
                                              self._current_colours[1],
                                              self._current_colours[2])
                    self._cursor_x = 0
                    self._cursor_y = self._canvas.start_line
            # Move to next line, scrolling buffer as needed.
            if i != len(lines) - 1:
                self._cursor_x = 0
                self._cursor_y += 1
                if self._cursor_y - self._canvas.start_line >= self._canvas.height:
                    self._canvas.scroll()

    def _print_at(self, text: str, x: int, y: int):
        """
        Helper function to simplify use of the renderer.
        """
        self._canvas.print_at(text,
                              x,
                              y,
                              colour=self._current_colours[0],
                              attr=self._current_colours[1],
                              bg=self._current_colours[2])


class AnsiArtPlayer(AbstractScreenPlayer):
    """
    Renderer to play ANSI art text files.

    In order to tidy up files, this must be used as a context manager (i.e. using `with`).
    """

    def __init__(self,
                 filename: str,
                 height: int = 25,
                 width: int = 80,
                 encoding: str = "cp437",
                 strip: bool = False,
                 rate: int = 2):
        """
        :param filename: the file containingi the ANSI art.
        :param height: required height of the renderer.
        :param width: required width of the renderer.
        :param encoding: text encoding ofnthe file.
        :param strip: whether to strip CRLF from the file content.
        :param rate: number of lines to render on each update.
        """
        # pylint: disable-next=consider-using-with
        super().__init__(open(filename, "rb"), height, width)
        self._strip = strip
        self._rate = rate
        self._encoding = encoding

    def _render_now(self) -> Tuple[List[str], List[List[Tuple[Optional[int], Optional[int], Optional[int]]]]]:
        count = 0
        line = None
        while count < self._rate and line != "":
            line = self._file.readline().decode(self._encoding)
            count += 1
            if self._strip:
                line = line.rstrip("\r\n")
            self._play_content(line)

        return self._plain_image, self._colour_map


class AsciinemaPlayer(AbstractScreenPlayer):
    """
    Renderer to play terminal recordings created by asciinema.

    This only supports the version 2 file format.  Use the max_delay setting to speed up human
    interactions (i.e. to reduce delays from typing).

    In order to tidy up files, this must be used as a context manager (i.e. using `with`).
    """

    def __init__(self,
                 filename: str,
                 height: Optional[int] = None,
                 width: Optional[int] = None,
                 max_delay: Optional[float] = None):
        """
        :param filename: the file containingi the ANSI art.
        :param height: required height of the renderer.
        :param width: required width of the renderer.
        :param max_delay: maximum time interval (in secs) to wait between frame updates.
        """
        # Open the file and check it looks plausibly like a supported format.
        # pylint: disable-next=consider-using-with
        f = open(filename, "rb")
        header = json.loads(f.readline())
        if header["version"] != 2:
            f.close()
            raise RuntimeError("Unsupported file format")

        # Use file details if not overridden by constructor params.
        height = height if height else header["height"]
        width = width if width else header["width"]

        # Construct the full player now we have all the details.
        super().__init__(f, height, width)
        self._max_delay = max_delay

    def _render_now(self) -> Tuple[List[str], List[List[Tuple[Optional[int], Optional[int], Optional[int]]]]]:
        self._counter += 0.05
        if self._counter >= self._next:
            if self._buffer:
                self._play_content(self._buffer)
                self._buffer = None
            while True:
                try:
                    self._next, _, self._buffer = json.loads(self._file.readline())
                    if self._next > self._counter:
                        # Speed up playback if requested.
                        if self._max_delay and self._next - self._counter > self._max_delay:
                            self._counter = self._next - self._max_delay
                        break
                    if self._buffer:
                        self._play_content(self._buffer)
                except ValueError:
                    # Python 3 raises a subclass of this error, so will also be caught.
                    break

        return self._plain_image, self._colour_map
