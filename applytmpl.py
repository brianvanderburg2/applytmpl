#!/usr/bin/env python
""" A simple template-based configuration builder. """

__author__      = "Brian Allen Vanderburg II"
__copyright__   = "Copyright 2016"
__license__     = "Apache License 2.0"
__version__     = "0.0.1"


import sys
import os
import argparse
import fnmatch
import shutil


try:
    from codecs import open
except ImportError:
    pass


from mrbaviirc import template


class Error(Exception):
    """ Our custom exception object. """
    pass


class Control(object):
    """ Represent a control state. """
    UNSET = 0
    COPY = 1
    FOLLOW = 2
    IGNORE = 3

    def __init__(self, copy=None):
        """ Initialize a control state. """
        self.file_symlink = copy.file_symlink if copy else None
        self.dir_symlink = copy.dir_symlink if copy else None
        self.other_symlink = copy.other_symlink if copy else None
        self.exclude = list(copy.exclude) if copy else None
        self.extension = copy.extension if copy else None
        self.other = copy.other if copy else None
        self.ignore = copy.ignore if copy else None

    def clone(self, update):
        """ Clone and update the control state. """
        c = Control(self)

        if not update.file_symlink is None:
            c.file_symlink = update.file_symlink

        if not update.dir_symlink is None:
            c.dir_symlink = update.dir_symlink

        if not update.other_symlink is None:
            c.other_symlink = update.other_symlink

        if not update.exclude is None and len(update.exclude):
            if update.exclude[0] == None:
                c.exclude = update.exclude[1:]
            else:
                c.exclude.extend(update.exclude)

        if not update.extension is None:
            c.extension = update.extension

        if not update.other is None:
            c.other = update.other

        if not update.ignore is None:
            c.ignore = update.ignore

        return c

    def defaults(self, ext=None):
        """ Set the defaults. """
        self.file_symlink = self.FOLLOW
        self.dir_symlink = self.COPY
        self.other_symlink = self.COPY
        self.exclude = [".*", "*~"]
        self.extension = ext
        self.other = self.IGNORE
        self.ignore = False


class LoadXML_Node(template.Library):
    """ Represent an XML node. """

    def __init__(self, node):
        """ Initialize the XML node. """
        self._node = node
        self._text = None

    def call_tag(self):
        """ Get the name of the node. """
        return self._node.tag

    def call_text(self):
        """ Get the text of the node. """
        if self._text is None:
            self._text = "".join(self._node.itertext())

        return self._text

    def __iter__(self):
        """ Allow iteration over the node. """
        for child in self._node:
            yield LoadXML_Node(child)

    def lib_find(self, what):
        """ Find child items. """
        child = self._node.find(what)
        if not child is None:
            child = LoadXML_Node(child)

        return child

    def lib_findall(self, what):
        """ Find child items. """
        return map(LoadXML_Node, self._node.findall(what))

    def lib_get(self, attr, defval=None):
        """ Get an attribute or default vaule. """
        return self._node.get(key, defval)


class LoadXML(object):
    """ An XML loader. """

    @staticmethod
    def load(filename):
        """ Load the data and return the object to assign to 'data' """
        try:
            import xml.etree.cElementTree as ET
        except ImportError:
            import xml.etree.ElementTree as ET

        tree = ET.parse(filename)
        root = tree.getroot()

        return LoadXML_Node(root)


class LoadIni(object):
    """ Class to load an INI file. """

    @staticmethod
    def load(filename):
        """ Load the data and return the resulting dict. """
        try:
            import ConfigParser as configparser
        except ImportError:
            import configparser

        result = {}

        parser = configparser.SafeConfigParser()
        parser.read(filename)

        for section in parser.sections():
            if not section in result:
                result[section] = {}

            for (key, value) in parser.items(section):
                result[section][key] = value

        return result


class LoadJSON(object):
    """ Class to load a JSON file. """

    @staticmethod
    def load(filename):
        """ Load the data and result the result. """
        import json

        with open(filename, "rU") as handle:
            return json.load(handle)


