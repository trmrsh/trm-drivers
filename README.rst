README
======

'drivers' provides GUIs to run the high-speed astronomical cameras ULTRACAM
and ULTRASPEC. It is currently under active development and chock-full of
bugs. 'drivers' is written in Python and is based on Tkinter. It could be a
useful example of a fairly complex GUI as it contains examples of talking to
servers, subprocesses, and simultaneous operation as a server which raises
issues to do with threading.  If you want to look at it for this purpose, it
is worth knowing that it will operate in the absence of the cameras although
some operations are not possible of course.

Installation
------------

The software is written as much as possible to make use of core Python 
components. The one third-party requirement is pyephem 
(http://rhodesmill.org/pyephem/), a package for astronomical calculations.
Once you have installed this, the usual::

 python setup.py install

or if you don't have root access::

 python setup.py install --prefix=my_own_installation_directory


Tom Marsh
