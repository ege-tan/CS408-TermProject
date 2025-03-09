import tkinter as tk
from tkinter import filedialog, messagebox
import socket
import threading
import os
import json
from turtledemo.penrose import start

# Server variables
server_socket = None #Main server socket for client communication
connected_clients = {} #Tracks connected clients by username
uploaded_files = {}  #Tracks uploaded files: {file_path: client_name}
file_storage_directory = "" #Directory where files are saved
server_running = False #indicates if the server is currently running
notification_port = 9001  # Port used for notifications
notification_server_socket = None  # Notification server socket for sending notifications to clients
notification_clients = {}  # Tracks notification clients: {username: notification_socket}

def start_notification_server():
    global notification_server_socket
    notification_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a socket for notifications
    notification_server_socket.bind(('0.0.0.0', notification_port))  #Bind the notification server to all IPs on a specific port
    notification_server_socket.listen(5)  #Listen for incoming notification client connections
    threading.Thread(target=accept_notification_clients, daemon=True).start()  #Run a thread to accept notification clients

def accept_notification_clients():
    while server_running:
        try:
            client_socket, address = notification_server_socket.accept()#Accept a new notification client
            client_name = client_socket.recv(1024).decode()# receive the username of the client
            notification_clients[client_name] = client_socket# Register the notification client
            log_message(f"Notification socket connected for {client_name}.")
        except Exception as e:
            log_message(f"Error in notification client connection: {e}")
            break

def start_server():
    global server_socket, file_storage_directory, server_running
    try:
        # Get the port number from the user
        port_input = port_entry.get().strip()
        if not port_input.isdigit():  # Ensure the port is a valid number
            messagebox.showerror("Error", "Port must be a valid number.")
            return

        port = int(port_input) #Convert the port to an integer
        #Prompt the user to select a directory for storing uploaded files
        file_storage_directory = filedialog.askdirectory(title="Select Directory for File Storage")
        if not file_storage_directory:
            messagebox.showerror("Error", "File storage directory must be selected.")
            return

        load_uploaded_files() #Load previously uploaded files from disk
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Create the main server socket
        server_socket.bind(("", port))#bind the server to the specified port
        server_socket.listen(5) #start listening for incoming connections

        server_running = True  #indicates that the server is running
        log_message(f"Server started on port {port}. Waiting for connections...")
        start_notification_server()# start the notification server
        threading.Thread(target=accept_clients, daemon=True).start() #Run a thread to accept client connections
        start_button.config(state="disabled")
        stop_button.config(state="normal")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start the server: {str(e)}")

def stop_server():
    global server_socket, server_running
    if server_running:
        server_running = False #Stop accepting new connections
        #Disconnect all clients
        for client_name, client_conn in list(connected_clients.items()):
            try:
                client_conn.sendall("DISCONNECTING".encode())#Notify the client about disconnection
                client_conn.close() #Close the client connection
            except Exception as e:
                log_message(f"Error disconnecting client {client_name}: {str(e)}")
        connected_clients.clear()  #Clear the list of connected clients

        try:
            server_socket.close() #Close the server socket
        except Exception as e:
            log_message(f"Error closing server socket: {str(e)}")

        save_uploaded_files()  # Save the list of uploaded files to disk
        log_message("Server stopped.")
        stop_button.config(state="disabled")
        start_button.config(state="normal")
        messagebox.showinfo("Info", "Server has been stopped.")
    else:
        log_message("Server is not running.")

def accept_clients():
    global server_socket
    while server_running:
        try:
            client_conn, client_addr = server_socket.accept()#accept a new client connection
            threading.Thread(target=handle_client, args=(client_conn, client_addr), daemon=True).start()#Handle the client in a separate thread
        except Exception as e:
            log_message(f"Error accepting clients: {str(e)}")
            break

