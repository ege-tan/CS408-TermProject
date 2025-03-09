import tkinter as tk  # import the tkinter library for creating the GUI.
from tkinter import messagebox, filedialog  # import specific modules for pop-up dialogs and file selection.
import socket  # import the socket library to enable TCP/IP communication.
import threading  # import the threading library to handle operations without blocking the GUI.
import os  # for file system operations.
import json  # for encoding and decoding JSON data.

# client variables
client_socket = None  # main socket for communication with the server.
server_address = None  # storing server's IP address and port.
username = None  # the username provided by the client.
connected = False  # to track the connection status.
notification_socket = None  # to handle real-time notifications from the server.


def connect_notification_socket():
    """
    connects the client to the server's notification socket to listen
    """
    global notification_socket
    try:
        ip, _ = server_address  # extract the IP address from the server_address
        notification_socket = socket.socket(socket.AF_INET,
                                            socket.SOCK_STREAM)  # create a new TCP socket for notifications
        notification_socket.connect((ip, 9001))  # connect to the server's notification port (9001)
        threading.Thread(target=listen_for_notifications,
                         daemon=True).start()  # start a thread to listen for notifications
        notification_socket.sendall(username.encode())  # send the username to the server for identification
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to connect to notification socket: {e}")  # if the connection fails, display an error message


def listen_for_notifications():
    """
    listens for notifications from the server and logs them to the GUI.
    """
    while True:
        try:
            notification_message = notification_socket.recv(
                1024).decode()  # receive a notification message from the server.
            log_message(notification_message)  # log the received message in the GUI.
        except:
            break  # Exit the loop if the notification socket is closed.


def connect_to_server():
    """
    Establishes a connection to the server and sends the username based on connection
    """
    global client_socket, server_address, username, connected
    try:
        ip = ip_entry.get().strip()  # get the server's IP address from the GUI input
        port = port_entry.get().strip()  # get the server's port from the GUI input
        username_input = username_entry.get().strip()  # Get the username from the GUI input

        if not ip or not port or not username_input:
            messagebox.showerror("Error",
                                 "IP, Port, and Username must all be provided.")  # if any field is empty, show error.
            return

        if not port.isdigit():  # checks if the port is a valid number or not
            messagebox.showerror("Error", "Port must be a valid number.")  # if the port is invalid, error occurs.
            return

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create a new TCP socket for communication.
        server_address = (ip, int(port))  # create a tuple of the server's IP and port.
        client_socket.connect(server_address)  # establish a connection to the server using the socket.
        client_socket.sendall(username_input.encode())  # Send the username to the server for identification.
        response = client_socket.recv(1024).decode()  # receiving of the server's response.

        # check for errors in response.
        if "ERROR" in response:
            messagebox.showerror("Error", response)  # show an error if the server rejects the connection.
            client_socket.close()  # Closing the connection if connection is rejected
            return

        username = username_input  # set the username, if the connection is successful
        connected = True  # Since it is connected now, connect variable became True
        log_message(f"Connected to server at {ip}:{port} as '{username}'.")  # Log the connection status in the GUI

        connect_notification_socket()  # connect to the notification socket

        connect_button.config(state="disabled")
        disconnect_button.config(state="normal")
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to connect to server: {str(e)}")  # display an error message if the connection fails.


def upload_file_thread():
    """
    Starts a thread to upload file in GUI.
    """
    threading.Thread(target=upload_file, daemon=True).start()  # start of a new thread for uploading a file


def disconnect_from_server():
    """
    Disconnects the client from the server
    """
    global client_socket, connected
    try:
        if connected:  # Check if the client is connected to the server.
            client_socket.sendall("DISCONNECT".encode())  # notify the server about disconnection.
            client_socket.close()  # Close the socket connection.
            connected = False  # Update the connection status as false since it is disconnecting from the server
            log_message("Disconnected from server.")  # log the disconnection in the GUI.
            connect_button.config(state="normal")
            disconnect_button.config(state="disabled")
    except Exception as e:
        log_message(f"Error during disconnection: {str(e)}")  # log any error that occurs during disconnection.


def upload_file():
    """
    Allows the client to upload a file to the server side
    """
    try:
        file_path = filedialog.askopenfilename(title="Select File to Upload")  # it opens a file selection
        print(file_path)
        if not file_path:  # Check if the user canceled the file selection.
            log_message("No file selected for upload.")
            return

        filename = os.path.basename(file_path)  # it extracts the filename
        client_socket.sendall("UPLOAD".encode())  # notifies the server about the upload.

        client_socket.sendall(filename.encode())  # Send the filename to the server
        print(filename, file_path)

        # Handle the server's acknowledgment.
        ack = client_socket.recv(1024).decode()
        print(ack)
        if ack == "Override":
            log_message(
                "The existing file was overwritten.")  # logging a message if the server overwrites an existing file.
        elif ack == "New":
            log_message("New file saved.")  # Log if the server saves a new file.
        else:
            log_message(
                "Error: Unexpected server response.")  # logging an error message for unexpected server responses
            return
        print("ok0")
        with open(file_path, "rb") as file:  # Open the selected file in binary read mode, to analyze the file
            while chunk := file.read(4096):  # it reads the file in chunks of 4096 bytes.
                client_socket.sendall(chunk)  # Send each chunk to the server.
        print("ok1")
        client_socket.sendall(b"EOFe")  # lastly it sends an end-of-file marker to the server.

        log_message(client_socket.recv(1024).decode())  # log the server's response after the upload is complete
        print("ok2")
    except Exception as e:
        log_message(
            f"Error during file upload: {e}")  # logging any error message if error occurs during the file upload.


