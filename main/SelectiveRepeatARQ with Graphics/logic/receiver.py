import socket
import struct
import time
from collections import OrderedDict
import tkinter as tk
from threading import Thread

FORMAT = "utf-8"
HOST = socket.gethostbyname(socket.gethostname())
PORT = 8085
ADDRESS = (HOST, PORT)


class Server:
    def __init__(self, rangeOfML=40):
        self.graphiste = None
        self.server_socket = None
        self.rangeOfML = rangeOfML
        self.packetManager = None
        self.fieldLength = None

    def server_program(self):
        print(f"[STARTING] Server is starting ...")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(ADDRESS)
        self.server_socket.listen()
        runningTimes = OrderedDict()
        for i in range(self.rangeOfML):
            print(f"[LISTENING] Server is listening on {HOST}")
            conn, addr = self.server_socket.accept()
            print('[CONNECTING] Connected by', addr, "\n\n")
            start = time.time()
            data = conn.recv(1024)
            dataSize = struct.unpack("=I", data[:4])[0]
            self.fieldLength = struct.unpack("=H", data[4:6])[0]
            # window = Window(dataSize)
            self.packetManager = PacketManager(conn, addr, self.fieldLength, self.graphiste, dataSize)
            self.packetManager.start()
            end = time.time()
            print(f"Elapsed time : {(end - start) * 1000} ms\n")
            if self.fieldLength not in runningTimes.keys():
                runningTimes[self.fieldLength] = []
            runningTimes[self.fieldLength].append((end - start) * 1000)
            print(runningTimes)


class PacketManager:
    def __init__(self, conn, addr, fieldLength, graphiste, dataSize=60):
        self.conn = conn
        self.buffer = {}
        self.addr = addr
        self.lastAck = None
        self.expectedFrame = 0
        self.received = 0
        self.result = ''
        self.lastRej = None
        self.graphiste = graphiste
        self.maxWindowSize = 2 ** (fieldLength - 1)
        self.fieldLength = fieldLength
        self.dataSize = dataSize

    def sendAck(self, data):

        seqNum = struct.unpack("=I", data[:4])[0]

        print("Server's buffer : ", self.buffer)

        if self.expectedFrame == seqNum:
            self.conn.sendall(struct.pack("=?", True) + struct.pack("=I", (seqNum + 1) % (2 ** self.fieldLength)))
            print(f"[Sending] Send acknowledgement for frame #{seqNum}\n\n\n")
            self.result += data.decode(FORMAT)[6:]
            self.received += self.fieldLength
            self.expectedFrame += 1
            # print("Result First cond : ", self.result)
            if len(self.buffer) != 0 and seqNum in self.buffer:
                del self.buffer[seqNum]

        elif len(self.buffer) != 0 and seqNum in self.buffer.keys():
            # print("Third condition")
            self.buffer[seqNum] = data.decode(FORMAT)[6:]
        elif (len(self.buffer) == 0 and (self.expectedFrame < seqNum < 2 ** self.fieldLength
                                         or seqNum < (self.expectedFrame + self.maxWindowSize) % 2 ** self.fieldLength)) \
                or ((self.expectedFrame < seqNum < (self.expectedFrame + self.maxWindowSize) % 2 ** self.fieldLength
                     or seqNum < (self.expectedFrame - self.maxWindowSize) % 2 ** self.fieldLength)
                    and 0 < len(self.buffer) < self.maxWindowSize):
            # print("Second condition")
            start = self.expectedFrame if len(self.buffer) == 0 else \
                (list(self.buffer.keys())[len(self.buffer.keys()) - 1] + 1) % (2 ** self.fieldLength)
            # print("Start : ", start)
            for i in range(start, seqNum if seqNum >= start else 2 ** self.fieldLength + seqNum):
                if i % 2 ** self.fieldLength not in self.buffer:
                    self.buffer[i % 2 ** self.fieldLength] = None
                    print(f"[Sending] Sent reject for frame #{i % (2 ** self.fieldLength)}")

            self.buffer[seqNum] = data.decode(FORMAT)[6:]

        if len(self.buffer) != 0:
            temp = self.buffer.copy().keys()
            for k in temp:
                if self.buffer[k] is not None:
                    self.result += self.buffer[k]
                    self.received += self.fieldLength
                    del self.buffer[k]
                    self.expectedFrame += 1
                else:
                    break
            # print(self.buffer, self.expectedFrame)

            if len(self.buffer) != 0 and self.lastRej is None or self.lastRej == self.expectedFrame % \
                    (2 ** self.fieldLength):
                self.conn.sendall(struct.pack("=?", True) + struct.pack("=I", self.expectedFrame
                                                                        % (2 ** self.fieldLength)))
                self.lastRej = self.expectedFrame % (2 ** self.fieldLength)

        self.expectedFrame %= 2 ** self.fieldLength
        # if len(self.buffer) != 0: self.conn.sendall(struct.pack("=?", False) + struct.pack("=I", self.expectedFrame
        # % (2 ** self.fieldLength)))

    def start(self):
        while self.received < self.dataSize:
            # print("Memory : ", self.memory)
            data = self.conn.recv(1024)
            if not data:
                break
            seqNum = struct.unpack("=I", data[:4])[0]
            if self.graphiste is not None:
                self.graphiste.receive(data.decode(FORMAT)[6:])
            print(f"[{self.addr}] Sequence number : {seqNum}, Data : \"{data.decode(FORMAT)[6:]}\"")
            self.sendAck(data)
        print(self.result)
        self.conn.close()


class Graphiste:
    def __init__(self, server):
        self.server = server
        self.server.graphiste = self
        self.server.graphiste = self
        self.fieldLength = self.server.fieldLength
        self.root = tk.Tk()
        self.count = 0
        # self.message = tk.Label(text="\t\t[LISTENING] Server is listening on {HOST}\t\t")
        self.root.geometry("400x400")
        # self.message.grid(row=2, column=2)

    def start(self):
        serverThread = Thread(target=self.server.server_program)
        serverThread.start()
        tk.mainloop()

    def receive(self, data):
        self.count += 1
        label = tk.Label(text=data)
        label.grid(row=int(self.count / 10), column=self.count % 10)


if __name__ == '__main__':
    Graphiste(Server()).start()