class ProgramData(object):
    """ Represent the program data. """

    def __init__(self):
        """ Initialize the program data. """
        self.cmdline = None
        self.setup = None
        self.setup_context = None
        self.setup_data_loaders = None
        self.controls = None
        self.params = None
        self.data = None
        self.lib = None

    def getcmdline(self):
        """ Parse the command line arguments. """
        if not self.cmdline is None:
            return self.cmdline

        parser = argparse.ArgumentParser(description="Apply configuration templates.")

        parser.add_argument("--live", dest="live", action="store_true", default=False,
            help="Make actual changes instead of a dry run.")
        parser.add_argument("--force", dest="force", action="store_true", default=False,
            help="Force-build a file even if not out of date."
        )
        parser.add_argument("--input", dest="input", required=True,
            help="Specify the input file or directory.")
        parser.add_argument("--output", dest="output", required=True,
            help="Specify the output directory.")
        parser.add_argument("--mode", dest="mode", choices=["template", "data"],
            required=True,
            help="Specify whether input is data or templates")
        parser.add_argument("--ext", dest="extension", required=True,
            help="File extension, including the dot, to act on by default.")
        parser.add_argument("--data", dest="data",
            help="Specify the data file if mode is template.")
        parser.add_argument("--template", dest="template",
            help="Specify the template if mode is data.")
        parser.add_argument("--datatype", dest="datatype", default="ini",
            help="Specify the expected data type.")
        parser.add_argument("--control", dest="control",
            help="Specify the control file.")
        parser.add_argument("--setup", dest="setup",
            help="Provide a setup script file.")
        parser.add_argument(dest="values", nargs="*",
            help="Specify name=value pairs of data.")

        self.cmdline = parser.parse_args()
        return self.cmdline

    def getsetup(self):
        """ Read the setup script file. """
        if not self.setup is None:
            return self.setup

        self.setup = {}

        cmdline = self.getcmdline()
        if cmdline.setup is None:
            return self.setup

        # Load and execute the setup file
        source = open(cmdline.setup, "rU").read()
        code = compile(source, cmdline.setup, "exec")
        data = {}
        exec(code, data, data)

        self.setup = data
        return self.setup

    def getsetup_context(self):
        """ Get the setup context. """
        if not self.setup_context is None:
            return self.setup_context

        setup = self.getsetup()
        self.setup_context = {}
        if "setup_context" in setup:
            self.setup_context.update(setup["setup_context"]())

        return self.setup_context

    def getsetup_data_loaders(self):
        """ Return the setup data loaders. """
        if not self.setup_data_loaders is None:
            return self.setup_data_loaders

        setup = self.getsetup()
        self.setup_data_loaders = {
            "xml": LoadXML.load,
            "ini": LoadIni.load,
            "json": LoadJSON.load
        }
        if "setup_data_loaders" in setup:
            self.setup_data_loaders.update(setup["setup_data_loaders"]())

        return self.setup_data_loaders

    def getparams(self):
        """ Return data from command line parameters. """
        if not self.params is None:
            return self.params

        cmdline = self.getcmdline()
        self.params = {}

        for value in cmdline.values:
            parts = value.split("=", 1)
            if len(parts) == 1:
                self.params[parts[0].strip()] = True
            else:
                self.params[parts[0].strip()] = parts[1].strip()

        return self.params

    def getdata(self, source):
        """ Read the data file and return the resulting dict. """
        if not self.data is None:
            return self.data

        cmdline = self.getcmdline()
        setup = self.getsetup()

        result = {}

        # From the data
        loaders = self.getsetup_data_loaders()
        loader = loaders.get(cmdline.datatype, LoadIni.load)

        if cmdline.mode == "template":
            # Input is template, so data comes from data file
            if cmdline.data:
                result["data"] = loader(cmdline.data)
        else:
            # Input is data, so data comes from there
            result["data"] = loader(source)


        # From command line parameters
        result.update(self.getparams())

        if cmdline.mode == "template":
            # Data is from a single source, so we can cache the result.
            self.data = result
            return self.data
        else:
            # Each source input is data, so we can't cache the result
            return result

    def getcontrols(self):
        """ Read the control file. """
        if not self.controls is None:
            return self.controls

        cmdline = self.getcmdline()
        if cmdline.control is None:
            self.controls = {}
            return self.controls

        parser = configparser.SafeConfigParser()
        parser.read(cmdline.control)

        result = {}
        for section in parser.sections():
            c = result.setdefault(section, Control())

            for (key, value) in parser.items(section):
                key = key.strip()
                value = value.strip()

                if key in ("file_symlink", "dir_symlink", "other_symlink"):
                    if value == "copy":
                        value = Control.COPY
                    elif value == "follow" and key != "other_symlink":
                        value = Control.FOLLOW
                    elif value == "ignore":
                        value = Control.IGNORE
                    else:
                        value = None # TODO: error

                    if key == "file_symlink":
                        c.file_symlink = value
                    elif key == "other_symlink":
                        c.other_symlink = value
                    else:
                        c.dir_symlink = value

                elif key == "exclude":
                    if value[0:1] == "+":
                        c.exclude = []
                        value = value[1:]
                    else:
                        c.exclude = [None]
                    
                    parts = value.split(",")
                    for part in parts:
                        part=part.strip()
                        if part:
                            c.exclude.append(part)

                elif key == "extension":
                    c.extension = value

                elif key == "other":
                    if value == "ignore":
                        c.other = Control.IGNORE
                    elif value == "copy":
                        c.other = Control.COPY
                    else:
                        pass # TODO: error

                elif key == "ignore":
                    c.ignore = (value.lower() in ("yes", "on", "true", "1"))


        self.controls = result
        return self.controls

    def getstate(self, path, state):
        """ Get a new state based on the current state and relpath """

        controls = self.getcontrols()

        path = path.replace(os.sep, "/")

        if not path in controls:
            return state
        else:
            return state.clone(controls[path])

    def getlib(self):
        """ Return the applyconf initial data. """
        if not self.lib is None:
            return self.lib

        cmdline = self.getcmdline()

        self.lib = {
            "lib": template.StdLib(),
            "applytmpl": {
                "root": cmdline.input,
            }
        }

        self.lib.update(self.getsetup_context())
        return self.lib