def request_file_list():
    """
    Requests the list of available files from the server
    """
    try:
        if not connected:  # it checks that whether the client is connected to the server or not
            messagebox.showerror("Error", "You must connect to a server first.")
            return

        client_socket.sendall("LIST".encode())  # send a command to request the file list from the server.
        response = client_socket.recv(4096).decode()  # it receives the server's response containing the file list
        file_list = json.loads(response)  # Decode the JSON-encoded file list
        log_message(f"Available files: {file_list}")  # Log the available files
    except Exception as e:
        log_message(
            f"Error during file list request: {str(e)}")  # logging any error message if error occurs during the file upload.


def download_file():
    """
    Downloads a file from the server to the client's local machine.
    """
    try:
        if not connected or client_socket is None:  # it ensures the client is connected.
            messagebox.showerror("Error", "You must connect to the server first.")
            return

        filename = filename_entry.get().strip()  # get the filename to download from the user input.
        if not filename:  # it ensures that the user provides a filename, if not provides an error message
            messagebox.showerror("Error", "Filename must be provided.")
            return

        save_path = filedialog.askdirectory(
            title="Select Directory to Save File")  # ask the user to select a save directory
        if not save_path:  # it checks that if the user canceled this selection operation
            log_message("Download canceled by user.")
            return

        client_socket.sendall("DOWNLOAD".encode())  # notification of the server about the download request
        client_socket.sendall(filename.encode())  # Send the filename to the server.

        response = client_socket.recv(1024).decode()  # it receives the server's acknowledgment.
        if response != "FILENAME RECEIVED":  # check if the server acknowledges the filename
            log_message(f"Error: {response}")  ###logging any error message if error occurs during the file upload
            return

        file_path = os.path.join(save_path, filename)  # file_path variable, full path, for saving the downloaded file
        with open(file_path, "wb") as file:  # it opens the file in binary write mode.
            while True:
                data = client_socket.recv(4096)  # it again receives file data in chunks
                if data.endswith(b"EOFe"):  # it checks for the end-of-file marker
                    file.write(data[:-4])  # it writes the data excluding the EOF marker
                    break
                file.write(data)  # write the received data to the file

        log_message(f"File '{filename}' downloaded successfully to '{file_path}'.")  # it logs the successful download.
    except Exception as e:
        log_message(
            f"Error during file download: {str(e)}")  ##logging any error message if error occurs during the file upload

def download_file_thread():
    """
    Starts a thread to handle the file download operation
    """
    threading.Thread(target=download_file, daemon=True).start()  # it starts a new thread for downloading a file


def delete_file():
    """
    Sends a delete request to the server for a specified file.
    """
    try:
        if not connected:  # it ensures the client is connected to the server.
            messagebox.showerror("Error", "You must connect to a server first.")
            return

        filename = filename_entry.get().strip()  # get the filename to delete from the user input

        if not filename:  # it ensures that the user provides a filename.
            messagebox.showerror("Error", "Filename must be provided.")
            return

        client_socket.sendall("DELETE".encode())  # it notifies the server about the delete request
        client_socket.sendall(filename.encode())  # it sends the filename to the server

        response = client_socket.recv(1024).decode()  # it receives the server's response.
        log_message(response)  # logging of the server's response
    except Exception as e:
        log_message(f"Error during file deletion: {str(e)}")  # Log any error that occurs during the operation.


def log_message(message):
    """
    Logs a message in the GUI's log listbox.
    """
    log_listbox.insert(tk.END, message)  # Insert the message at the end of the listbox
    log_listbox.yview(tk.END)  # scroll to the latest message

def on_closing():
    disconnect_from_server()
    root.destroy()

# GUI Setup
root = tk.Tk()  # Initialize the main Tkinter window.
root.title("Client")  # Set the title of the GUI window.

# Server Connection
tk.Label(root, text="Server IP:").pack()  # Add a label for the server IP input field.
ip_entry = tk.Entry(root)  # add an input field for the server IP.
ip_entry.pack()

tk.Label(root, text="Port:").pack()  # Add a label for the server port input field.
port_entry = tk.Entry(root)  # add an input field for the server port.
port_entry.pack()

tk.Label(root, text="Username:").pack()  # Add a label for the username input field.
username_entry = tk.Entry(root)  # Add an input field for the username.
username_entry.pack()

connect_button = tk.Button(root, text="Connect", command=connect_to_server)  # Add a button to connect to the server
connect_button.pack()

disconnect_button = tk.Button(root, text="Disconnect",
                              command=disconnect_from_server)  # Add a button to disconnect from the server
disconnect_button.pack()

# File Operations
tk.Label(root, text="Filename:").pack()  # Add a label for the filename input field
filename_entry = tk.Entry(root)  # add an input field for the filename.
filename_entry.pack()

upload_button = tk.Button(root, text="Upload File", command=upload_file_thread)  # Add a button to upload a file.
upload_button.pack()

list_button = tk.Button(root, text="Request File List",
                        command=request_file_list)  # add a button to request the file list
list_button.pack()

download_button = tk.Button(root, text="Download File",
                            command=download_file_thread)  # Add a button to download a file.
download_button.pack()

delete_button = tk.Button(root, text="Delete File", command=delete_file)  # add a button to delete a file.
delete_button.pack()

# Log Display
log_listbox = tk.Listbox(root, width=80, height=20)  # Add a listbox to display log messages
log_listbox.pack()

# Run GUI
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()