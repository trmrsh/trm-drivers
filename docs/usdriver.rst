Operation of the *usdriver* graphical user interface
==================================================

The main interaction an observer will have with ULTRASPEC is through the
graphical user interface (GUI) called *usdriver*. *usdriver* handles the 
setting up of CCD windows, exposure times, the input of target information,
talking to the telescope, filter wheel and focal plane slide.

How it works
------------

*usdriver* provides an interface to the software that runs ULTRASPEC by
talking to two servers called the "camera" and "data" servers. The two 
critical actions during observing are the **Post** and **Start** operations.
**Post** sends the current setup to the servers; **Start** actually implements
what you have sent. You cannot start without having posted. If you haven't
posted, then the servers won't have the configuration that you have setup
in *usdriver*.

This has the great benefit that you can devise setups in *usdriver* while
a run is going and you will have no effect. Indeed in usual operation, if a
run is going, you won't be allowed to **Post** whatever setup you currently
have.

Getting started
---------------

*usdriver* is run from the rack PC. From the data PC, open a terminal on the
rack PC, and type::
 
 usdriver.py

This will load a configuration file which will described later. 

GUI architecture
----------------

The GUI is arranged into a set of named sub-frames. Each of these tries to
group related items together. Here is the list of all of these sub-frames::

Count & S/N estimator:
  shows count rates and signal-to-noise estimated according to user input

Run status:
  information about the current or most recently completed run.

Run parameters:
  user input such as the target name and programme ID which will be
  added to the data for a given run.

Instrument parameters:
  the setup of the camera; window positions, binning factors and the like.

Time & Sky:
  information upon the current time and position of the Sun and Moon

Instrument setup:
  commands for setting up the servers

Focal plane slide:
  commands for moving the focal plane slide

Observing commands:
  commands to be used when observing

Command log:
  window which reports on what has happened

Response log:
  window relaying output from the servers

