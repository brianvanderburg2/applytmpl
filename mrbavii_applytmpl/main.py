#!/usr/bin/env python
""" A simple template-based configuration builder. """

__author__      = "Brian Allen Vanderburg II"
__copyright__   = "Copyright 2016"
__license__     = "Apache License 2.0"


import sys
import os
import argparse
import fnmatch


try:
    from codecs import open
except ImportError:
    pass
 
try:
    import ConfigParser as configparser
except ImportError:
    import configparser


from mrbaviirc import template


class ProgramData(object):
    """ Represent the program data. """

    def __init__(self):
        """ Initialize the program data. """
        self.cmdline = None
        self.params = None
        self.data = None
        self.lib = None

    def getcmdline(self):
        """ Parse the command line arguments. """
        if not self.cmdline is None:
            return self.cmdline

        parser = argparse.ArgumentParser(description="Apply configuration templates.")

        parser.add_argument("--dry", dest="dry", action="store_true", default=False,
            help="Perform a dry run.")
        parser.add_argument("-f", dest="force", action="store_true", default=False,
            help="Force-build a file even if not out of date."
        )
        parser.add_argument("-r", dest="root", required=True,
            help="Specify the input root.")
        parser.add_argument("-o", dest="output", required=True,
            help="Specify the output directory.")
        parser.add_argument("-d", dest="data", action="append",
            help="Specify the data files.")
        parser.add_argument("-D", dest="params", action="append",
            help="Specify name=value pairs of data.")
        parser.add_argument("-w", dest="walk",
            help="Walk the input root and specify glob pattern to match.")
        parser.add_argument("inputs", nargs="*",
            help="Input templates.")

        self.cmdline = parser.parse_args()
        return self.cmdline

    def getparams(self):
        """ Return data from command line parameters. """
        if not self.params is None:
            return self.params

        cmdline = self.getcmdline()
        self.params = {}

        if cmdline.params:
            for value in cmdline.params:
                parts = value.split("=", 1)
                if len(parts) == 1:
                    self.params[parts[0].strip()] = True
                else:
                    self.params[parts[0].strip()] = parts[1].strip()

        return self.params

    def getdata(self):
        """ Read the data file and return the resulting dict. """
        if not self.data is None:
            return self.data

        cmdline = self.getcmdline()

        # Parse data
        parser = configparser.SafeConfigParser()
        if cmdline.data:
            parser.read(cmdline.data)

        result = {}
        for section in parser.sections():
            if not section in result:
                result[section] = {}

            for (key, value) in parser.items(section):
                result[section][key] = value

        # Add cmdline options
        result.update(self.getparams())

        self.data = result
        return self.data

    def getlib(self):
        """ Return the applyconf initial data. """
        if not self.lib is None:
            return self.lib

        cmdline = self.getcmdline()

        self.lib = {
            "lib": template.StdLib(),
            "applytmpl": {
                "root": cmdline.root,
            }
        }
        return self.lib


def apply(source, dirname, env, progdata):
    """ Apply a template to some data and save the results. """
    cmdline = progdata.getcmdline()

    data = dict(progdata.getlib())

    data["applytmpl"].update({
        "sourcefile": os.path.basename(source),
        "sourcedir": os.path.dirname(source),
        "targetdir": dirname
    })

    data.update(progdata.getdata())

    # Load template from input
    tmpl = env.load_file(source)
    env.clear() # Start with a blank slate on each apply.

    rndr = template.StringRenderer()
    tmpl.render(rndr, data)

    found_sections = False
    for section in rndr.get_sections():
        if not section.startswith("file:"):
            continue
        found_sections = True
        target = os.path.join(dirname, section[5:].replace("/", os.sep))

        save(source, target, rndr.get_section(section), progdata)

    if not found_sections:
        # If no sections were created, just write the main content to the
        # output file.  The filename is determined as the input without
        # it's final extension
        (basename, _) = os.path.splitext(os.path.basename(source))
        target = os.path.join(dirname, basename)

        save(source, target, rndr.get(), progdata)

def save(source, target, content, progdata):
    """ Save regenerated output to a file. """
    cmdline = progdata.getcmdline()

    if not (os.path.islink(target) or checktimes(source, target) or cmdline.force):
        log("NOCHG", target, source)
        return

    log("BUILD", target, source)
    if cmdline.dry:
        return

    if os.path.exists(target):
        os.unlink(target) # Unlink so if it is a symlink we don't overwrite target of symlink

    targetdir = os.path.dirname(target)
    if not os.path.isdir(targetdir):
        os.makedirs(targetdir)

    with open(target, "wt") as handle:
        handle.write(content)


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


def entry():
    """ Run the program. """
    # Basic setup
    progdata = ProgramData()
    args = progdata.getcmdline()

    # Create our template environment
    env = template.Environment()

    # Determine inputs
    inputs = list(args.inputs)
    if args.walk:
        for (dir, dirs, files) in os.walk(args.root):
            extra = [os.path.join(dir, i) for i in files if fnmatch.fnmatch(i, args.walk)]
            inputs.extend(extra)

    # Build
    for input in inputs:
        # Deterine output
        relpath = os.path.relpath(input, args.root)
        output = os.path.join(args.output, relpath)

        # Apply
        apply(input, os.path.dirname(output), env, progdata)

    if args.dry:
        log("DRYRN", "This was a dry run.")


def main():
    try:
        entry()
    except (IOError, OSError, ValueError, template.Error) as e:
        log(type(e).__name__, str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