def apply(source, dirname, env, state, progdata):
    """ Apply a template to some data and save the results. """
    cmdline = progdata.getcmdline()

    data = dict(progdata.getlib())

    data["applytmpl"].update({
        "sourcefile": os.path.basename(source),
        "sourcedir": os.path.dirname(source),
        "targetdir": dirname
    })

    data.update(progdata.getdata(source))

    if cmdline.mode == "template":
        # Input is template, load template from input
        tmpl = env.load_file(source)
    else:
        # Input is data, load templte from cmdline
        if cmdline.template:
            tmpl = env.load_file(cmdline.template)
        else:
            raise Error("Must specify template with mode data")

    env.clear() # Start with a blank slate on each apply.

    rndr = template.StringRenderer()
    tmpl.render(rndr, data)

    for section in rndr.get_sections():
        if not section.startswith("file:"):
            continue
        target = os.path.join(dirname, section[5:].replace("/", os.sep))

        if not (os.path.islink(target) or checktimes(source, target) or cmdline.force):
            log("NOCHG", target, source)
            continue

        log("BUILD", target, source)
        if not cmdline.live:
            continue

        if os.path.exists(target):
            os.unlink(target) # Unlink so if it is a symlink we don't overwrite target of symlink
    
        with open(target, "wt") as handle:
            handle.write(rndr.get_section(section))


