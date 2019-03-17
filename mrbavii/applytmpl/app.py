""" Apply templates to data and produce output. """

__author__      = "Brian Allen Vanderburg II"
__copyright__   = "Copyright 2019"
__license__     = "Apache License 2.0"


import argparse
import configparser
import fnmatch
import json
import io
import os
import sys

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


import mrbaviirc.template
from mrbaviirc.template.lib.xml import ElementTreeWrapper


class SourceBase(object):
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

    @property
    def type(self):
        return self._type

    @property
    def typename(self):
        return self.TYPENAME_MAP.get(self._type, "unknown")
        

    @property
    def meta(self):
        """ Get the metadata dictionary. """
        self._load()
        return self._meta

    @property
    def body(self):
        """ Get the body contents. """
        self._load()
        return self._body

    @property
    def data(self):
        """ Get the parsed data. """
        self._load()
        return self._data

    def _open(self):
        """ Base method of opening the source. """
        raise NotImplementedError
        
    def _load(self):
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
                    if len(line) == 0:
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
            except ET.ParseError as e:
                e.filename = self._filename
                raise
        elif self._type == self.TYPE_JSON:
            try:
                self._data = json.loads("\n" * self._body_offset + self._body)
            except json.JSONDecodeError as e:
                e.filename = self._filename
                raise
        elif self._type == self.TYPE_INI:
            try:
                config = configparser.ConfigParser()
                config.read_string("\n" * self._body_offset + self._body, self._filename)
                self._data = dict((name, dict(values)) for (name, values) in config.items())
            except configparser.ParsingError as e:
                e.filename = self._filename
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
        sio = StringIO(self._source)
        return contextlib.closing(sio)


class Sources(object):
    def __init__(self):
        self._sources = []

    def add(self, source):
        self._sources.append(source)

    def __iter__(self):
        yield from self._sources