def handle_client(client_conn, client_addr):
    global connected_clients, uploaded_files
    try:
        client_name = client_conn.recv(1024).decode()#Receive the client's username
        if client_name in connected_clients:
            client_conn.sendall("ERROR: Name already in use.".encode())#Reject duplicate usernames
            client_conn.close()
            return

        connected_clients[client_name] = client_conn #register the client
        log_message(f"Client '{client_name}' connected from {client_addr}.")
        client_conn.sendall("Successfully".encode())#Acknowledge successful connection

        while True:
            command = client_conn.recv(1024).decode()#Receive a command from the client
            if command == "UPLOAD":
                handle_upload(client_conn, client_name)
                #Handle file upload
            elif command == "LIST":
                handle_list_request(client_conn)
                #Handle file list request
            elif command == "DELETE":
                handle_delete(client_conn, client_name)
                #Handle file deletion
            elif command == "DOWNLOAD":
                handle_download(client_conn, client_name)
                #Handle file download
            elif command == "DISCONNECT":
                handle_disconnect(client_conn, client_name)
                #Handle client disconnection
                break
    except Exception as e:
        log_message(f"Error with client {client_addr}: {str(e)}")
        client_conn.close()

def handle_upload(client_conn, client_name):
    global uploaded_files
    try:
        #Receive the filename from the client
        filename = client_conn.recv(1024).decode()
        print(filename)
        #Create the full path where the file will be stored
        file_path = os.path.join(file_storage_directory, f"{client_name}_{filename}")
        print(file_path)

        #Check if the file already exists and notify the client accordingly
        if file_path in uploaded_files:
            client_conn.sendall("Override".encode())#Notify client that the file will be overridden
            log_message(f"Client '{client_name}' attempted to re-upload '{filename}'.")
        else:
            client_conn.sendall("New".encode()) #Notify client that a new file will be saved
        print("ok0")
        #open the file for writing in binary mode
        with open(file_path, "wb") as file:
            while True:
                data = client_conn.recv(4096)#Receive file data in chunks
                if data.endswith(b"EOFe"):#Check for end-of-file marker
                    file.write(data[:-4])#Write the last chunk excluding the EOF marker
                    break
                file.write(data)#Write the chunk to the file
        print("ok1")
        #Update the server's file tracking dictionary
        uploaded_files[file_path] = client_name
        threading.Thread(target=save_uploaded_files, daemon=True).start()#save uploaded files asynchronously
        print("ok2")
        client_conn.sendall("UPLOAD SUCCESS".encode())#Notify the client of successful upload
        log_message(f"Uploaded file '{filename}' by '{client_name}'.")
        print("ok3")
    except Exception as e:
        #Handle errors during upload and notify the client
        client_conn.sendall(f"UPLOAD ERROR: {str(e)}".encode())
        log_message(f"Error during file upload: {str(e)}")


def handle_list_request(client_conn):
    try:
        ##create a list of files and their owners
        file_list = [{"file": os.path.basename(file), "owner": owner} for file, owner in uploaded_files.items()]
        #Send the list as a JSON-encoded string
        client_conn.sendall(json.dumps(file_list).encode())
    except Exception as e:
        #Handle errors and notify the client
        client_conn.sendall(f"LIST ERROR: {str(e)}".encode())
        log_message(f"Error handling list request: {str(e)}")


def handle_delete(client_conn, client_name):
    try:
        #Receive the filename to delete
        filename = client_conn.recv(1024).decode()
        #Construct the full file path
        file_path = os.path.normpath(os.path.join(file_storage_directory, filename))

        #normalize uploaded files for consistent comparison
        normalized_uploaded_files = {os.path.normpath(key): value for key, value in uploaded_files.items()}

        # check if the file exists and if the client is authorized to delete it
        if file_path in normalized_uploaded_files and normalized_uploaded_files[file_path] == client_name:
            os.remove(file_path)#Delete the file
            del uploaded_files[file_path]#Remove the file from the server's tracking
            save_uploaded_files()#Save updated file list to disk
            client_conn.sendall("DELETE SUCCESS".encode())#Notify client that deletion is successfull
            log_message(f"File '{filename}' deleted by '{client_name}'.")
        else:
            client_conn.sendall("DELETE ERROR: File not found or unauthorized.".encode())#notify client of failure
    except Exception as e:
        #Handle errors and notify the client
        client_conn.sendall(f"DELETE ERROR: {str(e)}".encode())
        log_message(f"Error handling delete: {str(e)}")


