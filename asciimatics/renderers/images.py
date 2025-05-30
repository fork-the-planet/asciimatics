"""
This module implements renderers that produce content based on image files.
"""

from PIL import Image, ImageSequence
from asciimatics.renderers.base import StaticRenderer
from asciimatics.screen import Screen


class ImageFile(StaticRenderer):
    """
    Renderer to convert an image file (as supported by the Python Imaging
    Library) into an ascii grey scale text image.
    """

    # The ASCII grey scale from darkest to lightest.
    _greyscale = ' .:;rsA23hHG#9&@'

    def __init__(self, filename: str, height: int = 30, colours: int = 8):
        """
        :param filename: The name of the file to render.
        :param height: The height of the text rendered image.
        :param colours: The number of colours the terminal supports.
        """
        super().__init__()
        with Image.open(filename) as image:
            background = image.info['background'] if 'background' in image.info else None
            for frame in ImageSequence.Iterator(image):
                ascii_image = ""
                frame = frame.resize((int(frame.size[0] * height * 2.0 / frame.size[1]), height),
                                     Image.Resampling.BICUBIC)
                grey_frame = frame.convert('L')
                for py in range(0, grey_frame.size[1]):
                    if py > 0:
                        ascii_image += "\n"
                    for px in range(0, grey_frame.size[0]):
                        real_col = frame.getpixel((px, py))
                        col = grey_frame.getpixel((px, py))
                        if real_col == background:
                            ascii_image += " "
                        else:
                            assert isinstance(col, int)
                            if colours >= 256:
                                ascii_image += "${%d}" % (232 + col * 23 // 256)
                            else:
                                ascii_image += "${%d,%d}" % (7 if col >= 85 else 0,
                                                             Screen.A_BOLD
                                                             if col < 85 or col > 170 else Screen.A_NORMAL)
                            ascii_image += self._greyscale[(int(col) * len(self._greyscale)) // 256]
                self._images.append(ascii_image)


class ColourImageFile(StaticRenderer):
    """
    Renderer to convert an image file (as supported by the Python Imaging
    Library) into an block image of available colours.

    .. warning::

        This is only compatible with 256-colour terminals.  Results in other
        terminals with reduced colour capabilities are severely restricted.
        Since Windows only has 8 base colours, it is recommended that you
        avoid this renderer on that platform.
    """

    def __init__(self,
                 screen: Screen,
                 filename: str,
                 height: int = 30,
                 bg: int = Screen.COLOUR_BLACK,
                 fill_background: bool = False,
                 uni: bool = False,
                 dither: bool = False):
        """
        :param screen: The screen to use when displaying the image.
        :param filename: The name of the file to render.
        :param height: The height of the text rendered image.
        :param bg: The default background colour for this image.
        :param fill_background: Whether to set background colours too.
        :param uni: Whether to use unicode box characters or not.
        :param dither: Whether to dither the rendered image or not.
        """
        super().__init__()
        with Image.open(filename) as image:
            # Create temp Image with web palette for quantization.
            tmp_img = Image.new("P", (1, 1))
            tmp_img.putpalette(screen.palette)

            # Convert each frame in the image.
            for frame in ImageSequence.Iterator(image):
                ascii_image = ""

                # Resize to the required size and standardize on RGBA to detect transparency.
                new_frame = frame.resize(
                    (int(frame.size[0] * height * 2.0 / frame.size[1]), height * 2 if uni else height),
                    Image.Resampling.BICUBIC)
                new_frame = new_frame.convert('RGBA')

                # Convert to terminal 256 colour palette.
                new_frame2 = new_frame.convert('RGB')
                new_frame2 = new_frame2.quantize(
                    colors=256,
                    palette=tmp_img,
                    dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)

                # Decide what "brush" we're going to use for the rendering.
                brush = "▄" if uni else "#"

                # Convert the resulting image to coloured ASCII codes.
                for py in range(0, new_frame2.size[1], 2 if uni else 1):
                    # Looks like some terminals need a character printed before
                    # they really reset the colours - so insert a dummy char
                    # to reset the background if needed.
                    if py > 0:
                        if uni:
                            ascii_image += "${%d,2,%d}." % (bg, bg)
                        ascii_image += "\n"
                    for px in range(0, new_frame2.size[0]):
                        real_col = new_frame.getpixel((px, py))
                        real_col2 = new_frame.getpixel((px, py + 1)) if uni else real_col
                        assert isinstance(real_col, tuple)
                        assert isinstance(real_col2, tuple)
                        col = new_frame2.getpixel((px, py))
                        col2 = new_frame2.getpixel((px, py + 1)) if uni else col
                        assert isinstance(col, int)
                        assert isinstance(col2, int)
                        if (real_col[3] < 64 and real_col2[3] < 64):
                            if fill_background or uni:
                                ascii_image += "${%d,2,%d}." % (bg, bg)
                            else:
                                ascii_image += "${%d} " % bg
                        else:
                            if fill_background or uni:
                                ascii_image += "${%d,2,%d}%s" % (col2, col, brush)
                            else:
                                ascii_image += "${%d}#" % col
                if uni:
                    ascii_image += "${%d,2,%d}." % (bg, bg)
                self._images.append(ascii_image)