class App(object):
    """ The main application class. """

    MODE_TEMPLATE = 0
    MODE_DATA = 1

    def __init__(self):
        """ Initialize the application. """
        self.cwd = os.getcwd()


    def parse_cmdline(self):
        """ Parse the command line. """

        # Add the arguments
        parser = argparse.ArgumentParser(description="Make static pages.")
        addarg = parser.add_argument

        addarg("-v", "--verbose", dest="verbose", action="count", default=1,
            help="Increaes verbosity level.")
        addarg("-q", "--quiet", dest="verbose", action="store_const", const=0,
            help="Set verbosity level to 0")

        addarg("--dry", dest="dry", action="store_true", default=False,
            help="Dry run, don't save any files.")

        addarg("--force", dest="force", action="store_true", default=False,
            help="Force save even if output is the same.")

        addarg("--type", dest="type", default="template", choices=("template", "xml", "json", "ini", "auto"),
            help="Specify whether how the input is treated.")

        addarg("--root-dir", dest="root_dir", required=True,
            help="Root directory to treat input files relative to.")

        addarg("--out-dir", dest="out_dir", required=True,
            help="Output directory.")

        addarg("--template-dir", dest="template_dir", action="append", default=[],
            help="Template directory to search for templates.")

        addarg("--template-pattern", dest="template_pattern", default="/{}.tmpl",
            help="Template pattern to apply to a template name.  {} is "
                 "substituted for the template name before the template search.")

        addarg("--template-default", dest="template_default", default="main",
            help="Default template name.")

        addarg("--template-code", dest="template_code", default=False, action="store_true",
            help="Enable use of code sections in templates.")

        addarg("--define", dest="define", action="append", default=[],
            help="<name>:<value> defines passed to the templates.")

        addarg("--data", dest="data", action="append", default=[],
            help="<name>:<type>:<file> Of a data file to load as data.")

        addarg("--walk", dest="walk", default=None,
            help="Walk the root directory for files matching the pattern.")

        addarg("--exclude", dest="exclude", action="append", default=[],
            help="Patterns to ignore during walk.")

        addarg("--input-from-file", dest="input_from_file", action="append", default=[],
            help="File containing list of files to use as inputs.")

        addarg("inputs", nargs="*",
            help="Directly specified inputs.")

        args = parser.parse_args()

        # Put into out attributes
        self.verbose = args.verbose
        self.dry = args.dry

        self.force = args.force

        if args.type == "auto":
            self.type = SourceBase.TYPE_HEADERED
        else:
            self.type = SourceBase.TYPE_MAP[args.type]

        self.root_dir = args.root_dir
        self.out_dir = args.out_dir
        
        self.template_dirs = tuple(args.template_dir)
        self.template_pattern = args.template_pattern
        self.template_default = args.template_default
        self.template_code = args.template_code

        self.defines = {}
        for i in args.define:
            parts = i.split(":", 1)
            if len(parts) != 2:
                # TODO: error
                continue

            self.defines[parts[0].strip()] = parts[1].strip()

        self.data = {}
        for i in args.data:
            parts = i.split(":", 2)
            if len(parts) != 3:
                # TODO: error
                continue
            if not parts[1].strip() in ("xml", "json", "ini"):
                # TODO: error
                continue

            self.data[parts[0].strip()] = (SourceBase.TYPE_MAP[parts[1].strip()], parts[2].strip())

        self.walk = args.walk
        self.exclude = tuple(args.exclude)
        self.input_from_files = tuple(args.input_from_file)
        self.initial_inputs = tuple(args.inputs)

    def prepare_templates(self):
        """ Prepare our templates. """

        # First create out template loaders and environment
        paths = list(os.path.normpath(i) for i in self.template_dirs)
        
        if len(paths):
            loader = mrbaviirc.template.SearchPathLoader(paths)
        else:
            loader = mrbaviirc.template.UnrestrictedLoader()

        env = mrbaviirc.template.Environment(
            loader=loader,
            allow_code = self.template_code
        )

        self.template_env = env
        self.template_vars = {}

        # Process any data for our template
        for (name, value) in self.defines.items():
            self.template_vars[name] = value

        for (name, (type, filename)) in self.data.items():
            # Use SourceFile since it already does the parsing
            if self.verbose >= 1:
                print("Loading data: {0}={1}".format(name, filename))
            self.template_vars[name] = SourceFile(type, filename).data

    def find_inputs(self):
        """ Accumulate all inputs in self.inputs. """

        if self.verbose >= 1:
            print("Finding inputs")

        # First find all inputs
        self.inputs = list(self.initial_inputs)
        if self.verbose >= 2:
            for i in self.inputs:
                print("Input: {0}".format(i))

        for fn in self.input_from_files:
            if self.verbose >= 1:
                print("Reading inputs from file: {0}".format(fn))
            with io.open(fn, "rt", newline=None) as handle:
                for line in handle:
                    line = line.rstrip("\n")
                    if line and line[0:1] != "#":
                        self.inputs.append(line)
                        if self.verbose >= 2:
                            print("Input: {0}".format(line))

        if self.walk:
            if self.verbose >= 1:
                print("Scanning for inputs: {0}".format(self.walk))
            for (sdir, sdirs, sfiles) in os.walk(self.root_dir):
                # First check for ignores for directories
                sdirs.sort()
                for i in sdirs:
                    for j in self.exclude:
                        if fnmatch.fnmatch(i, j):
                            sdirs.remove(i)
                            break # break out of ignore filter loop

                for fn in sorted(sfiles):
                    if not fnmatch.fnmatch(fn, self.walk):
                        continue

                    for j in self.exclude:
                        if fnmatch.fnmatch(fn, j):
                            break # break ignore filter loop
                    else:
                        # ignore filter loop not broken
                        fn = os.path.join(sdir, fn)
                        self.inputs.append(fn)
                        if self.verbose >= 2:
                            print("Input: {0}".format(fn))

        # Now prepare our sources list
        self.sources = Sources()
        for i in self.inputs:
            relpath = os.path.relpath(i, self.root_dir)
            toroot = "../" * relpath.replace("\\", "/").count("/")

            source = SourceFile(self.type, i)
            source.relpath = relpath.replace("\\", "/")
            source.toroot = toroot
            self.sources.add(source)

    def handle_inputs(self):
        """ Handle the inputs. """

        if self.verbose >= 1:
            if not self.dry:
                print("Building")
            else:
                print("Building (DRYRUN)")

        for source in self.sources:
            if self.verbose >= 2:
                print("Processing: {0}".format(source._filename))
            source._load()
            if source.type == SourceBase.TYPE_TEMPLATE:
                # The source is the template
                template = self.template_env.load_text(source.body, source._filename, self.template_code)
            else:
                # The source is the data
                templatename = source.meta.get("template", [self.template_default])[0].strip()
                templatepath = self.template_pattern.replace("{}", templatename)
                template = self.template_env.load_file(templatepath)

            data = dict(self.template_vars)
            data["source"] = source

            renderer = mrbaviirc.template.StringRenderer()
            template.render(renderer, data)

            outbase = os.path.join(
                self.out_dir,
                os.path.dirname(source.relpath.replace("/", os.sep))
            )
            sections = renderer.get_sections()
            for name in sections:
                if not name.startswith("file:"):
                    continue
                filename = name[5:]
                outname = os.path.join(outbase, os.path.basename(filename))
                if self.verbose >= 1:
                    print("Generating{0}: {1} -> {2}".format("(DRYRUN)" if self.dry else "", source._filename, outname))
                if not self.dry:
                    if not os.path.isdir(outbase):
                        os.makedirs(outbase)
                    self.save_output(outname, renderer.get_section(name))

    def save_output(self, filename, content):
        """ Save output to a file.  But only if it hasn't changed. """
        save = True
        if not self.force:
            if os.path.isfile(filename):
                with io.open(filename, "rt", encoding="UTF-8", newline=None) as handle:
                    original = handle.read()
                    if original == content:
                        save = False
                        if self.verbose >= 1:
                            print("No change: {0}".format(filename))

        if save:
            with io.open(filename, "wt", encoding="UTF-8", newline="\n") as handle:
                handle.write(content)

    def realrun(self):
        """ Run the application. """

        self.parse_cmdline()
        self.prepare_templates()
        self.find_inputs()
        self.handle_inputs()
    
        #for i in self.sources:
        #    print("==========================")
        #    print(i.relpath)
        #    print(i.toroot)
        #    print(i.meta)
        #    print(i.body)
        #    print(i.data)

    def run(self):
        try:
            self.realrun()
            sys.exit(0)
        except configparser.ParsingError as e:
            print("{0}: {1}".format(e.__class__.__name__, e))
        except ET.ParseError as e:
            print("{0}: {1}".format(e.__class__.__name__, e))
        except json.JSONDecodeError as e:
            print("{0}: {1}".format(e.__class__.__name__, e))
        except mrbaviirc.template.errors.Error as e:
            print("{0}: {1}".format(e.__class__.__name__, e))

        sys.exit(-1)





