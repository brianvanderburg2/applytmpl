#!/usr/bin/env python
#
# \file
# \author Brian Allen Vanderburg II
# \copyright GPL v3 or later
# \date 2016
#
# This application provides a simple template-based configuration builder.


import sys
import os
import argparse
import re

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

try:
    basestring
except NameError:
    basestring = str

try:
    from codecs import open
except ImportError:
    pass


def parseargs():
    """ Parse the command line arguments. """
    parser = argparse.ArgumentParser(description="Apply configuration templates.")

    parser.add_argument("-f", dest="force", action="store_true", default=False,
        help="Force-build a file even if not out of date."
    )
    parser.add_argument("-s", dest="symlink", action="store_true", default=False,
        help=("Copy symlink that links to a file instead of following it. "
              "Symlinks to directories and non-regular files are always copied as symlinks.")
    )
    parser.add_argument("-i", dest="input", required=True,
        help="Specify the input file or directory.")
    parser.add_argument("-o", dest="output", required=True,
        help="Specify the output file or directory.")
    parser.add_argument("-d", dest="data", required=True,
        help="Specify the data file.")

    return parser.parse_args()


def readdata(fn):
    """ Read the data file and return the resulting dict. """
    parser = configparser.SafeConfigParser()
    parser.read(fn)

    result = {}
    for section in parser.sections():
        for (key, value) in parser.items(section):
            result[section + "." + key] = value

    return result
        

def apply(source, target, data):
    """ Apply a template to some data and save the result. """
    with open(source, "rU") as handle:
        contents = handle.read()

    def callback(mo):
        key = mo.group(1)
        if len(key) == 0: # Escaping the key delimiters
            return "@"
        elif key in data:
            return data[key]
        else:
            raise ValueError("No such value: {0}".format(key))

    contents = re.sub("@(.*?)@", callback, contents)

    dirname = os.path.dirname(target)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    elif os.path.exists(target):
        os.unlink(target) # Unlink so if it is a symlink we don't overwrite target of symlink
    
    with open(target, "wt") as handle:
        handle.write(contents)


def checktimes(source, target):
    """ Check timestamps and return true to continue, false if up to date. """
    if not os.path.isfile(target):
        return True

    stime = os.path.getmtime(source)
    ttime = os.path.getmtime(target)

    return stime > ttime


def log(status, message):
    """ Log a simple status message. """
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
        if args.force or checktimes(args.input, args.output):
            log("BUILD", args.output)
            apply(args.input, args.output, data)
        else:
            log("NOCHG", args.output)

        sys.exit(0)

    # Building a directory
    for input in walk(args.input):
        rel = os.path.relpath(input, args.input)
        output = os.path.join(args.output, rel)

        # Walk only returns files and links
        # If file always build
        # If link to file, build if not args.symlink
        # For all other links (such as to directory, or device, etc), copy link

        if os.path.isfile(input) and (not os.path.islink(input) or not args.symlink):
            if args.force or os.path.islink(output) or checktimes(input, output):
                log("BUILD", output)
                apply(input, output, data)
            else:
                log("NOCHG", output)
        else:
            log("SYMLN", output)
            if os.path.isfile(output) or os.path.islink(output):
                os.unlink(output)
            link = os.readlink(input)
            os.symlink(link, output)


try:
    main()
except (OSError, ValueError, configparser.Error) as e:
    log("ERROR", str(e))
    sys.exit(1)


