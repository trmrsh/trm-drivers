"""
trm.drivers is all to do with providing GUI interfaces to running the
high-speed cameras, ULTRASPEC, ULTRACAM etc. The most developed script is
usdriver.py for ULTRASPEC.

The general structure is to group related buttons and information fields into
discrete widgets, which translate into equivalent classes at the code level,
e.g. trm.drivers.drivers.Astroframe. The compartmentalisation suggested by
this is rather illusory as there is typically a need to interact between such
widgets. One way to do this would have been with callbacks, but in the end I
decided it was much easier to use a set of globals. Many of the classes therefore
really serve just to loosely group functions associated with them.
"""
