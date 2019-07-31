""" Error classes. """
# pylint: disable=missing-docstring, redefined-builtin, too-few-public-methods
# pylint: disable=too-many-branches, too-many-instance-attributes

__author__ = "Brian Allen Vanderburg II"
__copyright__ = "Copyright 2019"
__license__ = "Apache License 2.0"


class Error(Exception):
    pass

class AbortError(Error):
    pass
