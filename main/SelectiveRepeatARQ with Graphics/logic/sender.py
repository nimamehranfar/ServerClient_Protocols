import random
import socket
import time
from threading import Thread, Lock
import struct
import tkinter as tk

FORMAT = "utf-8"
LOCK = Lock()
HOST = socket.gethostbyname(socket.gethostname())
PORT = 8085
ADDRESS = (HOST, PORT)


class Client:
    def __init__(self, fieldLength=5, fileAddress="C:\\Users\\NM\\Documents\\Python\\SRA\\text.txt", graphiste=None,
                 frameLostProb=-1):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fileAddress = fileAddress
        self.fieldLength = fieldLength
        self.window = Window(fieldLength)
        self.graphiste = graphiste
        self.frameLostProb = frameLostProb
        # self.frameManager = FrameManager(self.client_socket, self.fileAddress, self.window)
        self.frameManager = FrameManager(self.client_socket, self.fileAddress, self.window, self.graphiste,
                                         frameLostProb=self.frameLostProb)
        self.ackReceiver = AckReceiver(self.window, self.frameManager, self.client_socket)

    def client_program(self):
        self.client_socket.connect((HOST, PORT))
        start = time.time()
        self.ackReceiver.start()
        self.frameManager.start()
        self.ackReceiver.join()
        self.frameManager.join()
        end = time.time()
        print("End all")
        print(f"Time to send all the data : {(end - start) * 1000} ms")


class Frame:
    def __init__(self, sequenceNumber, data):
        self.sequenceNumber = sequenceNumber
        self.data = data
        self.fcs = self.generateFCS()
        self.packet = struct.pack("=I", self.sequenceNumber) + struct.pack("=H", self.fcs) + self.data.encode(FORMAT)

    @staticmethod
    def generateFCS():
        # TODO
        return 4


class Window:
    def __init__(self, dataSize, windowSize=None):
        self.dataSize = dataSize
        self.maxWindowSize = 2 ** (dataSize - 1)
        self.transmittedFrames = {}
        self.isTransmitting = True
        if windowSize is not None:
            self.maxWindowSize = min(self.maxWindowSize, windowSize)

    def isNotEmpty(self):
        return len(self.transmittedFrames) > 0

    def saveNumber(self, seqNumber):
        self.transmittedFrames[seqNumber] = [None, False]

    def markAcked(self, seqNumber):
        with LOCK:
            if seqNumber > list(self.transmittedFrames.keys())[0]:
                for key in self.transmittedFrames.keys():
                    if key < seqNumber:
                        self.transmittedFrames[key][1] = True
                    else:
                        break
            elif seqNumber < list(self.transmittedFrames.keys())[0]:
                for key in self.transmittedFrames.keys():
                    if list(self.transmittedFrames.keys())[0] <= key < 2 ** self.dataSize or key < seqNumber:
                        self.transmittedFrames[key][1] = True
                    else:
                        break
            # print(f"Marked {seqNumber}")

    def stop(self):
        with LOCK:
            temp = self.transmittedFrames.copy()
            for key, value in temp.items():
                if value[1]:
                    del self.transmittedFrames[key]
                    # print("Deleted ", key)
                else:
                    break


class FrameManager(Thread):
    HEADER_SIZE = 6

    def __init__(self, client_socket, fileAddress, window, graphiste, frameLostProb):
        Thread.__init__(self)
        self.frames = []
        self.fileAddress = fileAddress
        self.window = window
        self.client_socket = client_socket
        self.graphiste = graphiste
        self.frameLostProb = frameLostProb

    def makePackets(self):
        file = open(self.fileAddress, "r")
        while True:
            data = file.read(self.window.dataSize)
            if not data:
                break
            self.frames.append(Frame(len(self.frames) % 2 ** self.window.dataSize, data))

    def sendAgain(self, seqNum):
        self.window.transmittedFrames[seqNum][0] = time.time()
        if random.random() > self.frameLostProb:
            print(f"Sent again : {self.frames[seqNum].data}")
            self.client_socket.sendall(self.frames[seqNum].packet)

    def run(self):
        if self.graphiste is None:
            self.makePackets()
        packetCount = 0
        self.client_socket.sendall(struct.pack("=I", (len(self.frames) * self.window.dataSize)) +
                                   struct.pack("=H", self.window.dataSize))
        while packetCount < len(self.frames):
            # print(self.window.transmittedFrames, len(self.window.transmittedFrames), self.window.maxWindowSize)
            if len(self.window.transmittedFrames.keys()) < self.window.maxWindowSize:
                print("[Sending] Client is sending a packet ...")
                self.window.saveNumber(packetCount % 2 ** self.window.dataSize)
                SingleFrame(self.client_socket, self.frames[packetCount], self.window, self.frameLostProb).start()
                if self.graphiste is not None:
                    self.graphiste.scrollable_frame.grid_slaves(row=packetCount + 2, column=3)[0]["text"] = "Sent\t"
                    self.graphiste.scrollable_frame.grid_slaves(row=packetCount + 2, column=3)[0]["bg"] = "Green"
                time.sleep(0.00000001 if self.graphiste is None else 1)
                packetCount += 1
        print(self.window.transmittedFrames)
        while len(self.window.transmittedFrames) != 0:
            continue
        self.window.isTransmitting = False
        # self.client_socket.close()
        print("End FrameManager")


