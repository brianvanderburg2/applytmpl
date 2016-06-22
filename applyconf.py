#!/usr/bin/env python
#
# \file
# \author Brian Allen Vanderburg II
# \copyright MIT license
# \date 2016
#
# This application provides a simple template-based configuration builder.


# License
################################################################################
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# Credits
################################################################################

# Templite
#------------------------------------------------------------------------------
# Portions of the code below are based on the Templite code that is part of the
# 500 lines or less project.


# Imports
################################################################################

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


# Template generation portion based mostly on Templite with modifications.
################################################################################

class CodeBuilder(object):
    """ Represent code to be compiled. """

    INDENT_SIZE = 4

    def __init__(self, indent=0):
        """ Initialize the code fragment with a specific indentation level. """
        self._code = []
        self._indent = indent

    def __str__(self):
        """ Return the single string representation of the code. """
        return "".join(str(c) for c in self._code)

    def indent(self):
        """ Increase the indentation level. """
        self._indent += self.INDENT_SIZE

    def dedent(self):
        """ Decrease the indention level. """
        # TODO: check for error
        self._indent -= self.INDENT_SIZE

    def add_section(self):
        """ Add a new section to the code.  Additional code can be added
            to the section later. """
        code = CodeBuilder(self._indent)
        self._code.append(code)
        return code

    def add_line(self, line):
        """ Add a new line to the code at the current indent level. """
        self._code.extend([" " * self._indent, line, "\n"])

    def get_globals(self):
        """ Return the globals defined within the code. """
        assert self._indent == 0;
        print(str(self))
        names = {}
        exec(str(self), names)

        return names

        
