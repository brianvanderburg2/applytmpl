#!/usr/bin/env python
""" A simple template-based configuration builder. """

__author__      = "Brian Allen Vanderburg II"
__copyright__   = "Copyright 2016"
__license__     = "Apache License 2.0"
__version__     = "0.0.1"


import sys
import os
import argparse
import re

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

try:
    from codecs import open
except ImportError:
    pass


from mrbaviirc import template


def parseargs():
    """ Parse the command line arguments. """
    parser = argparse.ArgumentParser(description="Apply configuration templates.")

    parser.add_argument("-n", dest="dryrun", action="store_true", default=False,
        help="Dry run.  Log messages but dont touch any files.")
    parser.add_argument("-f", dest="force", action="store_true", default=False,
        help="Force-build a file even if not out of date."
    )
    parser.add_argument("-s", dest="symlink", action="store_true", default=False,
        help=("Copy symlink that links to a file instead of following it. "
              "Symlinks to directories and non-regular files are always copied as symlinks.")
    )
    parser.add_argument("-e", dest="ext", default=".tmpl",
        help="Extension for scanned templates.")
    parser.add_argument("-i", dest="input", required=True,
        help="Specify the input file or directory.")
    parser.add_argument("-o", dest="output", required=True,
        help="Specify the output file or directory.")
    parser.add_argument("-d", dest="data", required=True,
        help="Specify the data file.")
    parser.add_argument(dest="values", nargs="*",
        help="Specify name=value pairs of data.")

    return parser.parse_args()


def readdata(fn):
    """ Read the data file and return the resulting dict. """
    parser = configparser.SafeConfigParser()
    parser.read(fn)

    result = {}
    for section in parser.sections():
        if not section in result:
            result[section] = {}

        for (key, value) in parser.items(section):
            result[section][key] = value

    return result


def apply(source, dirname, data, args, _env=[None]):
    """ Apply a template to some data and save the results. """
    if not _env[0]:
        context = {}
        for value in args.values:
            parts = value.split("=", 1)
            if len(parts) == 1:
                context[parts[0].strip()] = True
            else:
                context[parts[0].strip()] = parts[1].strip()

        context["lib"] = template.StdLib()
        _env[0] = template.Environment(context)

        

    env = _env[0]

    tmpl = env.load_file(source)
    rndr = template.StringRenderer()
    tmpl.render(rndr, data)

    for section in rndr.get_sections():
        if not section.startswith("file:"):
            continue
        target = os.path.join(dirname, section[5:])

        if not (os.path.islink(target) or checktimes(source, target) or args.force):
            log("NOCHG", target, source)
            continue

        log("BUILD", target, source)
        if args.dryrun:
            continue

        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        elif os.path.exists(target):
            os.unlink(target) # Unlink so if it is a symlink we don't overwrite target of symlink
    
        with open(target, "wt") as handle:
            handle.write(rndr.get_section(section))


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


def walk(root):
    """ Walk a path and return all files and symlinks. """
    for item in sorted(os.listdir(root)):
        path = os.path.join(root, item)
        if os.path.isdir(path) and not os.path.islink(path):
            for i in walk(path):
                yield i
        else:
            yield path


def main():
    """ Run the program. """
    args = parseargs()

    data = readdata(args.data)

    # Building just a file
    if os.path.isfile(args.input):
        apply(args.input, args.output, data, args)
        sys.exit(0)

    # Building a directory
    for input in walk(args.input):
        rel = os.path.relpath(input, args.input)
        output = os.path.join(args.output, rel)
        dirname = os.path.dirname(output)

        # Walk only returns files and links
        # If file always build
        # If link to file, build if not args.symlink
        # For all other links (such as to directory, or device, etc), copy link

        if os.path.isfile(input) and (not os.path.islink(input) or not args.symlink):
            if input.endswith(args.ext):
                apply(input, dirname, data, args)
        else:
            link = os.readlink(input)
            log("SYMLN", output, "{0} --> {1}".format(input, link))
            if args.dryrun:
                continue

            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            elif os.path.isfile(output) or os.path.islink(output):
                os.unlink(output)
            os.symlink(link, output)

    if args.dryrun:
        log("DRYRN", "This was a dry run.")


try:
    main()
except (OSError, ValueError, configparser.Error, template.errors.Error) as e:
    log(type(e).__name__, str(e))
    sys.exit(1)


