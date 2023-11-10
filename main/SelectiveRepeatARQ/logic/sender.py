import random
import socket
import time
from threading import Thread, Lock
import struct

FORMAT = "utf-8"
LOCK = Lock()
HOST = socket.gethostbyname(socket.gethostname())
PORT = 8085
ADDRESS = (HOST, PORT)  # tarife connection be surate global


class Client:  # tarife etelaate marbute baraye etesal be daryaft konande
    def __init__(self, fieldLength=6, fileAddress="C:\\Users\\NM\\Documents\\Python\\SRA\\text.txt", frameLostProb=-1):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fileAddress = fileAddress
        self.fieldLength = fieldLength
        self.window = Window(fieldLength)
        self.frameLostProb = frameLostProb
        # self.frameManager = FrameManager(self.client_socket, self.fileAddress, self.window)
        self.frameManager = FrameManager(self.client_socket, self.fileAddress, self.window,
                                         frameLostProb=self.frameLostProb)
        self.ackReceiver = AckReceiver(self.window, self.frameManager, self.client_socket)

    def client_program(self):
        self.client_socket.connect((HOST, PORT))
        start = time.time()  # starte timer
        self.ackReceiver.start()  # start kardane thread haye sazande frame va girande ack
        self.frameManager.start()
        self.ackReceiver.join()
        self.frameManager.join()
        end = time.time()  # etemam barname
        print("End all")
        print(f"Time to send all the data : {(end - start) * 1000} ms")


class Frame:  # zakhire etelaate baste
    def __init__(self, sequenceNumber, data):
        self.sequenceNumber = sequenceNumber
        self.data = data
        self.fcs = 4
        self.packet = struct.pack("=I", self.sequenceNumber) + struct.pack("=H", self.fcs) + self.data.encode(FORMAT)


class Window:  # gereftane etelaate panjare laghzan va nezarat bar ersal va daryaf ack ha va taghyire frame haye panjare dar surate niyaz
    def __init__(self, dataSize, windowSize=None):
        self.dataSize = dataSize
        self.maxWindowSize = 2 ** (dataSize - 1)
        self.transmittedFrames = {}
        self.isTransmitting = True
        if windowSize is not None:
            self.maxWindowSize = min(self.maxWindowSize, windowSize)

    def isNotEmpty(self):  # age panjare khali nist
        return len(self.transmittedFrames) > 0

    def saveNumber(self, seqNumber):  # save kardane seq num frame haye ersali
        self.transmittedFrames[seqNumber] = [None, False]

    def markAcked(self, seqNumber):  # alamat gozari frame haye ack shode
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
            print(f"Marked {seqNumber}")

    def stop(self):  # hazf frame haye ack shode az list ersal shode ha
        with LOCK:
            temp = self.transmittedFrames.copy()
            for key, value in temp.items():
                if value[1]:
                    del self.transmittedFrames[key]
                    # print("Deleted ", key)
                else:
                    break


class FrameManager(Thread):  # sakht va ersale baste ha
    HEADER_SIZE = 6

    def __init__(self, client_socket, fileAddress, window, frameLostProb):
        Thread.__init__(self)
        self.frames = []
        self.fileAddress = fileAddress
        self.window = window
        self.client_socket = client_socket
        self.frameLostProb = frameLostProb

    def makePackets(self):  # khandane file va sakhtane packet ha
        file = open(self.fileAddress, "r")
        while True:
            data = file.read(self.window.dataSize)
            if not data:
                break
            self.frames.append(Frame(len(self.frames) % 2 ** self.window.dataSize, data))

    def sendAgain(self, seqNum):  # ersale dobare packet haye fail ya gom shode
        self.window.transmittedFrames[seqNum][0] = time.time()
        if random.random() > self.frameLostProb:
            print(f"Sent again : {self.frames[seqNum].data}")
            self.client_socket.sendall(self.frames[seqNum].packet)

    def run(self):  # ferestadane frame haye dakhel panjare ke az packet ha sakhte shodan

        packetCount = 0
        self.client_socket.sendall(struct.pack("=I", (len(self.frames) * self.window.dataSize)) +
                                   struct.pack("=H", self.window.dataSize))
        while packetCount < len(self.frames):
            # print(self.window.transmittedFrames, len(self.window.transmittedFrames), self.window.maxWindowSize)
            if len(self.window.transmittedFrames.keys()) < self.window.maxWindowSize:
                print("[Sending] Client is sending a packet ...")
                self.window.saveNumber(packetCount % 2 ** self.window.dataSize)
                SingleFrame(self.client_socket, self.frames[packetCount], self.window, self.frameLostProb).start()
                packetCount += 1
        print(self.window.transmittedFrames)
        while len(self.window.transmittedFrames) != 0:
            continue
        self.window.isTransmitting = False
        # self.client_socket.close()
        print("End FrameManager")


class SingleFrame(Thread):  # modiriyate har frame be tanhayi
    def __init__(self, client_socket, frame, window, frameLostPorb, timeOut=2):
        Thread.__init__(self)
        self.frame = frame
        self.window = window
        self.timeOut = timeOut
        self.client_socket = client_socket
        self.frameLostProb = frameLostPorb

    def timeOutProtocol(self):  # taskhis timeout va ferestadane dobare
        while self.frame.sequenceNumber in self.window.transmittedFrames.keys() and \
                not self.window.transmittedFrames[self.frame.sequenceNumber][1]:
            with LOCK:
                if self.frame.sequenceNumber in self.window.transmittedFrames.keys() and \
                        time.time() - self.window.transmittedFrames[self.frame.sequenceNumber][0] > self.timeOut:
                    # print("Elapsed : ", time.time() - self.window.transmittedFrames[self.frame.sequenceNumber][0])
                    self.window.transmittedFrames[self.frame.sequenceNumber][0] = time.time()
                    if random.random() > self.frameLostProb:
                        print(f"Sent : {self.frame.data}")
                        # self.client_socket.connect((HOST, PORT))
                        self.client_socket.sendall(self.frame.packet)
        self.window.stop()

    def run(self):  # tashkhis noise dasti va ferestadan ya naferestadane packet
        self.window.transmittedFrames[self.frame.sequenceNumber][0] = time.time()
        if random.random() > self.frameLostProb:
            self.client_socket.sendall(self.frame.packet)
        # print(f"Sent {self.frame.packet}")
        self.timeOutProtocol()
        print(f"[Sent] Frame #{self.frame.sequenceNumber} (\"{self.frame.data}\"), sent successfully.\n")


class AckReceiver(Thread):  # daryafte ack ha va nak ha
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
            if typeOfAck:  # hazf baste ack shode az list ersal shode ha va alamat gozari an
                if (seqNum - 1) % 2 ** self.window.dataSize in self.window.transmittedFrames.keys():
                    while not self.window.transmittedFrames[(seqNum - 1) % 2 ** self.window.dataSize][1]:
                        self.window.markAcked(seqNum)
            else:  # ferestadane dobare baste nak shode
                self.frameManager.sendAgain(seqNum)
        print("End AckReceiver")
        self.client_socket.close()

    @staticmethod
    def parseAck(ack):  # tajziye baste daryafti va estekhraje true ya false va seq number
        return struct.unpack("=?", ack[:1])[0], struct.unpack("=I", ack[1:5])[0]


if __name__ == '__main__':  # start kon
    client = Client(5)
    client.frameManager.makePackets()
    clientThread = Thread(target=client.client_program())
    clientThread.start()
