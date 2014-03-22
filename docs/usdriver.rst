Operation of the *usdriver* graphical user interface
==================================================

The main interaction an observer will have with ULTRASPEC is through the
graphical user interface (GUI) called *usdriver*. *usdriver* handles the 
setting up of CCD windows, exposure times, the input of target information,
talking to the telescope, filter wheel and focal plane slide.

How it works
------------

*usdriver* provides an interface to the software that runs ULTRASPEC by
talking to two servers called the "camera" and "data" servers. When you press
the **Start** button, an XML file containing your setup (called the
*application*) is sent to the servers and then a command is sent to start
exposing.

This means that you can change the setup in *usdriver* while
a run is going and you will have no effect. The real actions only
occur once **Start** has been pressed.

Getting started
---------------

*usdriver* is run from the rack PC. From the data PC, open a terminal on the
rack PC (double click the terminal icon labelled "rack"). Usually one then 
types::
 
 start_uspec.py

or::

 start_uspec.py -q

with the latter configuration suppressing messages which may slow the fastest
frame rates. *start_uspec* is actually a shell script that starts the servers
as well as usdriver. 

GUI architecture
----------------

The GUI is arranged into a set of named sub-frames. Each of these tries to
group related items together. Here is the list of all of these sub-frames, in
approximately the order you might encounter them::

Instrument setup:
  commands for setting up the servers. In the most common case, this is
  simply a matter of pressing *Initialise* on first starting the GUI.

Instrument parameters:
  the setup of the camera; window positions, binning factors and the
  like. These will be sent to ULTRASPEC when **Start** is pressed.

Next run parameters:
  user input such as the target name and programme ID which will be
  added to the data for the next run, once **Start** is pressed.

Observing commands:
  commands to be used when observing. They should be obvious.

Count & S-to-N estimator:
  shows count rates and signal-to-noise estimated according to the current
  instrument parameters and some additional target and condition information.

Current run & telescope status:
  information about the current (or most recently completed) run.

Time & Sky:
  information upon the current time and position of the Sun and Moon

Focal plane slide:
  commands for moving the focal plane slide

Command log:
  window which reports on what has happened

Response log:
  window relaying output from the servers

Instrument Parameters
---------------------

This section is where you define the mode of operation of the CCD, the
windows, the exposure time etc. The usage should mostly be obvious but
here are the explicit meanings of each entry::

 Mode :
    ULTRASPEC operates in two basic modes, *Windows* (Wins for short) and
    *Drift*. *Windows* allows up to 4 windows which can be placed anywhere as
    long as they do not overlap directly, or in their Y extents. The latter
    means that if a window entends from Y=101 to 200 say, then no other window
    can have any Y pixels in this interval. In *Drift* mode you can have 2
    windows that must have the *same* Y pixel range.

 Clear : 
    in normal operation, while one is reading the image from the masked
    area, one simultaneously exposes the image area. Once the reading of the
    masked area has completed, one can carry on exposing, by setting an
    "exposure delay" (see below), then transfer the image into the masked area
    for reading. The total exposure is then the sum of the time taken to read
    the masked area containing the previous exposure plus whatever delay you
    specify. Sometimes this is too long (bright targets) and in such cases one
    might want to invoke the *clear* option, which immediately after the
    readout of the masked area, clears the imaging area, so that only the
    exposure delay counts in terms of adding photons. This is often useful for
    flats and standard stars. It is normally not what you want on science
    targets of course, because you lose all the photons gathered during the
    reading of the masked area. The effect of this is obvious if you look at
    the duty cycle reported in the *Count & S-to-N estimator* section when you
    toggle the clear flag.






