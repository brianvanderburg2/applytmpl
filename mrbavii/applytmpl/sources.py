""" Manage the sources. """
# pylint: disable=missing-docstring, redefined-builtin, too-few-public-methods
# pylint: disable=too-many-branches, too-many-instance-attributes

__author__ = "Brian Allen Vanderburg II"
__copyright__ = "Copyright 2019"
__license__ = "Apache License 2.0"


import configparser
import contextlib
import fnmatch
import io
import json

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


from mrbaviirc.template.lib.xml import ElementTreeWrapper


class SourceBase:
    """ Represent a single source. """

    TYPES = (
        "auto", # Temporary type until final type is known
        "unknown", # Unable to determine type
        "xml",
        "json",
        "ini",
        "template",
    )

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
        return self.type if self.type in self.TYPES else "unknown"

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

            if self._type == "auto":
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
                    self._meta[name] = value

                # Fixup the type of data we have
                type = self._meta.get("type", None)
                self._type = type if type in self.TYPES else "unknown"
                if self._type == "unknown":
                    # TODO: error
                    pass

            # Read the rest of the body
            self._body = handle.read()

        # After reading, parse the body
        if self._type == "template":
            self._data = self._body
        elif self._type == "xml":
            try:
                root = ET.fromstring("\n" * self._body_offset + self._body)
                self._data = ElementTreeWrapper(root)
            except ET.ParseError as exc:
                exc.filename = self._filename
                raise
        elif self._type == "json":
            try:
                self._data = json.loads("\n" * self._body_offset + self._body)
            except json.JSONDecodeError as exc:
                exc.filename = self._filename
                raise
        elif self._type == "ini":
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

    def include_path(self, pattern):
        """ Filter the list by those with a relpath matching a pattern. """
        new_sources = SourceList()
        for source in self._sources:
            if fnmatch.fnmatch(source.relpath, pattern):
                new_sources.add(source)

        return new_sources

    def exclude_path(self, pattern):
        """ Filter the list by those with a relpath matching a pattern. """
        new_sources = SourceList()
        for source in self._sources:
            if not fnmatch.fnmatch(source.relpath, pattern):
                new_sources.add(source)

        return new_sources

    @staticmethod
    def meta_check(value, test):
        """ Test a value against a check. """

        if not test:
            return True # An empty test passes just by having the metadata name

        parts = tuple(v.strip().lower() for v in value.split(","))
        test = test.lower()
        for part in parts:
            if test in part:
                return True

        return False

    def include_meta(self, name, test=""):
        """ Filter by matched meta. """
        new_sources = SourceList()
        for source in self._sources:
            if name in source.meta and self.meta_check(source.meta[name], test):
                new_sources.add(source)

        return new_sources

    def exclude_meta(self, name, test=""):
        """ Filter by matched meta. """
        new_sources = SourceList()
        for source in self._sources:
            if name in source.meta and self.meta_check(source.meta[name], test):
                pass # Exclude matched items
            else:
                new_sources.add(source)

        return new_sources

    def sorted(self, meta):
        """ Sort by given meta. Return a new list since sorting top level
            sources may mess up handling the inputs. """
        # pylint: disable=protected-access
        new_sources = SourceList()
        new_sources._sources = list(self._sources)

        for part in reversed(meta.split(",")):
            # pylint: disable=cell-var-from-loop

            # Reversed or not for this part
            rsort = False
            if part[0:2] == "a:":
                part = part[2:]
            elif part[0:2] == "d:":
                rsort = True
                part = part[2:]

            def _keyfn(obj):
                if part == "relpath":
                    # magic meta refer's to the source's relpath
                    return obj.relpath if obj.relpath is not None else ""

                return obj.meta.get(part, "")

            new_sources._sources.sort(key=_keyfn, reverse=rsort)

        return new_sources

    def __len__(self):
        """ Count the sources. """
        return len(self._sources)

    def __getitem__(self, item):
        """ Get an item or slice """

        if isinstance(item, slice):
            new_sources = SourceList()
            # pylint: disable=protected-access
            new_sources._sources = self._sources[item]
            return new_sources

        return self._sources[item]

    def split(self, size):
        """ Split the sources into sets of n.
            The last set may have less than n. """
        results = []
        for i in range(0, len(self._sources), size):
            new_sources = SourceList()
            #pylint: disable=protected-access
            new_sources._sources = self._sources[i:i+size]
            results.append(new_sources)

        return results
