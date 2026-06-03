import socket
import time

class PTZController:
    def __init__(self, ip, port=52381):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sequence_number = 1
        
        # VISCA commands
        self.HEADER = bytearray([0x01, 0x00, 0x00, 0x09]) # Payload type and length to be updated
        self.sequence_bytes = bytearray([0x00, 0x00, 0x00, 0x01])

    def _send_command(self, payload):
        # Update sequence number
        self.sequence_bytes = self.sequence_number.to_bytes(4, byteorder='big')
        self.sequence_number += 1
        
        # Payload length
        payload_len = len(payload)
        header = bytearray([0x01, 0x00, (payload_len >> 8) & 0xFF, payload_len & 0xFF])
        
        packet = header + self.sequence_bytes + bytearray(payload)
        try:
            self.sock.sendto(packet, (self.ip, self.port))
        except Exception as e:
            print(f"Error sending command: {e}")

    def ptz_drive(self, pan_speed, tilt_speed, pan_dir, tilt_dir):
        # pan_speed: 0x01 to 0x18
        # tilt_speed: 0x01 to 0x14
        # pan_dir: 1=left, 2=right, 3=stop
        # tilt_dir: 1=up, 2=down, 3=stop
        
        # Clamp speeds
        pan_speed = max(1, min(24, int(pan_speed)))
        tilt_speed = max(1, min(20, int(tilt_speed)))
        
        payload = [0x81, 0x01, 0x06, 0x01, pan_speed, tilt_speed, pan_dir, tilt_dir, 0xFF]
        self._send_command(payload)

    def zoom_drive(self, speed, direction):
        # speed: 0 to 7
        # direction: 1=Tele (In), 2=Wide (Out), 3=Stop
        speed = max(0, min(7, int(speed)))
        
        if direction == 1:
            cmd = 0x20 | speed # 2p
        elif direction == 2:
            cmd = 0x30 | speed # 3p
        else:
            cmd = 0x00 # Stop
            
        payload = [0x81, 0x01, 0x04, 0x07, cmd, 0xFF]
        self._send_command(payload)

    def stop(self):
        self.ptz_drive(1, 1, 3, 3)
        self.zoom_drive(0, 3)

    def move_left(self, speed=10):
        self.ptz_drive(speed, 1, 1, 3)

    def move_right(self, speed=10):
        self.ptz_drive(speed, 1, 2, 3)

    def move_up(self, speed=10):
        self.ptz_drive(1, speed, 3, 1)

    def move_down(self, speed=10):
        self.ptz_drive(1, speed, 3, 2)
