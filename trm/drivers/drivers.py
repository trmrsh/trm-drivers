#!/usr/bin/env python

"""
As far as possible drivers contains classes of generic use, such as
PosInt for positive integer input. See e.g. 'uspec' for more instrument
dependent components.
"""

from __future__ import print_function
import sys
import traceback
import socket, errno
import Tkinter as tk
import tkFont, tkFileDialog
import xml.etree.ElementTree as ET
import urllib, urllib2
import logging, time, datetime
import BaseHTTPServer, SocketServer
import threading, subprocess
import math, json

# third party
import ephem

# mine
import tcs
import slide
import globals as g
import lakeshore as lake

def addStyle(root):
    """
    Styles the GUI: global fonts and colours.
    """

    # Default font
    g.DEFAULT_FONT = tkFont.nametofont("TkDefaultFont")
    g.DEFAULT_FONT.configure(size=10, weight='bold')
    root.option_add('*Font', g.DEFAULT_FONT)

    # Menu font
    g.MENU_FONT = tkFont.nametofont("TkMenuFont")
    g.MENU_FONT.configure(size=10)
    root.option_add('*Menu.Font', g.MENU_FONT)

    # Entry font
    g.ENTRY_FONT = tkFont.nametofont("TkTextFont")
    g.ENTRY_FONT.configure(size=10)
    root.option_add('*Entry.Font', g.ENTRY_FONT)

    # position and size
    #    root.geometry("320x240+325+200")

    # Default colours. Note there is a difference between
    # specifying 'background' with a capital B or lowercase b
    root.option_add('*background', g.COL['main'])
    root.option_add('*HighlightBackground', g.COL['main'])
    root.config(background=g.COL['main'])

class Boolean(tk.IntVar):
    """
    Defines an object representing one of the boolean configuration
    parameters to allow it to be interfaced with the menubar easily.

    If defined, callback is run with the new value of the flag as its
    argument
    """
    def __init__(self, flag, callback=None):
        tk.IntVar.__init__(self)
        self.set(g.cpars[flag])
        self.trace('w', self._update)
        self.flag = flag
        self.callback = callback

    def _update(self, *args):
        if self.get():
            g.cpars[self.flag] = True
        else:
            g.cpars[self.flag] = False
        if self.callback:
            self.callback(g.cpars[self.flag])


