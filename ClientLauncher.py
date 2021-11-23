import sys
from tkinter import Tk
from Client import Client

if __name__ == "__main__":
	try:
		serverAddr = sys.argv[1]
		serverPort = int(sys.argv[2])
		rtpPort = int(sys.argv[3])
		fileName = sys.argv[4]	
		print((serverAddr,serverPort,rtpPort,fileName))
	except:
		serverAddr='127.0.0.1'
		serverPort=1025
		rtpPort=2000
		fileName='movie.Mjpeg'
		print((serverAddr,serverPort,rtpPort,fileName))
		print("[Usage: ClientLauncher.py Server_name Server_port RTP_port Video_file]\n")	
	
	root = Tk()
	
	# Create a new client
	app = Client(root, serverAddr, serverPort, rtpPort, fileName)
	app.master.title("RTPClient")	
	root.mainloop()
	