class Template(object):
    """ Simple template parser and renderer.

    Extended variable access:

        {{ expression }}

        Expression:

            [variable or value] [ | function [(variable or value, ...)] ]*

        For example:

            {{ value }}

            {{ value | upper }}

            {{ value | index(12) }}

            {{ value | index(other.value) | upper }}

            {{ | random(1, 10) }} {# No value was used on purpose. #}

    Loops:

        {% for var in expression %}
        {% endfor %}

    Conditions:

        {% if expression %}
        {% elif expression %}
        {% else %}
        {% endif %}

    Set a variable

        {% set var = expresssion %}

    Comments:

        {# This is a commend. #}

    Whitespace control.  A "-" after an opening block will eat any preceeding
    whitespace up to and including the previous new line:

        {#- ... #}
        {{- ... }}
        {%- ... %}
    """

    def __init__(self, text=None, filename=None, *contexts):
        """ Initialize a template with context variables. """

        if text is None and filename is None:
            sys.exit(-1)
            # TODO: error

        if not text:
            self._filename = filename
            text = open(filename, "rU").read()
        else:
            self._filename = None

        # Copy all contexts into our context
        self._context = {}
        for context in contexts:
            self._context.update(context)

        # Keep track of variables accessed
        self._all_vars = set()
        self._loop_vars = set()

        # Manage the code we are building.
        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")
        body_code = code.add_section()
        code.add_line("return ''.join(result)")
        code.dedent()

        self._build_code(text, body_code)

        for var_name in self._all_vars - self._loop_vars:
            vars_code.add_line("c_{0} = context['{0}']".format(var_name))


        self._render_function = code.get_globals()["render_function"]

    def _build_code(self, text, code):
        """ Build the code for the template. """

        # Whitespace control function
        def whitespace_control(token):
            if token[2:3] == "-":
                code.add_line("if len(result) > 0:")
                code.indent()
                code.add_line("last_nl = result[-1].rfind('\\n')")
                code.add_line("if last_nl == -1:")
                code.indent()
                code.add_line("result[-1] = result[-1].rstrip()")
                code.dedent()
                code.add_line("else:")
                code.indent()
                code.add_line("result[-1] = result[-1][:last_nl] + result[-1][last_nl:].rstrip()")
                code.dedent()
                code.dedent()
                return token[3:-2].strip()
            else:
                return token[2:-2].strip()


        # Keep track of our stack
        ops_stack = []

        # Split tokens
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith("{#"):
                # Just a comment
                whitespace_control(token)
                continue

            elif token.startswith("{{"):
                # Output some value
                token = whitespace_control(token)

                expr = self._expr_code(token)
                code.add_line("append_result(to_str({0}))".format(expr))
            
            elif token.startswith("{%"):
                # An action
                token = whitespace_control(token)
                
                words = token.split()

                if words[0] == "set":
                    # set <variable> = <condition...>
                    if len(words) < 4 or words[2] != "=":
                        self._syntax_error("Don't understand set", token)

                    self._variable(words[1], None)
                    code.add_line("c_{0} = {1}".format(
                            words[1],
                            self._expr_code(" ".join(words[3:])),
                        )
                    )
                elif words[0] == "if":
                    # if <condition...>
                    if len(words) < 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append("if")
                    expr = self._expr_code(" ".join(words[1:]))
                    code.add_line("if {0}:".format(expr))
                    code.indent()

                elif words[0] == "elif":
                    # elif <condition...>
                    if len(words) < 2:
                        self._syntax_error("Don't understand elif", token)

                    if not ops_stack:
                        self._syntax_error("Mismatched elif", token)
                    start_what = ops_stack[-1]
                    if start_what != "if":
                        self._syntax_error("Mismatched elif", token)

                    expr = self._expr_code(" ".join(words[1:]))
                    code.dedent()
                    code.add_line("elif {0}:".format(expr))
                    code.indent()

                elif words[0] == "else":
                    # else
                    if len(words) != 1:
                        self._syntax_error("Don't understand else", token)

                    if not ops_stack:
                        self._syntax_error("Mismatched else", token)
                    start_what = ops_stack[-1]
                    if start_what != "if":
                        self._syntax_error("Mismatched else", token)

                    code.dedent()
                    code.add_line("else:")
                    code.indent()

                elif words[0] == "for":
                    # for <variable> in <condition...>
                    if len(words) < 4 or words[2] != "in":
                        self._syntax_error("Don't understarnd for", token)
                    ops_stack.append("for")
                    self._variable(words[1], self._loop_vars)
                    code.add_line(
                        "for c_{0} in {1}:".format(
                            words[1],
                            self._expr_code(" ".join(words[3:]))
                        )
                    )
                    code.indent()

                elif words[0].startswith("end"):
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)

                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])

            else:
                #Literal content
                if token:
                    code.add_line("append_result(to_str({0}))".format(repr(token)))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

    def _expr_code(self, expr):
        """ Create a python expression for output, if, and for. """
        expr = expr.strip()

        if len(expr) == 0:
            code = repr("")
        elif "|" in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for pipe in pipes[1:]:
                (func, params) = self._parse_pipe(pipe)
                self._variable(func, self._all_vars)

                params_code = []
                for p in params:
                    params_code.append(self._expr_code(p.strip()))
                if params_code:
                    code = "c_{0}({1},{2})".format(func, code, ",".join(params_code))
                else:
                    code = "c_{0}({1})".format(func, code)

        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots({0}, {1})".format(code, args)

        elif self._isint(expr):
            code = repr(expr)

        else:
            self._variable(expr, self._all_vars)
            code = "c_{0}".format(expr)

        return code

    def _isint(self, expr):
        """ Test for an integer. """
        try:
            value = int(expr)
            return True
        except ValueError as e:
            return False

    def _syntax_error(self, msg, thing):
        """ Raise an error if something is wrong. """

        raise Error("{0}: {1}".format(msg, repr(thing)))

    def _variable(self, what, where):
        """ Track a varialbe that is used. """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", what):
            self._syntax_error("Not a valid name", what)
    
        if not where is None:
            where.add(what)

    def render(self, context=None):
        """ Render teh template. """
        render_context= dict(self._context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _do_dots(self, value, *dots):
        """ Evaluate dotted expressions. """
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value

    def _parse_pipe(self, pipe):
        """ Parse a pipe """
        pipe = pipe.strip()

        start = pipe.find("(")
        if start == -1:
            return (pipe, [])
        
        func = pipe[0:start]
        end = pipe.rfind(")")
        if end != len(pipe) - 1:
            raise self._syntax_error("Don't understand pipe", pipe)

        params = pipe[start + 1:end].split(",")

        return (func.strip(), params)
            
                    

class Error(Exception):
    pass


# Application portion
################################################################################

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