class IntegerEntry(tk.Entry):
    """
    Defines an Entry field which only accepts integer input.
    This is the base class for several varieties of integer
    input fields and defines much of the feel to do with holding
    the mouse buttons down etc.
    """

    def __init__(self, master, ival, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid (the latter case requires some other checking)
        kw      -- optional keyword arguments that can be used for
                   an Entry.
        """
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        tk.Entry.__init__(self, master, **kw)
        self._variable = tk.StringVar()
        self._value    = str(int(ival))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank   = blank
        self.set_bind()

        # Nasty stuff to do with holding mouse
        # buttons down
        self._leftMousePressed        = False
        self._shiftLeftMousePressed   = False
        self._rightMousePressed       = False
        self._shiftRightMousePressed  = False
        self._mouseJustPressed        = True

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                int(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns integer value, if possible, None if not.
        """
        try:
            return int(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self._value = str(int(num))
        self._variable.set(self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            int(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        # Arrow keys and enter
        self.bind('<Up>', lambda e : self.add(1))
        self.bind('<Down>', lambda e : self.sub(1))
        self.bind('<Shift-Up>', lambda e : self.add(10))
        self.bind('<Shift-Down>', lambda e : self.sub(10))
        self.bind('<Control-Up>', lambda e : self.add(100))
        self.bind('<Control-Down>', lambda e : self.sub(100))

        # Mouse buttons: bit complex since they don't automatically
        # run in continuous mode like the arrow keys
        self.bind('<ButtonPress-1>', self._leftMouseDown)
        self.bind('<ButtonRelease-1>', self._leftMouseUp)
        self.bind('<Shift-ButtonPress-1>', self._shiftLeftMouseDown)
        self.bind('<Shift-ButtonRelease-1>', self._shiftLeftMouseUp)
        self.bind('<Control-Button-1>', lambda e : self.add(100))

        self.bind('<ButtonPress-3>', self._rightMouseDown)
        self.bind('<ButtonRelease-3>', self._rightMouseUp)
        self.bind('<Shift-ButtonPress-3>', self._shiftRightMouseDown)
        self.bind('<Shift-ButtonRelease-3>', self._shiftRightMouseUp)
        self.bind('<Control-Button-3>', lambda e : self.sub(100))

        self.bind('<Double-Button-1>', self._dadd1)
        self.bind('<Double-Button-3>', self._dsub1)
        self.bind('<Shift-Double-Button-1>', self._dadd10)
        self.bind('<Shift-Double-Button-3>', self._dsub10)
        self.bind('<Control-Double-Button-1>', self._dadd100)
        self.bind('<Control-Double-Button-3>', self._dsub100)

        self.bind('<Enter>', self._enter)

    def _leftMouseDown(self, event):
        self._leftMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _leftMouseUp(self, event):
        if self._leftMousePressed:
            self._leftMousePressed = False
            self.after_cancel(self.after_id)

    def _shiftLeftMouseDown(self, event):
        self._shiftLeftMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _shiftLeftMouseUp(self, event):
        if self._shiftLeftMousePressed:
            self._shiftLeftMousePressed = False
            self.after_cancel(self.after_id)

    def _rightMouseDown(self, event):
        self._rightMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _rightMouseUp(self, event):
        if self._rightMousePressed:
            self._rightMousePressed = False
            self.after_cancel(self.after_id)

    def _shiftRightMouseDown(self, event):
        self._shiftRightMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _shiftRightMouseUp(self, event):
        if self._shiftRightMousePressed:
            self._shiftRightMousePressed = False
            self.after_cancel(self.after_id)

    def _pollMouse(self):
        """
        Polls @10Hz, with a slight delay at the
        start.
        """
        if self._mouseJustPressed:
            delay = 300
            self._mouseJustPressed = False
        else:
            delay = 100

        if self._leftMousePressed:
            self.add(1)
            self.after_id = self.after(delay, self._pollMouse)

        if self._shiftLeftMousePressed:
            self.add(10)
            self.after_id = self.after(delay, self._pollMouse)

        if self._rightMousePressed:
            self.sub(1)
            self.after_id = self.after(delay, self._pollMouse)

        if self._shiftRightMousePressed:
            self.sub(10)
            self.after_id = self.after(delay, self._pollMouse)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')

        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<ButtonPress-1>')
        self.unbind('<ButtonRelease-1>')
        self.unbind('<ButtonPress-3>')
        self.unbind('<ButtonRelease-3>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Double-Button-1>')
        self.unbind('<shiftDouble-Button-3>')
        self.unbind('<Control-Double-Button-1>')
        self.unbind('<Control-Double-Button-3>')
        self.unbind('<Enter>')


    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd1(self, event):
        self.add(1)
        return 'break'

    def _dsub1(self, event):
        self.sub(1)
        return 'break'

    def _dadd10(self, event):
        self.add(10)
        return 'break'

    def _dsub10(self, event):
        self.sub(10)
        return 'break'

    def _dadd100(self, event):
        self.add(100)
        return 'break'

    def _dsub100(self, event):
        self.sub(100)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)

class PosInt (IntegerEntry):
    """
    Provide positive or 0 integer input. Basically
    an IntegerEntry with one or two extras.
    """

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(0))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < 0:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(max(0,val))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(max(0,val))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < 0:
                return False
            else:
                return True
        except:
            return False

class RangedInt (IntegerEntry):
    """
    Provides range-checked integer input.
    """
    def __init__(self, master, ival, imin, imax, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        imin    -- minimum value
        imax    -- maximum value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        kw      -- keyword arguments
        """
        self.imin = imin
        self.imax = imax
        IntegerEntry.__init__(self, master, ival, checker, blank, **kw)
        self.bind('<Next>', lambda e : self.set(self.imin))
        self.bind('<Prior>', lambda e : self.set(self.imax))

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(self.imin))
        self.bind('<Prior>', lambda e : self.set(self.imax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < self.imin or v > self.imax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(min(self.imax,max(self.imin,val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.imax,max(self.imin,val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < self.imin or v > self.imax:
                return False
            else:
                return True
        except:
            return False

class RangedMint (RangedInt):
    """
    This is the same as RangedInt but locks to multiples
    """

    def __init__(self, master, ival, imin, imax, mfac, checker, blank, **kw):
        """
        mfac must be class that support 'value()' to return an integer value.
        to allow it to be updated
        """
        self.mfac = mfac
        RangedInt.__init__(self, master, ival, imin, imax, checker, blank, **kw)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_bind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))

    def set_unbind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def add(self, num):
        """
        Adds num to the current value, jumping up the next
        multiple of mfac if the result is not a multiple already
        """
        try:
            val = self.value() + num
        except:
            val = num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk + 1)
            elif num < 0:
                val = chunk*(val // chunk)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value, forcing the result to be within
        range and a multiple of mfac
        """
        try:
            val = self.value() - num
        except:
            val = -num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk)
            elif num < 0:
                val = chunk*(val // chunk + 1)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            chunk = self.mfac.value()
            if v < self.imin or v > self.imax or (v % chunk != 0):
                return False
            else:
                return True
        except:
            return False

    def _min(self):
        chunk = self.mfac.value()
        mval  = chunk*(self.imin // chunk)
        return mval+chunk if mval < self.imin else mval

    def _max(self):
        chunk = self.mfac.value()
        return chunk*(self.imax // chunk)

class ListInt (IntegerEntry):
    """
    Provides integer input allowing only a finite list of integers.
    Needed for the binning factors.
    """
    def __init__(self, master, ival, allowed, checker, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        allowed -- list of allowed values. Will be checked for uniqueness
        checker -- command that is run on any change to the entry
        kw      -- keyword arguments
        """
        if ival not in allowed:
            raise DriverError('drivers.ListInt: value = ' + str(ival) +
                              ' not in list of allowed values.')
        if len(set(allowed)) != len(allowed):
            raise DriverError('drivers.ListInt: not all values unique'+
                              ' in allowed list.')

        # we need to maintain an index of which integer has been selected
        self.allowed = allowed
        self.index   = allowed.index(ival)
        IntegerEntry.__init__(self, master, ival, checker, False, **kw)
        self.set_bind()


    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')

        self.bind('<Button-1>', lambda e : self.add(1))
        self.bind('<Button-3>', lambda e : self.sub(1))
        self.bind('<Up>', lambda e : self.add(1))
        self.bind('<Down>', lambda e : self.sub(1))
        self.bind('<Enter>', self._enter)
        self.bind('<Next>', lambda e : self.set(self.allowed[0]))
        self.bind('<Prior>', lambda e : self.set(self.allowed[-1]))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Enter>')
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            v = int(value)
            if v not in self.allowed:
                return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        self.index = max(0,min(len(self.allowed)-1,self.index+num))
        self.set(self.allowed[self.index])

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        self.index = max(0,min(len(self.allowed)-1,self.index-num))
        self.set(self.allowed[self.index])

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        return True

class FloatEntry(tk.Entry):
    """
    Defines an Entry field which only accepts floating point input.
    """

    def __init__(self, master, fval, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid (the latter case requires some other checking)
        kw      -- optional keyword arguments that can be used for
                   an Entry.
        """
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        tk.Entry.__init__(self, master, **kw)
        self._variable = tk.StringVar()
        self._value = str(float(fval))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank   = blank
        self.set_bind()

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                float(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns float value, if possible, None if not.
        """
        try:
            return float(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self._value = str(float(num))
        self._variable.set(self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            float(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        self.bind('<Button-1>', lambda e : self.add(0.1))
        self.bind('<Button-3>', lambda e : self.sub(0.1))
        self.bind('<Up>', lambda e : self.add(0.1))
        self.bind('<Down>', lambda e : self.sub(0.1))
        self.bind('<Shift-Up>', lambda e : self.add(1))
        self.bind('<Shift-Down>', lambda e : self.sub(1))
        self.bind('<Control-Up>', lambda e : self.add(10))
        self.bind('<Control-Down>', lambda e : self.sub(10))
        self.bind('<Double-Button-1>', self._dadd)
        self.bind('<Double-Button-3>', self._dsub)
        self.bind('<Shift-Button-1>', lambda e : self.add(1))
        self.bind('<Shift-Button-3>', lambda e : self.sub(1))
        self.bind('<Control-Button-1>', lambda e : self.add(10))
        self.bind('<Control-Button-3>', lambda e : self.sub(10))
        self.bind('<Enter>', self._enter)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<Enter>')

    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(0.1)
        return 'break'

    def _dsub(self, event):
        self.sub(0.1)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)

class RangedFloat (FloatEntry):
    """
    Provides range-checked float input.
    """
    def __init__(self, master, fval, fmin, fmax, checker,
                 blank, allowzero=False, **kw):
        """
        master    -- enclosing widget
        fval      -- initial float value
        fmin      -- minimum value
        fmax      -- maximum value
        checker   -- command that is run on any change to the entry
        blank     -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        allowzero -- if 0 < fmin < 1 input of numbers in the range fmin to 1
                     can be difficult unless 0 is allowed even though it is
                     an invalid value.
        kw        -- keyword arguments
        """
        self.fmin = fmin
        self.fmax = fmax
        FloatEntry.__init__(self, master, fval, checker, blank, **kw)
        self.bind('<Next>', lambda e : self.set(self.fmin))
        self.bind('<Prior>', lambda e : self.set(self.fmax))
        self.allowzero = allowzero

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        FloatEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(self.fmin))
        self.bind('<Prior>', lambda e : self.set(self.fmax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        FloatEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = float(value)
                if (self.allowzero and v != 0 and v < self.fmin) or \
                        (not self.allowzero and v < self.fmin) or v > self.fmax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(min(self.fmax,max(self.fmin,val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.fmax,max(self.fmin,val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = float(self._value)
            if v < self.fmin or v > self.fmax:
                return False
            else:
                return True
        except:
            return False


class Expose (RangedFloat):
    """
    Special entry field for exposure times designed to return
    an integer number of 0.1ms increments.
    """
    def __init__(self, master, fval, fmin, fmax, checker, **kw):
        """
        master  -- enclosing widget
        fval    -- initial value, seconds
        fmin    -- minimum value, seconds
        fmax    -- maximum value, seconds
        checker -- command that is run on any change to the entry

        fval, fmin and fmax must be multiples of 0.0001
        """
        if abs(round(10000*fval)-10000*fval) > 1.e-12:
            raise DriverError(
                'drivers.Expose.__init__: fval must be a multiple of 0.0001')
        if abs(round(10000*fmin)-10000*fmin) > 1.e-12:
            raise DriverError(
                'drivers.Expose.__init__: fmin must be a multiple of 0.0001')
        if abs(round(10000*fmax)-10000*fmax) > 1.e-12:
            raise DriverError(
                'drivers.Expose.__init__: fmax must be a multiple of 0.0001')

        RangedFloat.__init__(self, master, fval, fmin,
                             fmax, checker, True, **kw)

    def validate(self, value):
        """
        This prevents setting any value more precise than 0.0001
        """
        try:
            # trap blank fields here
            if value:
                v = float(value)
                if (v != 0 and v < self.fmin) or v > self.fmax:
                    return None
                if abs(round(10000*v)-10000*v) > 1.e-12:
                    return None
            return value
        except ValueError:
            return None

    def ivalue(self):
        """
        Returns integer value in units of 0.1ms, if possible, None if not.
        """
        try:
            return int(round(10000*float(self._value)))
        except:
            return None

    def set_min(self, fmin):
        """
        Updates minimum value
        """
        if round(10000*fmin) != 10000*fmin:
            raise DriverError('drivers.Expose.set_min: ' + \
                                  'fmin must be a multiple of 0.0001')
        self.fmin = fmin
        self.set(self.fmin)

class TextEntry (tk.Entry):
    """
    Sub-class of Entry for basic text input. Not a lot to
    it but it keeps things neater and it has a check for
    blank entries.
    """

    def __init__(self, master, width, callback=None):
        """
        master  : the widget this gets placed inside
        """

        # Define a StringVar, connect it to the callback, if there is one
        self.val = tk.StringVar()
        if callback is not None:
            self.val.trace('w', callback)
        tk.Entry.__init__(self, master, textvariable=self.val, \
                              fg=g.COL['text'], bg=g.COL['main'], width=width)

        # Control input behaviour.
        self.bind('<Enter>', lambda e : self.focus())

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Returns value.
        """
        return self.val.set(text)

    def ok(self):
        if self.value() == '' or self.value().isspace():
            return False
        else:
            return True

class Choice(tk.OptionMenu):
    """
    Menu choice class.
    """
    def __init__(self, master, options, initial=None, width=0, checker=None):
        """
        master  : containing widget
        options : list of strings
        initial : the initial one to select. If None will default to the first.
        width   : minimum character width to use. Width set will be large
                  enough for longest option.
        checker : callback to run on any change of selection.
        """

        self.val = tk.StringVar()
        if initial is None:
            self.val.set(options[0])
        else:
            self.val.set(initial)
        tk.OptionMenu.__init__(self, master, self.val, *options)
        width = max(width, reduce(max, [len(s) for s in options]))
        self.config(width=width, font=g.ENTRY_FONT)
        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())


class Radio(tk.Frame):
    """
    Left-to-right radio button class. Lays out buttons in a grid
    from left-to-right. Has a max number of columns after which it
    will jump to left of next row and start over.
    """
    def __init__(self, master, options, ncmax, checker=None,
                 values=None, initial=0):
        """
        master : containing widget
        options : array of option strings, in order. These are the choices
        presented to the user.
        ncmax : max number of columns (flows onto next row if need be)
        checker : callback to be run after any change
        values : array of string values used by the code internally.
        If 'None', the value from 'options' will be used.
        initial : index of initial value to set.
        """
        tk.Frame.__init__(self, master)
        if values is not None and len(values) != len(options):
            raise DriverError('drvs.Radio.__init__: values and ' + \
                                  'options must have same length')

        self.val = tk.StringVar()
        if values is None:
            self.val.set(options[initial])
        else:
            self.val.set(values[initial])

        row = 0
        col = 0
        self.buttons = []
        for nopt, option in enumerate(options):
            if values is None:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   font=g.ENTRY_FONT,value=option))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            else:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   font=g.ENTRY_FONT,value=values[nopt]))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            col += 1
            if col == ncmax:
                row += 1
                col = 0

        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        self.val.set(choice)

    def disable(self):
        for b in self.buttons:
            b.configure(state='disable')

    def enable(self):
        for b in self.buttons:
            b.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())

class OnOff(tk.Checkbutton):
    """
    On or Off choice
    """

    def __init__(self, master, value, checker=None):
        self.val = tk.IntVar()
        self.val.set(value)
        tk.Checkbutton.__init__(
            self, master, variable=self.val, command=checker)

    def __call__(self):
        return self.val.get()

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def set(self, state):
        self.val.set(state)

def overlap(xl1,yl1,nx1,ny1,xl2,yl2,nx2,ny2):
    """
    Determines whether two windows overlap
    """
    return (xl2 < xl1+nx1 and xl2+nx2 > xl1 and \
                yl2 < yl1+ny1 and yl2+ny2 > yl1)

def saveXML(root):
    """
    Saves the current setup to disk.

    root : (xml.etree.ElementTree.Element)
    The current setup.
    """
    fname = tkFileDialog.asksaveasfilename(
        defaultextension='.xml', filetypes=[('xml files', '.xml'),],
        initialdir=g.cpars['app_directory'])
    if not fname:
        g.clog.warn('Aborted save to disk')
        return False
    tree = ET.ElementTree(root)
    tree.write(fname)
    g.clog.info('Saved setup to' + fname)
    return True

def postXML(root):
    """
    Posts the current setup to the camera and data servers.

    root : (xml.etree.ElementTree.Element)
    The current setup.

    """
    g.clog.debug('Entering postXML')

    if not g.cpars['cdf_servers_on']:
        g.clog.warn('postXML: servers are not active')
        return False

    # Write setup to an xml string
    sxml = ET.tostring(root)

    # Send the xml to the camera server
    url = g.cpars['http_camera_server'] + g.HTTP_PATH_CONFIG
    g.clog.debug('Camera URL = ' + url)

    opener = urllib2.build_opener()
    g.clog.debug('content length = ' + str(len(sxml)))
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5)
    csr = ReadServer(response.read())
    g.rlog.warn(csr.resp())
    if not csr.ok:
        g.clog.warn('Camera response was not OK')
        return False

    # Send the xml to the data server
    url = g.cpars['http_data_server'] + g.HTTP_PATH_CONFIG
    g.clog.debug('Data server URL = ' + url)
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5) # ?? need to check whether this is needed
    fsr = ReadServer(response.read())
    g.rlog.warn(fsr.resp())
    if not csr.ok:
        g.clog.warn('Fileserver response was not OK')
        return False

    g.clog.debug('Leaving postXML')
    return True

