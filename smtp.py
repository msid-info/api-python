import socket
import ssl

# Define the SMTP server's hostname and port
SMTP_SERVER = 'brudlab.mail.protection.outlook.com'
SMTP_PORT = 25

# Create a socket object and connect to the SMTP server
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SMTP_SERVER, SMTP_PORT))

def send_cmd(cmd: str) -> None:
    client_socket.send(f"{cmd}\r\n".encode())


def recv_data() -> str:
    return client_socket.recv(1024).decode()

# Receive the server's welcome message
print(recv_data())

# Send the EHLO command to initiate the SMTP session
send_cmd("EHLO example.com")
print(recv_data())

# interactive terminal session
while True:
    cmd = input(">> ")
    send_cmd(cmd)
    
    # upgrade to TLS
    if cmd.lower() == "starttls":
        print(recv_data())

        # upgrade the socket to TLS
        client_socket = ssl.wrap_socket(client_socket)

        continue


    print(recv_data())

    if cmd.lower() == "quit":
        break


# Close the connection
client_socket.close()
