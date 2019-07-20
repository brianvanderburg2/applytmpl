""" Template library functions for applytmpl. """

__author__ = "Brian Allen Vanderburg II"
__copyright__ = "Copyright 2019"
__license__ = "Apache License 2.0"


import os

from .sources import SourceFile


class ApplytmplLib:
    """ Template library for applytmpl. """

    def __init__(self, data_dirs):
        """ Initialize the library. """

        self._data_dirs = data_dirs


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

    def load_data(self, datatype, filename):
        """ Load a data file. """

        filename = self._find_data(filename)
        if filename is None:
            return None

        source = SourceFile(datatype, filename)
        source.load()
        return source.data
