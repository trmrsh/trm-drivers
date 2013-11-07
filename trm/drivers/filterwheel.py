"""
Class for accessing the ultraspec filter wheel

Written by Stu.
"""
import serial

class FilterWheel(object):

	def __init__(self,port='/dev/filterwheel',default_timeout=2):
		'''initialise filter wheel. doesnt actually connect'''
		self.port = '/dev/filterwheel'
		self.baudrate = 19200
		self.default_timeout = default_timeout
		self.connected = False
		self.initialised = False
		
	def connect(self):
		'''actually connects to the serial port of the filter wheel'''
		self.ser = serial.Serial(self.port,baudrate=self.baudrate,
					 timeout=self.default_timeout)
		self.connected = True
		
	def sendCommand(self,str):
		'''wrapper function to send commands to filter wheel'''
		if not self.initialised:
			raise FilterWheelError(
				'Filter wheel not initialised')

		if not self.connected:
			raise FilterWheelError(
				'Filter wheel not connected')

		if str=='WHOME' or str.startswith('WGOTO'):
			self.ser.setTimeout(30)
		else:
			self.ser.setTimeout(self.default_timeout)
		self.ser.write(str+'\r\n',)
		retVal = self.ser.readline()

		#return command with leading and trailing whitespace removed
		return retVal.lstrip().rstrip()
		
	def close(self):
		'''disables serial mode and disconnects from serial port'''
		# disable serial mode operation for the serial port
		self.sendCommand("WEXITS")
		self.ser.close()
		self.connected = False
		self.initialised = False
		
	def initialise(self):
		'''
		enables serial mode on the filter wheel. this 
		should always be the first command run after 
		connecting to the wheel
		'''
		response = self.sendCommand("WSMODE")
		if response != "!":
			raise FilterWheelError("Could not initialise wheel for serial commands")
		self.initialised = True
		
	def home(self):
		'''sends a home command to the wheel. 
		this shouldn't be needed very often, only if the slide has
		got into a confused state'''
		response = self.sendCommand("WHOME")
		if response == "ER=3":
			raise FilterWheelError("Could not ID filter wheel after HOME")
		elif response == "ER=1":
			raise FilterWheelError("Filter wheel homing took too many steps")
			
	def getID(self):
		'''returns ID of filter wheel, and checks for valid response'''
		response = self.sendCommand("WIDENT").strip()
		validIDs = ['A','B','C','D','E']
		if not response in validIDs:
			raise FilterWheelError("Bad filter wheel ID\n"+response)
		return response
		
	def getPos(self):
		'''gets current position of wheel (from 1 to 6)'''
		response = self.sendCommand("WFILTR")
		filtNum = int(response)
		return filtNum
		
	def getNames(self):
		'''returns the possible names. should always be 123456'''
		response = self.sendCommand("WREAD")
		return response.split()
		
	def goto(self,position):
		'''moves to desired position. positions 1 thru 6 are valid'''
		if position > 6 or position < 1:
			raise FilterWheelError("Invalid filter wheel position")
		response = self.sendCommand("WGOTO"+repr(position))
		if response == "ER=4":
			raise FilterWheelError("filter wheel is stuck")
		if response == "ER=5":
			raise FilterWheelError("requested position (" + position +
					") not valid")
		if response == "ER=6":
			raise FilterWheelError("filter wheel is slipping")

		if response != "*":
			raise FilterWheelError("unrecognised error " + response)
		
	def reSpawn(self):
		'''this can be used to fix a non-responding filter wheel'''
		self.close()
		time.sleep(2)
		self.connect()
		self.init()
		self.home()
	
class FilterWheelError(Exception):
	pass

if __name__ == "__main__":
	
	wheel = FilterWheel()
	try:
		wheel.connect()
		wheel.initialise()
		print 'Started'
		print 'Currently in filter position ', wheel.getPos()
		print 'This is filter wheel ', wheel.getID()
		print 'Available positions: ', wheel.getNames()
		print "GOTO 3"
		wheel.goto(3)
		print "HOME"
		wheel.home()
		print 'Disconnecting'
		wheel.close()
		print 'Finished normally'
	except:
		wheel.close()
		print 'Finished badly'
		
