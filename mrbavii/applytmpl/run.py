"""Function for setuptools entry point. """

__author__      = "Brian Allen Vanderburg II"
__copyright__   = "Copyright 2019"
__license__     = "Apache License 2.0"


from .app import App

def run():
    """ Run the application. """
    app = App()
    app.run()

