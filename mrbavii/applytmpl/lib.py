""" Template library functions for applytmpl. """

__author__ = "Brian Allen Vanderburg II"
__copyright__ = "Copyright 2019"
__license__ = "Apache License 2.0"


import os
import sys

from .errors import AbortError
from .sources import SourceString



class ApplytmplLib:
    """ Template library for applytmpl. """

    def __init__(self, app):
        """ Initialize the library. """

        self._app = app
        self._data_dirs = app.data_dirs


    def _find_data(self, filename):
        """ Find a data file. """
        parts = tuple(
            i for i in filename.replace(os.sep, "/").split("/")
            if not i in ("", ".", "..")
        )

        for data_dir in self._data_dirs:
            filename = os.path.join(data_dir, *parts)
            if os.path.exists(filename):
                return filename

        return None

    def load_datafile(self, datatype, filename):
        """ Load a data file. """

        filename = self._find_data(filename)
        if filename is None:
            return None

        source = SourceFile(datatype, filename)
        source.load()
        return source.data

    def load_datatext(self, datatype, text):
        """ Load data from text. """
        source = SourceString(datatype, text)
        source.load()
        return source.data

    def warning(self, message):
        """ Print a warning message. """
        print("Warning: " + message, file=sys.stderr, flush=True)

    def info(self, message):
        """ Print an informational message. """

        if self._app.verbose:
            print("Info: " + message, flush=True)

    def error(self, message):
        """ Print an error message and abort. """
        raise AbortError(message)