def handle_download(client_conn, client_name):
    try:
        #Receive the filename from the client
        filename = client_conn.recv(1024).decode()
        #Construct the full file path
        file_path = os.path.join(file_storage_directory, filename)
        #Check if the file exists
        if not os.path.exists(file_path):
            client_conn.sendall("DOWNLOAD ERROR: File not found.".encode())
            return

        #Notify the file owner if they are connected
        file_owner = uploaded_files.get(file_path, None)
        if file_owner and file_owner in notification_clients:
            owner_notification_socket = notification_clients[file_owner]
            try:
                #send a notification to the file owner
                owner_notification_socket.sendall(f"NOTIFICATION: Your file '{filename}' was downloaded by '{client_name}'.".encode())
                log_message(f"Notification sent to '{file_owner}' about file '{filename}'.")
            except Exception as e:
                log_message(f"Failed to send notification to '{file_owner}': {str(e)}")

        #notify the client that the file is ready to be downloaded
        client_conn.sendall("FILENAME RECEIVED".encode())
        print("okk")
        #send the file content in chunks
        with open(file_path, "rb") as file:
            while chunk := file.read(4096):
                client_conn.sendall(chunk)
        client_conn.sendall(b"EOFe")#send EOF marker to indicate the end of the file

        log_message(f"File '{filename}' sent to client '{client_name}'.")
    except Exception as e:
        #handle errors during download and notify the client
        client_conn.sendall(f"DOWNLOAD ERROR: {str(e)}".encode())
        log_message(f"Error during file download: {str(e)}")


def handle_disconnect(client_conn, client_name):
    try:
        del connected_clients[client_name] #emove the client from the server's tracking
        client_conn.close() #close the client connection
        log_message(f"Client '{client_name}' disconnected.")
    except Exception as e:
        #Log any errors during disconnection
        log_message(f"Error handling disconnect: {str(e)}")


def save_uploaded_files():
    try:
        #Normalize file paths for consistent storage
        normalized_uploaded_files = {os.path.normpath(key): value for key, value in uploaded_files.items()}
        with open("uploaded_files.json", "w") as file:
            json.dump(normalized_uploaded_files, file, indent=4)#write the file list to a JSON file
        log_message("Uploaded files list saved.")
    except Exception as e:
        #Log any errors during the save operation
        log_message(f"Error saving uploaded files: {str(e)}")


def load_uploaded_files():
    global uploaded_files
    try:
        if os.path.exists("uploaded_files.json"):#check if the file exists
            with open("uploaded_files.json", "r") as file:
                uploaded_files = json.load(file)#load the file list from the JSON file
            log_message("Uploaded files loaded.")
        else:
            #If the file doesn't exist, create an empty file
            uploaded_files = {}
            with open("uploaded_files.json", "w") as file:
                json.dump(uploaded_files, file, indent=4)
            log_message("No existing uploaded files. Created a new file.")
    except Exception as e:
        #Log any errors during the load operation
        log_message(f"Error loading uploaded files: {str(e)}")


def log_message(message):
    log_listbox.insert(tk.END, message)#add the message to the listbox
    log_listbox.yview(tk.END)# scroll to the end of the listbox to show the latest message


#GUI Setup
root = tk.Tk()
root.title("Server")

#Port entry for specifying the server's port
tk.Label(root, text="Port:").pack()
port_entry = tk.Entry(root)
port_entry.pack()

#buttons for starting and stopping the server
start_button = tk.Button(root, text="Start Server", command=start_server)
start_button.pack()

stop_button = tk.Button(root, text="Stop Server", command=stop_server)
stop_button.pack()

#Listbox for displaying server logs
log_listbox = tk.Listbox(root, width=80, height=20)
log_listbox.pack()

#Window closing event handling
def on_closing():
    stop_server()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()