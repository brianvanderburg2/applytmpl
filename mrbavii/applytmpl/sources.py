""" Manage the sources. """
# pylint: disable=missing-docstring, redefined-builtin, too-few-public-methods
# pylint: disable=too-many-branches, too-many-instance-attributes

__author__ = "Brian Allen Vanderburg II"
__copyright__ = "Copyright 2019"
__license__ = "Apache License 2.0"


import configparser
import contextlib
import io
import json

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


from mrbaviirc.template.lib.xml import ElementTreeWrapper


class SourceBase:
    """ Represent a single source. """

    TYPE_HEADERED = 0 # Temporary type until type is read from header
    TYPE_XML = 1
    TYPE_JSON = 2
    TYPE_INI = 3
    TYPE_TEMPLATE = 4
    TYPE_UNKNOWN = 99

    TYPE_MAP = {
        "xml": TYPE_XML,
        "json": TYPE_JSON,
        "ini": TYPE_INI,
        "template": TYPE_TEMPLATE
    }

    TYPENAME_MAP = {
        TYPE_XML: "xml",
        TYPE_JSON: "json",
        TYPE_INI: "ini",
        TYPE_TEMPLATE: "template",
    }

    def __init__(self, type):
        """ Initialize the source. """

        self._filename = "<string>"
        self._type = type
        self._meta = {}
        self._body_offset = 0
        self._body = None
        self._data = None

        # Externally assigned/accessed
        self.relpath = None
        self.toroot = None

    @property
    def filename(self):
        return self._filename

    @property
    def type(self):
        return self._type

    @property
    def typename(self):
        return self.TYPENAME_MAP.get(self._type, "unknown")

    @property
    def meta(self):
        """ Get the metadata dictionary. """
        self.load()
        return self._meta

    @property
    def body(self):
        """ Get the body contents. """
        self.load()
        return self._body

    @property
    def data(self):
        """ Get the parsed data. """
        self.load()
        return self._data

    def _open(self):
        """ Base method of opening the source. """
        raise NotImplementedError

    def load(self):
        """ Load the source. """
        if self._body is not None:
            return

        # First read the contents
        with self._open() as handle:
            # Read the meta information
            self._meta = {}
            self._body_offset = 0

            if self._type == self.TYPE_HEADERED:
                while True:
                    self._body_offset += 1
                    line = handle.readline().strip()
                    if not line:
                        break # First blank line terminates headers

                    if line[0] == "#":
                        continue # Comment

                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        continue

                    (name, value) = (parts[0].strip().lower(), parts[1].strip())
                    self._meta.setdefault(name, []).append(value)

                # Fixup the type of data we have
                type = self._meta.get("type", [None])[0]
                self._type = self.TYPE_MAP.get(type, self.TYPE_UNKNOWN)
                if self._type == self.TYPE_UNKNOWN:
                    # TODO: error
                    pass

            # Read the rest of the body
            self._body = handle.read()

        # After reading, parse the body
        if self._type == self.TYPE_TEMPLATE:
            self._data = self._body
        elif self._type == self.TYPE_XML:
            try:
                root = ET.fromstring("\n" * self._body_offset + self._body)
                self._data = ElementTreeWrapper(root)
            except ET.ParseError as exc:
                exc.filename = self._filename
                raise
        elif self._type == self.TYPE_JSON:
            try:
                self._data = json.loads("\n" * self._body_offset + self._body)
            except json.JSONDecodeError as exc:
                exc.filename = self._filename
                raise
        elif self._type == self.TYPE_INI:
            try:
                config = configparser.ConfigParser()
                config.read_string("\n" * self._body_offset + self._body, self._filename)
                self._data = dict((name, dict(values)) for (name, values) in config.items())
            except configparser.ParsingError as exc:
                exc.filename = self._filename
                raise


class SourceFile(SourceBase):
    """ Represent as source loaded from a file. """

    def __init__(self, type, filename):
        SourceBase.__init__(self, type)
        self._filename = filename

    def _open(self):
        return io.open(self._filename, "rt", newline=None)


class SourceString(SourceBase):
    """ Represent a source loaded from a string. """

    def __init__(self, type, string):
        SourceBase.__init__(self, type)
        self._source = string

    def _open(self):
        sio = io.StringIO(self._source)
        return contextlib.closing(sio)


class SourceList:
    def __init__(self):
        self._sources = []

    def add(self, source):
        self._sources.append(source)

    def __iter__(self):
        yield from self._sources