class SingleFrame(Thread):
    def __init__(self, client_socket, frame, window, frameLostPorb, timeOut=1):
        Thread.__init__(self)
        self.frame = frame
        self.window = window
        self.timeOut = timeOut
        self.client_socket = client_socket
        self.frameLostProb = frameLostPorb

    def timeOutProtocol(self):
        while self.frame.sequenceNumber in self.window.transmittedFrames.keys() and \
                not self.window.transmittedFrames[self.frame.sequenceNumber][1]:
            with LOCK:
                if self.frame.sequenceNumber in self.window.transmittedFrames.keys() and \
                        time.time() - self.window.transmittedFrames[self.frame.sequenceNumber][0] > self.timeOut:
                    # print("Elapsed : ", time.time() - self.window.transmittedFrames[self.frame.sequenceNumber][0])
                    self.window.transmittedFrames[self.frame.sequenceNumber][0] = time.time()
                    if random.random() > self.frameLostProb:
                        print(f"Sent : {self.frame.data}")
                        self.client_socket.sendall(self.frame.packet)
        self.window.stop()

    def run(self):
        self.window.transmittedFrames[self.frame.sequenceNumber][0] = time.time()
        if random.random() > self.frameLostProb:
            self.client_socket.sendall(self.frame.packet)
        # print(f"Sent {self.frame.packet}")
        self.timeOutProtocol()
        print(f"[Sent] Frame #{self.frame.sequenceNumber} (\"{self.frame.data}\"), sent successfully.\n")


class AckReceiver(Thread):
    def __init__(self, window, frameManager, client_socket):
        Thread.__init__(self)
        self.window = window
        self.client_socket = client_socket
        self.frameManager = frameManager

    def run(self):
        while self.window.isTransmitting:
            ack = self.client_socket.recv(1024)
            if not ack:
                break
            print("Received acknowledgement : ", self.parseAck(ack), "\n")
            typeOfAck, seqNum = self.parseAck(ack)
            if typeOfAck:
                if (seqNum - 1) % 2 ** self.window.dataSize in self.window.transmittedFrames.keys():
                    while not self.window.transmittedFrames[(seqNum - 1) % 2 ** self.window.dataSize][1]:
                        self.window.markAcked(seqNum)
                    if self.frameManager.graphiste is not None:
                        self.frameManager.graphiste.scrollable_frame.grid_slaves(row=seqNum + 1, column=4)[0]["text"] = \
                            "Ack Received\t"
                        self.frameManager.graphiste.scrollable_frame.grid_slaves(row=seqNum + 1, column=4)[0]["bg"] = \
                            "Green"
                    # self.window.stop()
            else:
                self.frameManager.sendAgain(seqNum)
        print("End AckReceiver")
        self.client_socket.close()

    @staticmethod
    def parseAck(ack):
        return struct.unpack("=?", ack[:1])[0], struct.unpack("=I", ack[1:5])[0]


class Graphiste:
    def __init__(self, client):
        self.client = client
        self.client.frameManager.graphiste = self
        self.fieldLength = self.client.fieldLength
        self.root = tk.Tk()
        self.root.geometry("400x300")
        self.client.frameManager.makePackets()
        self.frames = self.client.frameManager.frames
        self.mainFrame = tk.Frame()
        self.canvas = tk.Canvas(self.mainFrame)
        self.scrollbar = tk.Scrollbar(self.mainFrame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

    def startClient(self):
        clientThread = Thread(target=self.client.client_program)
        clientThread.start()

    def start(self):
        c = 1

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # canvas.pack(row=1, column=1)
        # scrollbar.grid(row=1, column=1)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.mainFrame.grid(row=1, column=1)

        frameData = tk.Label(self.scrollable_frame, text="Data")
        frameData.grid(row=1, column=2)
        status = tk.Label(self.scrollable_frame, text="Status")
        status.grid(columnspan=4, row=1, column=2)
        seqNumL = tk.Label(self.scrollable_frame, text="Sequence number")
        seqNumL.grid(row=1, column=1)
        for frame in self.frames:
            seqNumL = tk.Label(master=self.scrollable_frame, text=str((c - 1) % (2 ** self.client.fieldLength)))
            dataL = tk.Label(master=self.scrollable_frame, text=frame.data)
            statusL = tk.Label(master=self.scrollable_frame, text="Not Sent Yet\t", bg="Gray")
            ackL = tk.Label(master=self.scrollable_frame, text="No Ack", bg="Red")
            c += 1
            seqNumL.grid(row=c, column=1)
            dataL.grid(row=c, column=2)
            statusL.grid(row=c, column=3)
            ackL.grid(row=c, column=4)

        start = tk.Button(bd=3, command=self.startClient, text="Start client")
        start.grid(row=c + 2, column=1)
        print()
        self.root.grid_slaves(row=2, column=3)
        tk.mainloop()


if __name__ == '__main__':
    Graphiste(Client(5)).start()