class ActButton(tk.Button):
    """
    Base class for action buttons. This keeps an internal flag
    representing whether the button should be active or not.
    Whether it actually is, might be overridden, but the internal
    flag tracks the (potential) activity status allowing it to be
    reset. The 'expert' flag controls whether the activity status
    will be overridden. The button starts out in non-expert mode by
    default. This can be switched with setExpert, setNonExpert.
    """

    def __init__(self, master, width, callback=None, **kwargs):
        """
        master   : containing widget
        width    : width in characters of the button
        callback : function that is called when button is pressed
        bg       : background colour
        kwargs   : keyword arguments
        """
        tk.Button.__init__(
            self, master, fg='black', width=width,
            command=self.act, **kwargs)

        # store some attributes. other anc calbback are obvious.
        # _active indicates whether the button should be enabled or disabled
        # _expert indicates whether the activity state should be overridden so
        #         that the button is enabled in any case (if set True)
        self.callback = callback
        self._active  = True
        self._expert  = False

    def enable(self):
        """
        Enable the button, set its activity flag.
        """
        self.config(state='normal')
        self._active = True

    def disable(self):
        """
        Disable the button, if in non-expert mode;
        unset its activity flag come-what-may.
        """
        if not self._expert:
            self.config(state='disable')
        self._active = False

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        self._expert = True
        self.configure(state='normal')

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carry out the action associated with the button.
        Override in derived classes
        """
        self.callback()

class Stop(ActButton):
    """
    Class defining the 'Stop' button's operation
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        ActButton.__init__(self, master, width, bg=g.COL['stop'], text='Stop')

        # flags to help with stopping in background
        self.stopped_ok = True
        self.stopping   = False

    def enable(self):
        """
        Enable the button.
        """
        ActButton.enable(self)
        self.config(bg=g.COL['stop'])

    def disable(self):
        """
        Disable the button, if in non-expert mode.
        """
        ActButton.disable(self)
        if self._expert:
            self.config(bg=g.COL['stop'])
        else:
            self.config(bg=g.COL['stopD'])

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        ActButton.setExpert(self)
        self.config(bg=g.COL['stop'])

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carries out the action associated with Stop button
        """

        g.clog.debug('Stop pressed')

        def stop_in_background():
            try:
                self.stopping   = True
                if execCommand('EX,0'):
                    # Report that run has stopped
                    g.clog.info('Run stopped')
                    self.stopped_ok = True
                else:
                    g.clog.warn('Failed to stop run')
                    self.stopped_ok = False
                self.stopping   = False
            except Exception, err:
                g.clog.warn('Failed to stop run. Error = ' + str(err))
                self.stopping   = False
                self.stopped_ok = False

        # stopping can take a while during which the GUI freezes so run in
        # background.
        t = threading.Thread(target=stop_in_background)
        t.daemon = True
        t.start()

    def check(self):
        """
        Checks the status of the stop exposure command
        This is run in background and can take a few seconds
        """

        if self.stopped_ok:
            # Exposure stopped OK; modify buttons
            self.disable()
            g.observe.start.enable()
            g.setup.resetSDSUhard.enable()
            g.setup.resetSDSUsoft.enable()
            g.setup.resetPCI.disable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.enable()

            # Stop exposure meter
            g.info.timer.stop()
            return True

        elif self.stopping:
            # Exposure in process of stopping
            # Disable lots of buttons
            self.disable()
            g.observe.start.disable()
            g.setup.resetSDSUhard.disable()
            g.setup.resetSDSUsoft.disable()
            g.setup.resetPCI.disable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()

            # wait a second before trying again
            self.after(1000, self.check)

        else:
            self.enable()
            g.observe.start.disable()
            g.setup.resetSDSUhard.disable()
            g.setup.resetSDSUsoft.disable()
            g.setup.resetPCI.disable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return False

class Target(tk.Frame):
    """
    Class wrapping up what is needed for a target name which
    is an entry field and a verification button. The verification
    button checks for simbad recognition and goes green or red
    according to the results. If no check has been made, it has
    a default colour.
    """
    def __init__(self, master, callback=None):
        tk.Frame.__init__(self, master)

        # Entry field, linked to a StringVar which is traced for
        # any modification
        self.val    = tk.StringVar()
        self.val.trace('w', self.modver)
        self.entry  = tk.Entry(
            self, textvariable=self.val, fg=g.COL['text'],
            bg=g.COL['main'], width=25)
        self.entry.bind('<Enter>', lambda e : self.entry.focus())

        # Verification button which accesses simbad to see if
        # the target is recognised.
        self.verify = tk.Button(
            self, fg='black', width=8, text='Verify',
            bg=g.COL['main'], command=self.act)
        self.entry.pack(side=tk.LEFT,anchor=tk.W)
        self.verify.pack(side=tk.LEFT,anchor=tk.W,padx=5)
        self.verify.config(state='disable')
        # track successed and failures
        self.successes = []
        self.failures  = []
        self.callback = callback

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Sets value.
        """
        return self.val.set(text)

    def disable(self):
        self.entry.configure(state='disable')
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['startD'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stopD'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
        else:
            self.verify.config(bg=g.COL['main'])
        self.verify.config(state='disable')

    def enable(self):
        self.entry.configure(state='normal')
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['start'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stop'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
        else:
            self.verify.config(bg=g.COL['main'])
        self.verify.config(state='normal')

    def ok(self):
        if self.val.get() == '' or self.val.get().isspace():
            return False
        else:
            return True

    def modver(self, *args):
        """
        Switches colour of verify button
        """
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['start'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stop'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
            self.verify.config(state='normal')
        else:
            self.verify.config(bg=g.COL['main'])
            self.verify.config(state='disable')

        if self.callback is not None:
            self.callback()

    def act(self):
        """
        Carries out the action associated with Verify button
        """

        tname = self.val.get()

        g.clog.info('Checking ' + tname + ' in simbad')
        try:
            ret = checkSimbad(tname)
            if len(ret) == 0:
                self.verify.config(bg=g.COL['stop'])
                g.clog.warn('No matches to "' + tname + '" found.')
                if tname not in self.failures:
                    self.failures.append(tname)
            elif len(ret) == 1:
                self.verify.config(bg=g.COL['start'])
                g.clog.info(tname + ' verified OK in simbad')
                g.clog.info('Primary simbad name = ' + ret[0]['Name'])
                if tname not in self.successes:
                    self.successes.append(tname)
            else:
                g.clog.warn('More than one match to "' + tname + '" found')
                self.verify.config(bg=g.COL['stop'])
                if tname not in self.failures:
                    self.failures.append(tname)
        except URLError, e:
            g.clog.warn('Simbad lookup timed out')
        except socket.timeout:
            g.clog.warn('Simbad lookup timed out')

class ReadServer(object):
    """
    Class to field the xml responses sent back from the ULTRACAM servers

    Set the following attributes:

     root    : the xml.etree.ElementTree.Element at the root of the xml
     camera  : true if the response was from the camera server (else filesave)
     ok      : whether response is OK or not (True/False)
     err     : message if ok == False
     state   : state of the camera. Possibilties are:
               'IDLE', 'BUSY', 'ERROR', 'ABORT', 'UNKNOWN'
     run     : current or last run number
    """

    def __init__(self, resp):
        # Store the entire response
        self.root = ET.fromstring(resp)

        # Identify the source: camera or filesave
        cfind = self.root.find('source')
        if cfind is None:
            self.camera = None
            self.ok     = False
            self.err    = 'Could not identify source'
            self.state  = None
            return

        self.camera = cfind.text.find('Camera') > -1

        # strip excess stuff
        camstat = self.root.find('camera_status')
        if camstat is not None:
            self.root.remove(camstat)

        filestat = self.root.find('filesave_status')
        if filestat is not None:
            self.root.remove(filestat)

        # Work out whether it was happy
        sfind = self.root.find('status')
        if sfind is None:
            self.ok    = False
            self.err   = 'Could not identify status'
            self.state = None
            return

        att = sfind.attrib
        if 'software' in att and 'errnum' in att:
            self.ok = att['software'] == 'OK'
            if self.ok:
                self.err = ''
            else:
                self.err = 'server errnum = ' + str(att['errnum'])

        # Determine state of the camera / data server
        sfind = self.root.find('state')
        if sfind is None:
            self.ok     = False
            self.err    = 'Could not identify state'
            self.state  = None
            return

        if self.camera:
            self.state = sfind.attrib['camera']
        else:
            self.state = sfind.attrib['server']

        # Find current run number (set it to 0 if we fail)
        # this only works for  the 'fstatus' command as
        # opposed to 'status' for which the above works
        sfind = self.root.find('lastfile')
        if sfind is not None and 'path' in sfind.attrib:
            self.run = int(sfind.attrib['path'][-3:])
        else:
            self.run = 0

    def resp(self):
        return ET.tostring(self.root)

def execCommand(command):
    """
    Executes a command by sending it to the camera server

    Arguments:

      command : (string)
           the command (see below)

    Possible commands are:

      GO   : starts a run
      ST   : stops a run
      EX,0 : stops a run
      RCO  : resets the timing board (SDSU hardware reset)
      RS   : resets the timing board (SDSU software reset)
      RST  : resets the PCI board (software)
      SRS  :
      RM,X,0x80: to get version

    Returns True/False according to whether the command
    succeeded or not.
    """
    if not g.cpars['cdf_servers_on']:
        g.clog.warn('execCommand: servers are not active')
        return False

    try:
        url = g.cpars['http_camera_server'] + g.HTTP_PATH_EXEC + \
            '?' + command
        g.clog.info('execCommand, command = "' + command + '"')
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())

        g.rlog.info('Camera response =\n' + rs.resp())
        if rs.ok:
            g.clog.info('Response from camera server was OK')
            return True
        else:
            g.clog.warn('Response from camera server was not OK')
            g.clog.warn('Reason: ' + rs.err)
            return False
    except urllib2.URLError, err:
        g.clog.warn('execCommand failed')
        g.clog.warn(str(err))

    return False

def execServer(name, app):
    """
    Sends application to a server

    Arguments:

      name : (string)
         'camera' or 'data' for the camera or data server

      app : (string)
           the appication name

    Returns True/False according to success or otherwise
    """
    if not g.cpars['cdf_servers_on']:
        g.clog.warn('execServer: servers are not active')
        return False

    if name == 'camera':
        url = g.cpars['http_camera_server'] + g.HTTP_PATH_CONFIG + \
            '?' + app
    elif name == 'data':
        url = g.cpars['http_data_server'] + g.HTTP_PATH_CONFIG + '?' + app
    else:
        raise DriverError('Server name = ' + name + ' not recognised.')

    g.clog.debug('execServer, url = ' + url)

    response = urllib2.urlopen(url)
    rs  = ReadServer(response.read())
    if not rs.ok:
        g.clog.warn('Response from ' + name + ' server not OK')
        g.clog.warn('Reason: ' + rs.err)
        return False

    g.clog.debug('execServer command was successful')
    return True

def execRemoteApp(app):
    """
    Executes a remote application by sending it first to the
    camera and then to the data server.

    Arguments:

      app : (string)
           the application command (see below)

    Returns True/False according to whether the command
    succeeded or not.
    """

    return execServer('camera', app) and execServer('data', app)

class ResetSDSUhard(ActButton):
    """
    Class defining the 'Reset SDSU hardware' button
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        ActButton.__init__(self, master, width, text='Reset SDSU hardware')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU hardware button
        """

        g.clog.debug('Reset SDSU hardware pressed')

        if execCommand('RCO'):
            g.clog.info('Reset SDSU hardware succeeded')

            # adjust buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUsoft.disable()
            g.setup.resetPCI.enable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return True
        else:
            g.clog.warn('Reset SDSU hardware failed')
            return False

class ResetSDSUsoft(ActButton):
    """
    Class defining the 'Reset SDSU software' button
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        ActButton.__init__(self, master, width, text='Reset SDSU software')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU software button
        """
        g.clog.debug('Reset SDSU software pressed')

        if execCommand('RS'):
            g.clog.info('Reset SDSU software succeeded')

            # alter buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.disable()
            g.setup.resetPCI.enable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return True
        else:
            g.clog.warn('Reset SDSU software failed')
            return False

class ResetPCI(ActButton):
    """
    Class defining the 'Reset PCI' button
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        ActButton.__init__(self, master, width, text='Reset PCI')

    def act(self):
        """
        Carries out the action associated with the Reset PCI button
        """
        g.clog.debug('Reset PCI pressed')

        if execCommand('RST'):
            g.clog.info('Reset PCI succeeded')

            # alter buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.enable()
            g.setup.resetSDSUsoft.enable()
            g.setup.resetPCI.enable()
            g.setup.setupServers.enable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return True
        else:
            g.clog.warn('Reset PCI failed')
            return False

class SystemReset(ActButton):
    """
    Class defining the 'System Reset' button
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """

        ActButton.__init__(self, master, width, text='System Reset')

    def act(self):
        """
        Carries out the action associated with the System Reset
        """

        g.clog.debug('System Reset pressed')

        if execCommand('SRS'):
            g.clog.info('System Reset succeeded')

            # alter buttons here
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.disable()
            g.setup.resetSDSUsoft.disable()
            g.setup.resetPCI.enable()
            g.setup.setupServers.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return True
        else:
            g.clog.warn('System Reset failed')
            return False

class SetupServers(ActButton):
    """
    Class defining the 'Setup servers' button
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        ActButton.__init__(self, master, width, text='Setup servers')

    def act(self):
        """
        Carries out the action associated with the 'Setup servers' button
        """

        g.clog.debug('Setup servers pressed')
        tapp = g.TINS[g.cpars['telins_name']]['app']

        if execServer('camera', tapp) and \
                execServer('camera', g.cpars['instrument_app']) and \
                execServer('data', tapp) and \
                execServer('data', g.cpars['instrument_app']):

            g.clog.info('Setup servers succeeded')

            # alter buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.enable()
            g.setup.resetSDSUsoft.enable()
            g.setup.resetPCI.disable()
            g.setup.powerOn.enable()
            g.setup.powerOff.disable()

            # set flag indicating that the servers have been initialised
            g.cpars['servers_initialised'] = True
            return True
        else:
            g.clog.warn('Setup servers failed')
            return False

class PowerOn(ActButton):
    """
    Class defining the 'Power on' button's operation
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        ActButton.__init__(self, master, width, text='Power on')

    def act(self):
        """
        Power on action
        """
        g.clog.debug('Power on pressed')

        if execRemoteApp(g.cpars['power_on_app']) and execCommand('GO'):

            g.clog.info('Power on successful')

            # change other buttons
            self.disable()
            g.observe.start.enable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.enable()
            g.setup.resetSDSUsoft.enable()
            g.setup.resetPCI.disable()
            g.setup.setupServers.disable()
            g.setup.powerOff.enable()

            try:
                # now check the run number -- lifted from Java code; the wait
                # for the power on application to finish may not be needed
                n = 0
                while isRunActive() and n < 5:
                    n += 1
                    time.sleep(1)

                if isRunActive():
                    g.clog.warn(
                        'Timed out waiting for power on run to ' + \
                            'de-activate; cannot initialise run number. ' + \
                            'Tell trm if this happens')
                else:
                    g.info.run.configure(text='{0:03d}'.format(getRunNumber(True)))
            except Exception, err:
                g.clog.warn(\
                    'Failed to determine run number at start of run')
                g.clog.warn(str(err))
                g.info.run.configure(text='UNDEF')
            return True
        else:
            g.clog.warn('Power on failed\n')
            return False

class PowerOff(ActButton):
    """
    Class defining the 'Power off' button's operation
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """

        ActButton.__init__(self, master, width, text='Power off')
        self.disable()

    def act(self):
        """
        Power off action
        """
        g.clog.debug('Power off pressed')

        if execRemoteApp(g.cpars['power_off_app']) and execCommand('GO'):

            g.clog.info('Powered off SDSU')

            # alter buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.resetSDSUhard.enable()
            g.setup.resetSDSUsoft.enable()
            g.setup.resetPCI.disable()
            g.setup.setupServers.disable()
            g.setup.powerOn.enable()
            return True
        else:
            g.clog.warn('Power off failed')
            return False

class Initialise(ActButton):
    """
    Class defining the 'Initialise' button's operation
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """

        ActButton.__init__(self, master, width, text='Initialise')

    def act(self):
        """
        Initialise action
        """
        g.clog.debug('Initialise pressed')

        if not g.setup.systemReset.act():
            g.clog.warn('Initialise failed on system reset')
            return False

        if not g.setup.setupServers.act():
            g.clog.warn('Initialise failed on server setup')
            return False

        if not g.setup.powerOn.act():
            g.clog.warn('Initialise failed on power on')
            return False

        g.clog.info('Initialise succeeded')
        return True

class InstSetup(tk.LabelFrame):
    """
    Instrument setup frame.
    """

    def __init__(self, master):
        """
        master -- containing widget
        """
        tk.LabelFrame.__init__(
            self, master, text='Instrument setup', padx=10, pady=10)

        # Define all buttons
        width = 17
        self.resetSDSUhard = ResetSDSUhard(self, width)
        self.resetSDSUsoft = ResetSDSUsoft(self, width)
        self.resetPCI      = ResetPCI(self, width)
        self.systemReset   = SystemReset(self, width)
        self.setupServers  = SetupServers(self, width)
        self.powerOn       = PowerOn(self, width)
        self.initialise    = Initialise(self, width)
        width = 8
        self.powerOff      = PowerOff(self, width)

        # set which buttons are presented and where they go
        self.setExpertLevel()

    def setExpertLevel(self):
        """
        Set expert level
        """
        level = g.cpars['expert_level']

        # first define which buttons are visible
        if level == 0:
            # simple layout
            self.resetSDSUhard.grid_forget()
            self.resetSDSUsoft.grid_forget()
            self.resetPCI.grid_forget()
            self.systemReset.grid_forget()
            self.setupServers.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()
            self.initialise.grid_forget()

            # then re-grid the two simple ones
            self.initialise.grid(row=0,column=0)
            self.powerOff.grid(row=0,column=1)

        elif level == 1 or level == 2:
            # first remove all possible buttons
            self.resetSDSUhard.grid_forget()
            self.resetSDSUsoft.grid_forget()
            self.resetPCI.grid_forget()
            self.systemReset.grid_forget()
            self.setupServers.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()
            self.initialise.grid_forget()

            # restore detailed layout
            row    = 0
            column = 0
            self.resetSDSUhard.grid(row=row,column=column)
            row += 1
            self.resetSDSUsoft.grid(row=row,column=column)
            row += 1
            self.resetPCI.grid(row=row,column=column)
            row += 1
            self.systemReset.grid(row=row,column=column)
            row += 1
            self.setupServers.grid(row=row,column=column)
            row += 1
            self.powerOn.grid(row=row,column=column)

            # next column
            row = 0
            column += 1
            self.powerOff.grid(row=row,column=column)

        # now set whether buttons are permanently enabled or not
        if level == 0 or level == 1:
            self.resetSDSUhard.setNonExpert()
            self.resetSDSUsoft.setNonExpert()
            self.resetPCI.setNonExpert()
            self.systemReset.setNonExpert()
            self.setupServers.setNonExpert()
            self.powerOn.setNonExpert()
            self.powerOff.setNonExpert()
            self.initialise.setNonExpert()

        elif level == 2:
            self.resetSDSUhard.setExpert()
            self.resetSDSUsoft.setExpert()
            self.resetPCI.setExpert()
            self.systemReset.setExpert()
            self.setupServers.setExpert()
            self.powerOn.setExpert()
            self.powerOff.setExpert()
            self.initialise.setExpert()

# start of logging stuff with definition of
# three handlers

class GuiHandler(logging.Handler):
    """
    This defines the output sent to a text widget GUI
    """
    def __init__(self, twidget):
        """
        twidget : text widget to display logging messages
        """

        logging.Handler.__init__(self)
        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(asctime)s - %(message)s\n','%H:%M:%S')
        self.setFormatter(formatter)

        # ignore DEBUG messages
        self.setLevel(logging.INFO)

        # configure and store the text widget
        twidget.tag_config('DEBUG', background=g.COL['debug'])
        twidget.tag_config('INFO')
        twidget.tag_config('WARNING', background=g.COL['warn'])
        twidget.tag_config('ERROR', background=g.COL['error'])
        twidget.tag_config('CRITICAL', background=g.COL['critical'])
        self.twidget = twidget

    def emit(self, message):
        formattedMessage = self.format(message)

        # Write message to twidget
        self.twidget.configure(state=tk.NORMAL,font=g.ENTRY_FONT)
        self.twidget.insert(tk.END, formattedMessage, (message.levelname,))

        # Prevent further input
        self.twidget.configure(state=tk.DISABLED)
        self.twidget.see(tk.END)

class FileHandler(logging.FileHandler):
    """
    Used to send logging output to a file
    """
    def __init__(self, fname):
        """
        fout: file pointer to send messages to
        """
        logging.FileHandler.__init__(self, fname)
        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)-7s %(message)s','%Y-%m-%d %H:%M:%S')
        self.setFormatter(formatter)

class StreamHandler(logging.StreamHandler):
    """
    Used to send logging output to stderr
    """
    def __init__(self):
        """
        fout: file pointer to send messages to
        """
        logging.StreamHandler.__init__(self)
        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)-7s %(message)s\n','%H:%M:%S')
        self.setFormatter(formatter)
        self.setLevel(logging.INFO)

    def emit(self, message):
        """
        Overwrites the default handler's emit method:

        message : the message to display
        """
        sys.stderr.write(self.format(message))

class Logger(object):
    """
    Defines an object for logging. This uses the logging module to
    define an internal logger and then defines how it reports to
    stderr and, optionally, a file. It also defines shortcuts to
    the standard logging methods warn, info etc. This is mainly
    as a base class for two GUI-based loggers that come next.

     logname : unique name for logger

    """

    def __init__(self, logname):

        # make a logger
        self._log = logging.getLogger(logname)

        # disable automatic logging to the terminal
        self._log.propagate = False

        # add terminal handler that avoids debug messages
        self._log.addHandler(StreamHandler())

    def update(self, fname):
        """
        Adds a handler to save to a file. Includes debug stuff.
        """
        ltfh = FileHandler(fname)
        self._log.addHandler(ltfh)

    def debug(self, message):
        self._log.debug(message)

    def info(self, message):
        self._log.info(message)

    def warn(self, message):
        self._log.warn(message)

    def error(self, message):
        self._log.error(message)

    def critical(self, message):
        self._log.critical(message)

class GuiLogger(Logger, tk.Frame):
    """
    Defines a GUI logger, a combination of Logger and a Frame

     logname : unique name for logger
     root    : the root widget the LabelFrame descends from
     height  : height in pixels
     width   : width in pixels

    """

    def __init__(self, logname, root, height, width):

        # configure the Logger
        Logger.__init__(self, logname);

        # configure the LabelFrame
        tk.Frame.__init__(self, root);

        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        twidget = tk.Text(
            self, height=height, width=width, bg=g.COL['log'],
            yscrollcommand=scrollbar.set)
        twidget.configure(state=tk.DISABLED)
        twidget.pack(side=tk.LEFT)
        scrollbar.config(command=twidget.yview)

        # create and add a handler for the GUI
        self._log.addHandler(GuiHandler(twidget))

class LabelGuiLogger(Logger, tk.LabelFrame):
    """
    Defines a GUI logger, a combination of Logger and a LabelFrame

     logname : unique name for logger
     root    : the root widget the LabelFrame descends from
     height  : height in pixels
     width   : width in pixels
     label   : label for the LabelFrame

    """

    def __init__(self, logname, root, height, width, label):

        # configure the Logger
        Logger.__init__(self, logname);

        # configure the LabelFrame
        tk.LabelFrame.__init__(self, root, text=label);

        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        twidget = tk.Text(
            self, height=height, width=width, bg=g.COL['log'],
            yscrollcommand=scrollbar.set)
        twidget.configure(state=tk.DISABLED)
        twidget.pack(side=tk.LEFT)
        scrollbar.config(command=twidget.yview)

        # create and add a handler for the GUI
        self._log.addHandler(GuiHandler(twidget))

# ok, that's last of logging stuff

class Switch(tk.Frame):
    """
    Frame sub-class to switch between setup, focal plane slide
    and observing frames. Provides radio buttons and hides / shows
    respective frames
    """
    def __init__(self, master):
        """
        master : containing widget
        """
        tk.Frame.__init__(self, master)

        self.val = tk.StringVar()
        self.val.set('Setup')
        self.val.trace('w', self._changed)

        tk.Radiobutton(self, text='Setup', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Setup').grid(row=0, column=0, sticky=tk.W)
        tk.Radiobutton(self, text='Observe', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Observe').grid(row=0, column=1, sticky=tk.W)
        tk.Radiobutton(self, text='Focal plane slide', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Focal plane slide').grid(row=0, column=2, 
                                                       sticky=tk.W)

    def _changed(self, *args):
        if self.val.get() == 'Setup':
            g.setup.pack(anchor=tk.W, pady=10)
            g.fpslide.pack_forget()
            g.observe.pack_forget()

        elif self.val.get() == 'Focal plane slide':
            g.setup.pack_forget()
            g.fpslide.pack(anchor=tk.W, pady=10)
            g.observe.pack_forget()

        elif self.val.get() == 'Observe':
            g.setup.pack_forget()
            g.fpslide.pack_forget()
            g.observe.pack(anchor=tk.W, pady=10)

        else:
            raise DriverError('Unrecognised Switch value')

class ExpertMenu(tk.Menu):
    """
    Provides a menu to select the level of expertise wanted
    when interacting with a control GUI. This setting might
    be used to hide buttons for instance according to
    the status of others, etc. Use ExpertMenu.indices
    to pass a set of indices of the master menu which get
    enabled or disabled according to the expert level (disabled
    at level 0, otherwise enabled)
    """
    def __init__(self, master, *args):
        """
        master   -- the containing widget, e.g. toolbar menu
        args     -- other objects that have a 'setExpertLevel()' method.
        """
        tk.Menu.__init__(self, master, tearoff=0)

        self.val = tk.IntVar()
        self.val.set(g.cpars['expert_level'])
        self.val.trace('w', self._change)
        self.add_radiobutton(label='Level 0', value=0, variable=self.val)
        self.add_radiobutton(label='Level 1', value=1, variable=self.val)
        self.add_radiobutton(label='Level 2', value=2, variable=self.val)
        self.args    = args
        self.root    = master
        self.indices = []

    def _change(self, *args):
        g.cpars['expert_level'] = self.val.get()
        for arg in self.args:
            arg.setExpertLevel()
        for index in self.indices:
            if g.cpars['expert_level']:
                self.root.entryconfig(index,state=tk.NORMAL)
            else:
                self.root.entryconfig(index,state=tk.DISABLED)

class RtplotHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """
    Handler for requests from rtplot. It accesses the window
    parameters via the 'server' attribute; the Server class
    that comes next stores these in on instantiation.
    """
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        wins = self.server.instpars.getRtplotWins()
        if wins == '':
            self.wfile.write('No valid data available\r\n')
        else:
            self.wfile.write(wins)

class RtplotServer (SocketServer.TCPServer):
    """
    Server for requests from rtplot.
    The response delivers the binning factors, number of windows and
    their positions.
    """
    def __init__(self, instpars, port):
        # '' opens port on localhost and makes it visible
        # outside localhost
        try:
            SocketServer.TCPServer.__init__(
                self, ('', port), RtplotHandler)
            self.instpars = instpars
        except socket.error, err:
            errorcode =  err[0]
            if errorcode == errno.EADDRINUSE:
                message = str(err) + '. '
                message += 'Failed to start the rtplot server. '
                message += 'There may be another instance of usdriver running. '
                message += 'Suggest that you shut down usdriver, close all other instances,'
                message += ' and then restart it.'
            else:
                message = str(err)
                message += 'Failed to start the rtplot server'

            raise DriverError(message)
        print('rtplot server started')

    def run(self):
        while True:
            try:
                self.serve_forever()
            except Exception, e:
                g.clog.warn('RtplotServer.run', e)

class Timer(tk.Label):
    """
    Run Timer class. Updates @10Hz, checks
    run status @1Hz. Switches button statuses
    when the run stops.
    """
    def __init__(self, master):
        tk.Label.__init__(self, master, text='{0:<d} s'.format(0), font=g.ENTRY_FONT)
        self.id    = None
        self.count = 0

    def start(self):
        """
        Starts the timer from zero
        """
        self.startTime = time.time()
        self.configure(text='{0:<d} s'.format(0))
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock, checks
        run status @1Hz to reduce load on servers.
        """
        try:
            self.count += 1
            delta = int(round(time.time()-self.startTime))
            self.configure(text='{0:<d} s'.format(delta))

            if self.count % 10 == 0:
                if not isRunActive():
                    g.observe.start.enable()
                    g.observe.stop.disable()
                    g.setup.resetSDSUhard.enable()
                    g.setup.resetSDSUsoft.enable()
                    g.setup.resetPCI.disable()
                    g.setup.setupServers.disable()
                    g.setup.powerOn.disable()
                    g.setup.powerOff.enable()
                    g.clog.info('Run stopped')
                    self.stop()
                    return

        except Exception, err:
            if self.count % 100 == 0:
                g.clog.warn('Timer.update: error = ' + str(err))

        self.id = self.after(100, self.update)

    def stop(self):
        if self.id is not None:
            self.after_cancel(self.id)
        self.id = None

class Ilabel(tk.Label):
    """
    Class to define an information label which uses the same font
    as the entry fields rather than the default font
    """
    def __init__(self, master, **kw):
        tk.Label.__init__(self, master,font=g.ENTRY_FONT, **kw)

class InfoFrame(tk.LabelFrame):
    """
    Information frame: run number, exposure time, etc.
    """
    def __init__(self, master):
        tk.LabelFrame.__init__(self, master,
                               text='Current run & telescope status', padx=4, pady=4)

        self.run     = Ilabel(self, text='UNDEF')
        self.frame   = Ilabel(self,text='UNDEF')
        self.timer   = Timer(self)
        self.cadence = Ilabel(self,text='UNDEF')
        self.duty    = Ilabel(self,text='UNDEF')
        self.filter  = Ilabel(self,text='UNDEF')
        self.ra      = Ilabel(self,text='UNDEF')
        self.dec     = Ilabel(self,text='UNDEF')
        self.alt     = Ilabel(self,text='UNDEF')
        self.az      = Ilabel(self,text='UNDEF')
        self.airmass = Ilabel(self,text='UNDEF')
        self.ha      = Ilabel(self,text='UNDEF')
        self.pa      = Ilabel(self,text='UNDEF')
        self.engpa   = Ilabel(self,text='UNDEF')
        self.focus   = Ilabel(self,text='UNDEF')
        self.mdist   = Ilabel(self,text='UNDEF')
        self.fpslide = Ilabel(self,text='UNDEF')
        self.lake    = Ilabel(self,text='UNDEF')

        # left-hand side
        tk.Label(self,text='Run:').grid(row=0,column=0,padx=5,sticky=tk.W)
        self.run.grid(row=0,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Frame:').grid(row=1,column=0,padx=5,sticky=tk.W)
        self.frame.grid(row=1,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Exposure:').grid(row=2,column=0,padx=5,sticky=tk.W)
        self.timer.grid(row=2,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Filter:').grid(row=3,column=0,padx=5,sticky=tk.W)
        self.filter.grid(row=3,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Cadence:').grid(row=4,column=0,padx=5,sticky=tk.W)
        self.cadence.grid(row=4,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Duty cycle:').grid(row=5,column=0,padx=5,
                                               sticky=tk.W)
        self.duty.grid(row=5,column=1,padx=5,sticky=tk.W)

        # middle
        tk.Label(self,text='RA:').grid(row=0,column=3,padx=5,sticky=tk.W)
        self.ra.grid(row=0,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Dec:').grid(row=1,column=3,padx=5,sticky=tk.W)
        self.dec.grid(row=1,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Alt:').grid(row=2,column=3,padx=5,sticky=tk.W)
        self.alt.grid(row=2,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Az:').grid(row=3,column=3,padx=5,sticky=tk.W)
        self.az.grid(row=3,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Airm:').grid(row=4,column=3,padx=5,sticky=tk.W)
        self.airmass.grid(row=4,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='HA:').grid(row=5,column=3,padx=5,sticky=tk.W)
        self.ha.grid(row=5,column=4,padx=5,sticky=tk.W)

        # right-hand side
        tk.Label(self,text='PA:').grid(row=0,column=6,padx=5,sticky=tk.W)
        self.pa.grid(row=0,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='Eng. PA:').grid(row=1,column=6,padx=5,sticky=tk.W)
        self.engpa.grid(row=1,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='Focus:').grid(row=2,column=6,padx=5,sticky=tk.W)
        self.focus.grid(row=2,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='Mdist:').grid(row=3,column=6,padx=5,sticky=tk.W)
        self.mdist.grid(row=3,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='FP slide:').grid(row=4,column=6,padx=5,sticky=tk.W)
        self.fpslide.grid(row=4,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='CCD temp:').grid(row=5,column=6,padx=5,sticky=tk.W)
        self.lake.grid(row=5,column=7,padx=5,sticky=tk.W)

        # these are used to judge whether we are tracking or not
        self.ra_old    = 0.
        self.dec_old   = 0.
        self.pa_old    = 0.
        self.tracking  = False

        # start
        self.count = 0
        self.update()

    def update(self):
        """
        Updates run & tel status window. Runs
        once every 2 seconds.
        """

        if g.astro is None or g.fpslide is None:
            self.after(100, self.update)
            return

        try:

            if g.cpars['tcs_on']:
                if g.cpars['telins_name'] == 'TNO-USPEC':
                    try:

                        # Poll TCS for ra,dec etc.
                        ra,dec,pa,focus,tracking,engpa = tcs.getTntTcs()

                        self.ra.configure(text=d2hms(ra/15., 1, False))
                        self.dec.configure(text=d2hms(dec, 0, True))
                        while pa < 0.:
                            pa += 360.
                        while pa > 360.:
                            pa -= 360.
                        self.pa.configure(text='{0:6.2f}'.format(pa))

                        # check for significant changes in position to flag
                        # tracking failures. I have removed a test of tflag
                        # to be True because the telescope often switches to
                        # "slewing" status even when nominally tracking.
                        if abs(ra-self.ra_old) < 1.e-3 and \
                           abs(dec-self.dec_old) < 1.e-3:
                            self.tracking = True
                            self.ra.configure(bg=g.COL['main'])
                            self.dec.configure(bg=g.COL['main'])
                        else:
                            self.tracking = False
                            self.ra.configure(bg=g.COL['warn'])
                            self.dec.configure(bg=g.COL['warn'])

                        # check for changing sky PA
                        if abs(pa-self.pa_old) > 0.1 and \
                           abs(pa-self.pa_old-360.) > 0.1 and \
                           abs(pa-self.pa_old+360.) > 0.1:
                            self.pa.configure(bg=g.COL['warn'])
                        else:
                            self.pa.configure(bg=g.COL['main'])

                        # store current values for comparison with next
                        self.ra_old  = ra
                        self.dec_old = dec
                        self.pa_old  = pa

                        # set engineering PA, warn if within 20 degrees
                        # of limits
                        self.engpa.configure(text='{0:+6.1f}'.format(engpa))

                        # rotator limits are -220, +250. Warn when within 20
                        # degrees of these. (I carried out a test and the
                        # upper rotator limit was actually hit at +255 but
                        # I have stuck to 250).
                        if engpa < -200 or engpa > 230:
                            self.engpa.configure(bg=g.COL['warn'])
                        else:
                            self.engpa.configure(bg=g.COL['main'])

                        # set focus
                        self.focus.configure(text='{0:+5.2f}'.format(focus))

                        # create a Body for the target, calculate most of the
                        # stuff that we don't get from the telescope
                        star = ephem.FixedBody()
                        star._ra  = math.radians(ra)
                        star._dec = math.radians(dec)
                        star.compute(g.astro.obs)

                        lst = g.astro.obs.sidereal_time()
                        ha  = (math.degrees(lst)-ra)/15.
                        if ha > 12.:
                            ha -= 12.
                        elif ha < -12.:
                            ha += 12.
                        self.ha.configure(text=d2hms(ha, 0, True))

                        dalt = math.degrees(star.alt)
                        daz  = math.degrees(star.az)
                        self.alt.configure(text='{0:<4.1f}'.format(dalt))
                        self.az.configure(text='{0:<5.1f}'.format(daz))

                        # warn about the TV mast. Basically checks whether alt
                        # and az lie in roughly triangular shape presented by
                        # the mast. First move azimuth 5 deg closer to the
                        # mast to give a bit of warning.
                        if daz > 33.5:
                            daz = min(33.5,daz-5.)
                        else:
                            daz = max(33.5,daz+5.)

                        if daz > 25.5 and daz < 50.0 and \
                           dalt < 73.5 and \
                           ((daz < 33.5 and \
                             dalt < 73.5-(33.5-daz)/ \
                             (33.5-25.5)*(73.5-21.5)) or \
                            (daz > 33.5 and \
                             dalt < 73.5- \
                             (daz-33.5)/(50.0-33.5)*(73.5-21.5))):
                            self.alt.configure(bg=g.COL['warn'])
                            self.az.configure(bg=g.COL['warn'])
                        else:
                            self.alt.configure(bg=g.COL['main'])
                            self.az.configure(bg=g.COL['main'])

                        # set airmass
                        self.airmass.configure(
                            text='{0:<4.2f}'.format(
                            1./math.sin(star.alt)))

                        # distance to the moon. Warn if too close
                        # (configurable) to it.
                        md = math.degrees(ephem.separation(g.astro.moon,star))
                        self.mdist.configure(text='{0:<7.2f}'.format(md))
                        if md < g.cpars['mdist_warn']:
                            self.mdist.configure(bg=g.COL['warn'])
                        else:
                            self.mdist.configure(bg=g.COL['main'])

                    except Exception, err:
                        self.ra.configure(text='UNDEF')
                        self.dec.configure(text='UNDEF')
                        self.pa.configure(text='UNDEF')
                        self.ha.configure(text='UNDEF')
                        self.alt.configure(text='UNDEF')
                        self.az.configure(text='UNDEF')
                        self.airmass.configure(text='UNDEF')
                        self.mdist.configure(text='UNDEF')
                        g.clog.warn('TCS error: ' + str(err))
                else:
                    g.clog.debug('TCS error: could not recognise ' +
                                     g.cpars['telins_name'])

            if g.cpars['cdf_servers_on'] and \
               g.cpars['servers_initialised']:

                # get run number (set by the 'Start' button')
                try:
                    # if no run is active, get run number from
                    # ultracam servers
                    if not isRunActive():
                        run = getRunNumber(True)
                        self.run.configure(text='{0:03d}'.format(run))

                    # get the value of the run being displayed, regardless of
                    # whether we just managed to update it
                    rtxt = self.run.cget('text')

                    # if the value comes back as undefined, try to work out
                    # the run number from the FileServer directory listing
                    if rtxt == 'UNDEF':
                        url = g.cpars['http_file_server'] + '?action=dir'
                        response = urllib2.urlopen(url)
                        resp = response.read()

                        # parse response from server
                        ldir = resp.split('<li>')
                        runs = [entry[entry.find('>run')+1:\
                                      entry.find('>run')+7] \
                                for entry in ldir \
                                if entry.find('getdata">run') > -1]
                        runs.sort()
                        rtxt = runs[-1][3:]
                        run = int(rtxt)
                        self.run.configure(text='{0:03d}'.format(run))
                    else:
                        run = int(rtxt)

                    # OK, we have managed to get the run number
                    rstr = 'run{0:03d}'.format(run)
                    try:
                        url = g.cpars['http_file_server'] + rstr + '?action=get_num_frames'
                        response = urllib2.urlopen(url)
                        rstr = response.read()
                        ind = rstr.find('nframes="')
                        if ind > -1:
                            ind += 9
                            nframe = int(rstr[ind:ind+rstr[ind:].find('"')])
                            self.frame.configure(text='{0:d}'.format(nframe))
                    except Exception, err:
                        if err.code == 404:
#                            g.clog.debug('Error trying to set frame: ' +
#                                             str(err))
                            self.frame.configure(text='0')
                        else:
                            g.clog.debug('Error occurred trying to set frame')
                            self.frame.configure(text='UNDEF')

                except Exception, err:
                    g.clog.debug('Error trying to set run: ' + str(err))

            # get the current filter, which is set during the start
            # operation
            if g.start_filter:
                self.filter.configure(text=g.start_filter)

            # get the slide position
            # poll at 5x slower rate than the frame
            if self.count % 5 == 0 and g.cpars['focal_plane_slide_on']:
                try:
                    pos_ms,pos_mm,pos_px = g.fpslide.slide.return_position()
                    self.fpslide.configure(text='{0:d}'.format(
                        int(round(pos_px))))
                    if pos_px < 1050.:
                        self.fpslide.configure(bg=g.COL['warn'])
                    else:
                        self.fpslide.configure(bg=g.COL['main'])
                except Exception, err:
                    g.clog.warn('Slide error: ' + str(err))
                    self.fpslide.configure(text='UNDEF')
                    self.fpslide.configure(bg=g.COL['warn'])

            # get the CCD temperature poll at 5x slower rate than the frame
            if self.count % 5 == 0 and g.cpars['ccd_temperature_on']:
                try:
                    if g.lakeshore is None:
                        g.lakeshore = lake.LakeFile()
                    tempa, tempb, heater = g.lakeshore.temps()
                    self.lake.configure(text='{0:5.1f}'.format(tempa))
                    if tempa > 165:
                        self.lake.configure(bg=g.COL['error'])
                    elif tempa > 162.:
                        self.lake.configure(bg=g.COL['warn'])
                    else:
                        self.lake.configure(bg=g.COL['main'])
                except Exception, err:
                    g.clog.warn(str(err))
                    self.lake.configure(text='UNDEF')
                    self.lake.configure(bg=g.COL['warn'])

        except Exception, err:
            # this is a safety catchall trap as it is important
            # that this routine keeps going
            g.clog.warn('Unexpected error: ' + str(err))

        # run every 2 seconds
        self.count += 1
        self.after(2000, self.update)

class AstroFrame(tk.LabelFrame):
    """
    Astronomical information frame
    """
    def __init__(self, master):
        tk.LabelFrame.__init__(self, master, padx=2, pady=2, text='Time & Sky')

        # times
        self.mjd       = Ilabel(self)
        self.utc       = Ilabel(self,width=9,anchor=tk.W)
        self.lst       = Ilabel(self)

        # sun info
        self.sunalt    = Ilabel(self,width=11,anchor=tk.W)
        self.riset     = Ilabel(self)
        self.lriset    = Ilabel(self)
        self.astro     = Ilabel(self)

        # moon info
        self.moonra    = Ilabel(self)
        self.moondec   = Ilabel(self)
        self.moonalt   = Ilabel(self)
        self.moonphase = Ilabel(self)

        # observatory info
        self.obs      = ephem.Observer()

        tins = g.TINS[g.cpars['telins_name']]
        self.obs.lat       = tins['latitude']
        self.obs.lon       = tins['longitude']
        self.obs.elevation = tins['elevation']

        # generate Sun and Moon
        self.sun = ephem.Sun()
        self.moon = ephem.Moon()

        # arrange time info
        tk.Label(self,text='MJD:').grid(
            row=0,column=0,padx=2,pady=3,sticky=tk.W)
        self.mjd.grid(row=0,column=1,columnspan=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='UTC:').grid(
            row=0,column=3,padx=2,pady=3,sticky=tk.W)
        self.utc.grid(row=0,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='LST:').grid(
            row=0,column=5,padx=2,pady=3,sticky=tk.W)
        self.lst.grid(row=0,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange solar info
        tk.Label(self,text='Sun:').grid(
            row=1,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(
            row=1,column=1,padx=2,pady=3,sticky=tk.W)
        self.sunalt.grid(row=1,column=2,padx=2,pady=3,sticky=tk.W)
        self.lriset.grid(row=1,column=3,padx=2,pady=3,sticky=tk.W)
        self.riset.grid(row=1,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='At -18:').grid(
            row=1,column=5,padx=2,pady=3,sticky=tk.W)
        self.astro.grid(row=1,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange moon info
        tk.Label(self,text='Moon:').grid(
            row=2,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='RA:').grid(
            row=2,column=1,padx=2,pady=3,sticky=tk.W)
        self.moonra.grid(row=2,column=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Dec:').grid(row=3,column=1,padx=2,sticky=tk.W)
        self.moondec.grid(row=3,column=2,padx=2,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(
            row=2,column=3,padx=2,pady=3,sticky=tk.W)
        self.moonalt.grid(row=2,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Phase:').grid(row=3,column=3,padx=2,sticky=tk.W)
        self.moonphase.grid(row=3,column=4,padx=2,sticky=tk.W)

        # report back to the user
        tins = g.TINS[g.cpars['telins_name']]
        g.clog.info('Tel/ins = ' + g.cpars['telins_name'])
        g.clog.info('Longitude = ' + tins['longitude'] + ' E')
        g.clog.info('Latitude = ' + tins['latitude'] + ' N')
        g.clog.info('Elevation = ' + str(tins['elevation']) + ' m')

        # parameters used to reduce re-calculation of sun rise etc, and
        # to provide info for other widgets
        self.lastRiset = 0
        self.lastAstro = 0
        self.counter   = 0

        # start
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock.
        """

        try:

            # update counter
            self.counter += 1

            # current time in seconds since start of UNIX
            utc = time.time()
            self.obs.date = ephem.Date(g.UNIX0-g.EPH0+utc/g.DAY)

            # configure times
            self.utc.configure(text=time.strftime('%H:%M:%S',time.gmtime(utc)))
            self.mjd.configure(text='{0:11.5f}'.format(
                g.UNIX0-g.MJD0+utc/g.DAY))
            lst = g.DAY*(self.obs.sidereal_time()/math.pi/2.)
            self.lst.configure(text=time.strftime('%H:%M:%S',time.gmtime(lst)))

            if self.counter % 100 == 1:
                # only re-compute Sun & Moon info once every 100 calls

                # re-compute sun
                self.obs.pressure = 1010.
                self.sun.compute(self.obs)

                self.sunalt.configure(
                    text='{0:+03d} deg'.format(
                        int(round(math.degrees(self.sun.alt)))))

                if self.obs.date > self.lastRiset and \
                   self.obs.date > self.lastAstro:
                    # Only re-compute rise and setting times when necessary,
                    # and only re-compute when both rise/set and astro
                    # twilight times have gone by

                    # turn off refraction for both sunrise & set and astro
                    # twilight calculation.
                    self.obs.pressure = 0.

                    # For sunrise and set we set the horizon down to match a
                    # standard amount of refraction at the horizon
                    self.obs.horizon  = '-0:34'
                    sunset  = self.obs.next_setting(self.sun)
                    sunrise = self.obs.next_rising(self.sun)

                    # Astro twilight: geometric centre at -18 deg
                    self.obs.horizon = '-18'
                    astroset  = self.obs.next_setting(self.sun, use_center=True)
                    astrorise = self.obs.next_rising(self.sun, use_center=True)

                    if sunrise > sunset:
                        # In the day time we report the upcoming sunset and
                        # end of evening twilight
                        self.lriset.configure(text='Sets:', font=g.DEFAULT_FONT)
                        self.lastRiset = sunset
                        self.lastAstro = astroset

                    elif astrorise > astroset and astrorise < sunrise:
                        # During evening twilight, we report the sunset just
                        # passed and end of evening twilight
                        self.lriset.configure(text='Sets:', font=g.DEFAULT_FONT)
                        self.obs.horizon  = '-0:34'
                        self.lastRiset = self.obs.previous_setting(self.sun)
                        self.lastAstro = astroset

                    elif astrorise > astroset and astrorise < sunrise:
                        # During night, report upcoming start of morning
                        # twilight and sunrise
                        self.lriset.configure(text='Rises:',
                                              font=g.DEFAULT_FONT)
                        self.obs.horizon  = '-0:34'
                        self.lastRiset = sunrise
                        self.lastAstro = astrorise

                    else:
                        # During morning twilight report start of twilight
                        # just passed and upcoming sunrise
                        self.lriset.configure(text='Rises:',
                                              font=g.DEFAULT_FONT)
                        self.obs.horizon  = '-18'
                        self.lastRiset = sunrise
                        self.lastAstro = self.obs.previous_rising(
                            self.sun, use_center=True)

                    # Configure the corresponding text fields
                    ntime = g.DAY*(self.lastRiset + g.EPH0 - g.UNIX0)
                    self.riset.configure(
                        text=time.strftime('%H:%M:%S',time.gmtime(ntime)))
                    ntime = g.DAY*(self.lastAstro + g.EPH0 - g.UNIX0)
                    self.astro.configure(
                        text=time.strftime('%H:%M:%S',time.gmtime(ntime)))

                # re-compute moon
                self.obs.pressure = 1010.
                self.moon.compute(self.obs)
                self.moonra.configure(text='{0}'.format(self.moon.ra))
                self.moondec.configure(text='{0}'.format(self.moon.dec))
                self.moonalt.configure(
                    text='{0:+03d} deg'.format(
                        int(round(math.degrees(self.moon.alt)))))
                self.moonphase.configure(
                    text='{0:02d} %'.format(
                        int(round(100.*self.moon.moon_phase))))

        except Exception, err:
            # catchall
            g.clog.warn('AstroFrame.update: error = ' + str(err))

        # run again after 100 milli-seconds
        self.after(100, self.update)


# various helper routines

def isRunActive():
    """
    Polls the data server to see if a run is active
    """
    if g.cpars['cdf_servers_on']:
        url = g.cpars['http_data_server'] + 'status'
        response = urllib2.urlopen(url, timeout=2)
        rs  = ReadServer(response.read())
        if not rs.ok:
            raise DriverError('isRunActive error: ' + str(rs.err))

        if rs.state == 'IDLE':
            return False
        elif rs.state == 'BUSY':
            return True
        else:
            raise DriverError('isRunActive error, state = ' + rs.state)
    else:
        raise DriverError('isRunActive error: servers are not active')

def getRunNumber(nocheck=False):
    """
    Polls the data server to find the current run number. Throws
    exceptions if it can't determine it.

    nocheck : determines whether a check for an active run is made
            nocheck=False is safe, but runs 'isRunActive' which
            might not be needed if you have called this already.
            nocheck=True avoids the isRunActive but runs the risk
            of polling for the run of an active run which cannot
            be done.
    """

    if not g.cpars['cdf_servers_on']:
        raise DriverError('getRunNumber error: servers are not active')

    if nocheck or isRunActive():
        url = g.cpars['http_data_server'] + 'fstatus'
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())
        if rs.ok:
            return rs.run
        else:
            raise DriverError('getRunNumber error: ' + str(rs.err))
    else:
        raise DriverError('getRunNumber error')

def checkSimbad(target, maxobj=5, timeout=5):
    """
    Sends off a request to Simbad to check whether a target is recognised.
    Returns with a list of results, or raises an exception if it times out
    """
    url   = 'http://simbad.u-strasbg.fr/simbad/sim-script'
    q     = 'set limit ' + str(maxobj) + \
        '\nformat object form1 "Target: %IDLIST(1) | %COO(A D;ICRS)"\nquery ' \
        + target
    query = urllib.urlencode({'submit' : 'submit script', 'script' : q})
    resp  = urllib2.urlopen(url, query, timeout)
    data  = False
    error = False
    results = []
    for line in resp:
        if line.startswith('::data::'):
            data = True
        if line.startswith('::error::'):
            error = True
        if data and line.startswith('Target:'):
            name,coords = line[7:].split(' | ')
            results.append(
                {'Name' : name.strip(), 'Position' : coords.strip(),
                 'Frame' : 'ICRS'})
    resp.close()

    if error and len(results):
        g.clog.warn('drivers.check: Simbad: there appear to be some ' + \
                        'results but an error was unexpectedly raised.')
    return results


class WinPairs (tk.Frame):
    """
    Class to define a frame of multiple window pairs,
    contained within a gridded block that can be easily position.
    """

    def __init__(self, master, xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs,
                 yss, ysmins, ysmaxs, nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xsls, xslmins, xslmaxs :
            initial X values of the leftmost columns of left-hand windows
            along with minimum and maximum values (array-like)

          xsrs, xsrmins, xsrmaxs :
            initial X values of the leftmost column of right-hand windows
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            Y dimensions of windows, unbinned pixels
            (array-like)

          xbfac :
            array of unique x-binning factors

          ybfac :
            array of unique y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.

        It is assumed that the maximum X dimension is the same for both left
        and right windows and equal to xslmax-xslmin+1.
        """

        npair = len(xsls)
        checks = (xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs, \
                      yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if npair != len(check):
                raise DriverError(
                    'drivers.WindowPairs.__init__:' + \
                        ' conflict array lengths amonst inputs')

        tk.Frame.__init__(self, master)

        # top part contains the binning factors and
        # the number of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0,column=1,sticky=tk.W)

        row = 1
        self.npair = RangedInt(top, 1, 1, npair, checker, False, width=2)
        if npair > 1:
            # Second row: number of windows
            tk.Label(top, text='Number of window pairs').grid(
                row=1,column=0, sticky=tk.W)
            self.npair.grid(row=row,column=1,sticky=tk.W,pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xsl').grid(row=row,column=1,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='xsr').grid(row=row,column=2,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row,column=3,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row,column=4,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row,column=5,ipady=5,sticky=tk.S)

        row += 1
        self.label, self.xsl, self.xsr, self.ys, self.nx, self.ny = \
            [],[],[],[],[],[]
        nr = 0
        for xsl, xslmin, xslmax, xsr, xsrmin, xsrmax, ys, ysmin, ysmax, \
                nx, ny in zip(*checks):

            # create
            if npair == 1:
                self.label.append(tk.Label(bottom, text='Pair: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Pair ' + str(nr) + ': '))

            self.xsl.append(
                RangedInt(bottom, xsl, xslmin, xslmax, checker, True, width=4))
            self.xsr.append(
                RangedInt(bottom, xsr, xsrmin, xsrmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xslmax-xslmin+1, self.xbin,
                           checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1, self.ybin,
                           checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row,column=0)
            self.xsl[-1].grid(row=row,column=1)
            self.xsr[-1].grid(row=row,column=2)
            self.ys[-1].grid(row=row,column=3)
            self.nx[-1].grid(row=row,column=4)
            self.ny[-1].grid(row=row,column=5)

            row += 1
            nr  += 1

        # syncing button
        self.sbutt = ActButton(bottom, 5, self.sync, text='Sync')
        self.sbutt.grid(row=row,column=0,columnspan=5,pady=10,sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the window pairs. If any problems are found, it
        flags them by changing the background colour.

        Returns (status, synced)

          status : flag for whether parameters are viable at all
          synced : flag for whether the windows are synchronised.
        """

        status = True
        synced = True

        xbin  = self.xbin.value()
        ybin  = self.ybin.value()
        npair = self.npair.value()

        # individual pair checks
        for xslw, xsrw, ysw, nxw, nyw in \
                zip(self.xsl[:npair], self.xsr[:npair], self.ys[:npair],
                    self.nx[:npair], self.ny[:npair]):
            xslw.config(bg=g.COL['main'])
            xsrw.config(bg=g.COL['main'])
            ysw.config(bg=g.COL['main'])
            nxw.config(bg=g.COL['main'])
            nyw.config(bg=g.COL['main'])
            status = status if xslw.ok() else False
            status = status if xsrw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xsl = xslw.value()
            xsr = xsrw.value()
            ys  = ysw.value()
            nx  = nxw.value()
            ny  = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=g.COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=g.COL['error'])
                status = False

            # overlap checks
            if xsl is None or xsr is None or xsl >= xsr:
                xsrw.config(bg=g.COL['error'])
                status = False

            if xsl is None or xsr is None or nx is None or xsl + nx > xsr:
                xsrw.config(bg=g.COL['error'])
                status = False

            # Are the windows synchronised? This means that they would
            # be consistent with the pixels generated were the whole CCD
            # to be binned by the same factors. If relevant values are not
            # set, we count that as "synced" because the purpose of this is
            # to enable / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            if xsl is not None and xsr is not None and ys is not None and \
                    nx is not None and ny is not None and \
                    ((xsl - 1) % xbin != 0 or (xsr - 1) % xbin != 0 or \
                         (ys - 1) % ybin != 0):
                synced = False

            # Range checks
            if xsl is None or nx is None or xsl + nx - 1 > xslw.imax:
                xslw.config(bg=g.COL['error'])
                status = False

            if xsr is None or nx is None or xsr + nx - 1 > xsrw.imax:
                xsrw.config(bg=g.COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=g.COL['error'])
                status = False

        # Pair overlap checks. Compare one pair with the next one upstream
        # (if there is one). Only bother if we have survived so far, which
        # saves a lot of checks
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:npair-1], self.ny[:npair-1]):

                ys1  = ysw1.value()
                ny1  = nyw1.value()

                n1 += 1

                ysw2, nyw2 = self.ys[n1], self.ny[n1]

                ys2  = ysw2.value()
                ny2  = nyw2.value()

                if ys1 + ny1 > ys2:
                    ysw2.config(bg=g.COL['error'])
                    status = False

        if synced:
            self.sbutt.config(bg=g.COL['main'])
            self.sbutt.disable()
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=g.COL['warn'])

        return status

    def sync(self):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factors == 1.
        """

        # needs some mods for ultracam ??
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xsl, xsr, ys, nx, ny in self:
            if xbin > 1:
                if xsl % xbin != 1:
                    xsl = xbin*((xsl-1)//xbin)+1
                    self.xsl[n].set(xsl)
                if xsr % xbin != 1:
                    xsr = xbin*((xsr-1)//xbin)+1
                    self.xsr[n].set(xsr)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze (disable) all settings so they can't be altered
        """
        for xsl, xsr, ys, nx, ny in \
                zip(self.xsl, self.xsr,
                    self.ys, self.nx, self.ny):
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.npair.disable()
        self.xbin.disable()
        self.ybin.disable()
        self.sbutt.disable()
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings so that they can be altered
        """
        self.enable()
        self.frozen = False
        self.check()

    def enable(self):
        """
        Enables WinPair settings
        """
        npair = self.npair.value()
        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[:npair], self.xsl[:npair], self.xsr[:npair],
                    self.ys[:npair], self.nx[:npair], self.ny[:npair]):
            label.config(state='normal')
            xsl.enable()
            xsr.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[npair:], self.xsl[npair:], self.xsr[npair:],
                    self.ys[npair:], self.nx[npair:], self.ny[npair:]):
            label.config(state='disable')
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.npair.enable()
        self.xbin.enable()
        self.ybin.enable()
        self.sbutt.enable()

    def __iter__(self):
        """
        Generator to allow looping through through the window pairs.
        Successive calls return xsl, xsr, ys, nx, ny for each pair
        """
        n = 0
        npair = self.npair.value()
        while n < npair:
            yield (self.xsl[n].value(),self.xsr[n].value(),
                   self.ys[n].value(),self.nx[n].value(),self.ny[n].value())
            n += 1

class Windows (tk.Frame):
    """
    Class to define a frame of multiple windows as a gridded
    block that can be placed easily within a container widget.
    Also defines binning factors and the number of active windows.
    """

    def __init__(self, master, xss, xsmins, xsmaxs, yss, ysmins, ysmaxs,
                 nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xss, xsmins, xsmaxs :
            initial X values of the leftmost column of window(s)
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            initial X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            initial Y dimension(s) of windows, unbinned pixels
            (array-like)

          xbfac :
            set of x-binning factors

          ybfac :
            set of y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.
        """

        nwin = len(xss)
        checks = (xss, xsmins, xsmaxs, yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if nwin != len(check):
                raise DriverError('drivers.Windows.__init__: ' + \
                                      'conflict array lengths amonst inputs')

        tk.Frame.__init__(self, master)

        # top part contains the binning factors and the number
        # of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0,column=1,sticky=tk.W)

        # Second row: number of windows
        self.nwin = RangedInt(top, 1, 1, nwin, checker, False, width=2)
        row = 1
        if nwin > 1:
            tk.Label(top, text='Number of windows').grid(
                row=row,column=0, sticky=tk.W)
            self.nwin.grid(row=1,column=1,sticky=tk.W,pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xs').grid(row=row,column=1,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row,column=2,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row,column=3,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row,column=4,ipady=5,sticky=tk.S)

        self.label, self.xs, self.ys, self.nx, self.ny = [],[],[],[], []
        nr = 0
        row += 1
        for xs, xsmin, xsmax, ys, ysmin, ysmax, nx, ny in zip(*checks):

            # create
            if nwin == 1:
                self.label.append(tk.Label(bottom, text='Window: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Window ' + str(nr+1) + ': '))

            self.xs.append(
                RangedInt(bottom, xs, xsmin, xsmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xsmax-xsmin+1,
                           self.xbin, checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1,
                           self.ybin, checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row,column=0)
            self.xs[-1].grid(row=row,column=1)
            self.ys[-1].grid(row=row,column=2)
            self.nx[-1].grid(row=row,column=3)
            self.ny[-1].grid(row=row,column=4)

            row += 1
            nr  += 1

        self.sbutt = ActButton(bottom, 5, self.sync, text='Sync')
        self.sbutt.grid(row=row,column=0,columnspan=5,pady=6,sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the windows. If any problems are found,
        it flags them by changing the background colour. Only active
        windows are checked.

        Returns status, flag for whether parameters are viable.
        """

        status = True
        synced = True

        xbin = self.xbin.value()
        ybin = self.ybin.value()
        nwin = self.nwin.value()

        # individual window checks
        for xsw, ysw, nxw, nyw in \
                zip(self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):

            xsw.config(bg=g.COL['main'])
            ysw.config(bg=g.COL['main'])
            nxw.config(bg=g.COL['main'])
            nyw.config(bg=g.COL['main'])
            status = status if xsw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xs  = xsw.value()
            ys  = ysw.value()
            nx  = nxw.value()
            ny  = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=g.COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=g.COL['error'])
                status = False

            # Are the windows synchronised? This means that they
            # would be consistent with the pixels generated were
            # the whole CCD to be binned by the same factors
            # If relevant values are not set, we count that as
            # "synced" because the purpose of this is to enable
            # / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            if xs is not None and ys is not None and nx is not None and \
                    ny is not None and \
                    ((xs - 1) % xbin != 0 or (ys - 1) % ybin != 0):
                synced = False

            # Range checks
            if xs is None or nx is None or xs + nx - 1 > xsw.imax:
                xsw.config(bg=g.COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=g.COL['error'])
                status = False

        # Overlap checks. Compare each window with the next one, requiring
        # no y overlap and that the second is higher than the first
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:nwin-1], self.ny[:nwin-1]):

                ys1  = ysw1.value()
                ny1  = nyw1.value()

                n1 += 1
                ysw2, nyw2 = self.ys[n1], self.ny[n1]

                ys2  = ysw2.value()
                ny2  = nyw2.value()

                if ys2 < ys1 + ny1:
                    ysw2.config(bg=g.COL['error'])
                    status = False

        if synced:
            self.sbutt.config(bg=g.COL['main'])
            self.sbutt.disable()
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=g.COL['warn'])

        return status

    def sync(self, *args):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factor == 1
        """
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xs, ys, nx, ny in self:
            if xbin > 1 and xs % xbin != 1:
                xs = xbin*((xs-1)//xbin)+1
                self.xs[n].set(xs)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze all settings so they can't be altered
        """
        for xs, ys, nx, ny in \
                zip(self.xs, self.ys, self.nx, self.ny):
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.nwin.disable()
        self.xbin.disable()
        self.ybin.disable()
        self.sbutt.disable()
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings
        """
        self.enable()
        self.frozen = False
        self.check()

    def enable(self):
        """
        Enables all settings
        """
        nwin = self.nwin.value()
        for label, xs, ys, nx, ny in \
                zip(self.label[:nwin], self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):
            label.config(state='normal')
            xs.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xs, ys, nx, ny in \
                zip(self.label[nwin:], self.xs[nwin:], self.ys[nwin:],
                    self.nx[nwin:], self.ny[nwin:]):
            label.config(state='disable')
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.nwin.enable()
        self.xbin.enable()
        self.ybin.enable()
        self.sbutt.enable()

    def __iter__(self):
        """
        Generator to allow looping through through the window values.
        Successive calls return xs, ys, nx, ny for each window
        """
        n = 0
        nwin = self.nwin.value()
        while n < nwin:
            yield (self.xs[n].value(),self.ys[n].value(),
                   self.nx[n].value(),self.ny[n].value())
            n += 1

def d2hms(d, decp, sign):
    """
    Converts a decimal to HH:MM:SS.SS format. Also
    appropriate for dd:mm:ss

    d    :  decimal value
    dp   :  number of decimal places for seconds
    sign :  True to add a + sign for positive d
    """
    dp = abs(d)
    h, fh = divmod(dp,1)
    m, fm = divmod(60.*fh,1)
    s = 60.*fm
    h  = int(h)
    m  = int(m)
    ns = int(round(s))

    # add sign, depending on case
    if d < 0.:
        form = '-'
    elif sign:
        form = '+'
    else:
        form =''
    form += '{0:02d}:{1:02d}:{2:0'
    if decp == 0:
        form += '2d}'
        if ns == 60:
            m += 1
            ns = 0
            if m == 60:
                h += 1
                m  = 0
                if h == 24:
                    h = 0
        return form.format(h,m,ns)
    else:
        form += str(3+decp) + '.' + str(decp) + 'f}'
        return form.format(h,m,s)

class FifoThread(threading.Thread):
    """
    Adds a fifo Queue to a thread in order to store up disasters which are
    added to the fifo for later retrieval. This is to get around the problem
    that otherwise exceptions thrown from withins threaded operations are
    lost.
    """
    def __init__(self, target, fifo, args=()):
        threading.Thread.__init__(self, target=target, args=args)
        self.fifo = fifo

    def run(self):
        """
        Version of run that traps Exceptions and stores
        them in the fifo
        """
        try:
            threading.Thread.run(self)
        except Exception:
            t, v, tb = sys.exc_info()
            error = traceback.format_exception_only(t,v)[0][:-1]
            tback = 'Traceback (most recent call last):\n' + \
                    ''.join(traceback.format_tb(tb))
            self.fifo.put((error, tback))

class DriverError(Exception):
    pass
