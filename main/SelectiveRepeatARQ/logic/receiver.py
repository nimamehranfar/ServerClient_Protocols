import socket
import struct
import time
from collections import OrderedDict
from threading import Thread

FORMAT = "utf-8"
HOST = socket.gethostbyname(socket.gethostname())
PORT = 8085
ADDRESS = (HOST, PORT)  # tarife connection be surate global


class Server:  # tarife etelaate marbute baraye etesal be ersal konande
    def __init__(self, rangeOfML=40):
        self.server_socket = None
        self.rangeOfML = rangeOfML
        self.packetManager = None
        self.fieldLength = None

    def server_program(self):  # etesal be ersal konande
        print(f"[STARTING] Server is starting ...")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(ADDRESS)
        self.server_socket.listen()
        # runningTimes = OrderedDict()
        for i in range(self.rangeOfML):
            print(f"[LISTENING] Server is listening on {HOST}")
            conn, addr = self.server_socket.accept()
            print('[CONNECTING] Connected by', addr, "\n\n")
            start = time.time()  # starte timer
            data = conn.recv(1024)  # daryaft frame
            dataSize = struct.unpack("=I", data[:4])[0]
            self.fieldLength = struct.unpack("=H", data[4:6])[0]  # estekhraj field length
            # window = Window(dataSize)
            self.packetManager = PacketManager(conn, addr, self.fieldLength, dataSize)
            self.packetManager.start()  # run kardane packet manager
            end = time.time()  # etemam barname
            print(f"Elapsed time : {(end - start) * 1000} ms\n")
            # if self.fieldLength not in runningTimes.keys():
            #     runningTimes[self.fieldLength] = []
            # runningTimes[self.fieldLength].append((end - start) * 1000)
            # print(runningTimes)


class PacketManager:
    def __init__(self, conn, addr, fieldLength, dataSize=60):
        self.conn = conn
        self.buffer = {}
        self.addr = addr
        self.lastAck = None
        self.expectedFrame = 0
        self.received = 0
        self.result = ''
        self.lastRej = None
        self.maxWindowSize = 2 ** (fieldLength - 1)
        self.fieldLength = fieldLength
        self.dataSize = dataSize

    def start(self):
        while self.received < self.dataSize:  # daryaft baste ha ta zamane residan tul baste ha be tul kolli dade
            data = self.conn.recv(1024)
            if not data:
                break
            seqNum = struct.unpack("=I", data[:4])[0]

            print(f"[{self.addr}] Sequence number : {seqNum}, Data : \"{data.decode(FORMAT)[6:]}\"")
            self.sendAck(data)  # ack zadan be dade ha be shomare khpdeshun
        print(self.result)
        self.conn.close()

    def sendAck(self, data):  # tabe ack zadan
        seqNum = struct.unpack("=I", data[:4])[0]

        print("Server's buffer : ", self.buffer)

        if self.expectedFrame == seqNum:  # dade mored entezar daryaft shod
            self.conn.sendall(struct.pack("=?", True) + struct.pack("=I", (seqNum + 1) % (2 ** self.fieldLength)))
            print(f"[Sending] Send acknowledgement for frame #{seqNum}\n\n\n")
            self.result += data.decode(FORMAT)[6:]
            self.received += self.fieldLength
            self.expectedFrame += 1
            # print("Result First cond : ", self.result)
            if len(self.buffer) != 0 and seqNum in self.buffer:
                del self.buffer[seqNum]

        elif len(
                self.buffer) != 0 and seqNum in self.buffer.keys():  # dade kharej az tartib daryaft shod vali dar buffer hast
            # print("Third condition")
            self.buffer[seqNum] = data.decode(FORMAT)[6:]
        elif (len(self.buffer) == 0 and (
                self.expectedFrame < seqNum < 2 ** self.fieldLength  # dade kharej az tartib daryaft shod vali dar buffer nist
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

        if len(self.buffer) != 0:  # buffer dar result ezafe kon va az buffer hazf kon
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
                self.conn.sendall(struct.pack("=?", True) + struct.pack("=I",
                                                                        self.expectedFrame  # agar expected frame hanuz nayumade dobare nack beferest biyad
                                                                        % (2 ** self.fieldLength)))
                self.lastRej = self.expectedFrame % (2 ** self.fieldLength)

        self.expectedFrame %= 2 ** self.fieldLength
        # if len(self.buffer) != 0: self.conn.sendall(struct.pack("=?", False) + struct.pack("=I", self.expectedFrame
        # % (2 ** self.fieldLength)))


if __name__ == '__main__':  # start kon
    server = Server()
    serverThread = Thread(target=server.server_program)
    serverThread.start()
