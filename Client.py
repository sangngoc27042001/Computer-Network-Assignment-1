from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk,ImageDraw ,ImageFont
import socket, threading, sys, traceback, os
from time import time
from RtpPacket import RtpPacket
import sys

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
a=0
class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	REPLAY=4
	DESCRIBE=5
	SPEED=6

	speed_arr=['Speed: x1','Speed: x1.25','Speed: x1.5','Speed: x2','Speed: x4','Speed: x0.5','Speed: x0.75']
	speed_idx=0
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = serverport
		self.rtpPort = rtpport
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.current_fps=0
		self.prev_fps=None #for counting the fps

		self.video_current_data_rate=0
		self.prev_datarate=None 
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button #lẽ ra là setup
		self.setup = Button(self.master, width=16, padx=3, pady=3)
		self.setup["text"] = "Play"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# # Create Play button		
		# self.start = Button(self.master, width=16, padx=3, pady=3)
		# self.start["text"] = "Play"
		# self.start["command"] = self.playMovie
		# self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=16, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Describe button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Describe"
		self.pause["command"] = self.describeMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)

		# Create Teardown button
		self.teardown = Button(self.master, width=16, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create Replay button
		self.teardown = Button(self.master, width=16, padx=3, pady=3)
		self.teardown["text"] = "Replay"
		self.teardown["command"] =  self.replayMovie
		self.teardown.grid(row=1, column=4, padx=2, pady=2)

		# Create Speed button
		self.speed = Button(self.master, width=16, padx=3, pady=3)
		self.speed["text"] = self.speed_arr[self.speed_idx]
		self.speed["command"] =  self.speedMovie
		self.speed.grid(row=2, column=0, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=5, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
		else:
    			self.playMovie()
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	
	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def describeMovie(self):
    		self.sendRtspRequest(self.DESCRIBE)

	def replayMovie(self):
		self.teardownAcked = 0
		self.frameNbr = 0
		self.sendRtspRequest(self.REPLAY)

	def speedMovie(self):
		self.sendRtspRequest(self.SPEED)
		pass
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					
					if self.prev_datarate==None:
						self.prev_datarate=time()

					self.video_current_data_rate=int(sys.getsizeof(rtpPacket.getPayload())/(time()-self.prev_datarate)/1000)
					print("Current Seq Num: " + str(currFrameNbr)+' '+str(self.video_current_data_rate))
					self.prev_datarate=time()
										
					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		self.current_fps=0
		if self.prev_fps == None:
    			self.prev_fps=time()
		else:
				self.current_fps=round(1/(time()-self.prev_fps),2)
				self.prev_fps=time()
		img=Image.open(imageFile)
		draw = ImageDraw.Draw(img)
		draw.text((5, 5),"fps: "+str(self.current_fps),(255,255,255))
		photo = ImageTk.PhotoImage(img)
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP:
			self.rtpSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = 1
			
			# Write the RTSP request to be sent.
			# request = ...
			request = "SETUP " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nTransport: RTP/UDP; client_port= " + str(self.rtpPort)
			self.rtspSocket.send(request.encode("utf-8"))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			# request = ...
			request = "PLAY " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) +"\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY
		# Pause request
		elif requestCode == self.PAUSE:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			# request = ...
			request = "PAUSE " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = "TEARDOWN " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.TEARDOWN
		elif requestCode == self.REPLAY and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = "REPLAY " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			self.requestSent = self.REPLAY
		elif requestCode == self.DESCRIBE and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = "DESCRIBE " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			self.requestSent = self.DESCRIBE
		elif requestCode == self.SPEED and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = "SPEED " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			self.rtspSocket.send(request.encode("utf-8"))
			self.requestSent = self.SPEED
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		# ...
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		print("-"*40 + "\nData received:\n" + data)
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])

		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						# self.state = ...
						self.state = self.READY
						
						# Open RTP port.
						self.openRtpPort() 
						self.playMovie()
					elif self.requestSent == self.PLAY:
						# self.state = ...
						self.state = self.PLAYING
					elif self.requestSent == self.PAUSE:
						# self.state = ...
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.REPLAY:
						# self.state = ...
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
						self.playMovie()
					elif self.requestSent == self.TEARDOWN:
						# self.state = ...
						self.state = self.INIT
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1
					elif self.requestSent == self.DESCRIBE:
						# self.state = ...
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
						tkMessageBox.showinfo(title='Information', message='File name: '+self.fileName+'\n'+data.split('\n')[2]+'\nFPS: '+str(self.current_fps)+'\nVideo Data Rate: '+str(self.video_current_data_rate)+' kBytes')
					elif self.requestSent == self.SPEED:
						if self.speed_idx==6:
							self.speed_idx=0
						else:
							self.speed_idx+=1
						self.speed["text"] = self.speed_arr[self.speed_idx]
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		self.rtpSocket.settimeout(0.5)
		# Set the timeout value of the socket to 0.5sec
		# ...
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			# ...
			self.rtpSocket.bind((self.serverAddr,self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()