def copylink(source, target, state, progdata):
    """ Copy a symbolic link. """
    cmdline = progdata.getcmdline()

    link = os.readlink(source)
    log("SYMLN", target, "{0} --> {1}".format(source, link))
    if not cmdline.live:
        return

    if os.path.exists(target) or os.path.islink(target):
        os.unlink(target)
    os.symlink(link, target)


def copyfile(source, target, state, progdata):
    """ Copy a file. """
    cmdline = progdata.getcmdline()

    if os.path.islink(target) or checktimes(source, target) or cmdline.force:
        log("COPY ", target, source)
        if not cmdline.live:
            return

        if os.path.exists(target):
            os.unlink(target)

        shutil.copy(source, target)
    else:
        log("NOCHG", target, source)


def handlefile(source, target, env, state, progdata):
    """ Handle a file action. """
    if source.endswith(state.extension):
        apply(source, os.path.dirname(target), env, state, progdata)
    elif state.other == Control.COPY:
        copyfile(source, target, state, progdata)


def checktimes(source, target):
    """ Check timestamps and return true to continue, false if up to date. """
    if not os.path.isfile(target):
        return True

    stime = os.path.getmtime(source)
    ttime = os.path.getmtime(target)

    return stime > ttime


def log(status, message, extra=None):
    """ Log a simple status message. """
    if extra:
        print("{0}: {1} ({2})".format(status, message, extra))
    else:
        print("{0}: {1}".format(status, message))


def process(indir, outdir, relpath, env, state, progdata):
    """ Process a given directory. """
    cmdline = progdata.getcmdline()

    if not os.path.isdir(outdir) and cmdline.live:
        os.makedirs(outdir)
        # TODO: create outdir based on state information
        # state can contain perms, ownershipm etc

    listing = os.listdir(indir)
    for entry in sorted(listing):

        # Set some values for the entry
        entrypath = os.path.join(relpath, entry)
        inpath = os.path.join(indir, entry)
        outpath = os.path.join(outdir, entry)
        entrystate = progdata.getstate(entrypath, state)

        # Check against excludes
        if entrystate.ignore:
            continue

        if any(fnmatch.fnmatchcase(entrypath, exclude) for exclude in state.exclude):
            continue

        # Handle the entry
        if os.path.isdir(inpath):
            if os.path.islink(inpath):
                if entrystate.dir_symlink == Control.FOLLOW:
                    process(inpath, outpath, entrypath, env, entrystate, progdata)
                elif entrystate.dir_symlink == Control.COPY:
                    copylink(inpath, outpath, entrystate, progdata)
                else:
                    pass # Other option is ignore
            else:
                process(inpath, outpath, entrypath, env, entrystate, progdata)

        elif os.path.isfile(inpath):
            if os.path.islink(inpath):
                if entrystate.file_symlink == Control.FOLLOW:
                    handlefile(inpath, outpath, env, entrystate, progdata)
                elif entrystate.file_symlink == Control.COPY:
                    copylink(inpath, outpath, entrystate, progdata)
                else:
                    pass # Other option is ignore
            else:
                handlefile(inpath, outpath, env, entrystate, progdata)

        elif os.path.islink(inpath): # Not file or directory
            if entrystate.other_symlink == Control.COPY:
                copylink(inpath, outpath, entrystate, progdata)
            else:
                pass # Other option is ignore



def main():
    """ Run the program. """
    # Basic setup
    progdata = ProgramData()
    args = progdata.getcmdline()

    # Set initial states
    state = Control()
    state.defaults(args.extension)

    # Create our template environment
    env = template.Environment()


    # Build
    state = progdata.getstate(".", state)
    if os.path.isfile(args.input):
        apply(args.input, args.output, env, state, progdata)
    else:
        process(args.input, args.output, "", env, state, progdata)

    if not args.live:
        log("DRYRN", "This was a dry run.")


try:
    main()
except (IOError, OSError, ValueError, Error, template.Error) as e:
    log(type(e).__name__, str(e))
    sys.exit(1)


