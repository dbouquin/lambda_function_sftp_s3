import paramiko
import os

#%%
# Initialize the SSH client
client = paramiko.SSHClient()

#%%
# Add the SSH public key
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

#%%
# connect to the SFTP server
ssh_key_filepath = os.path.expanduser('~/.ssh/id_rsa_roi')
my_ssh_key = paramiko.RSAKey(filename=ssh_key_filepath)


#%%
# Connect to the SFTP server
client.connect(hostname='outbound.roisolutions.net', port=22, username='npca_dbouquin9335', pkey=my_ssh_key)

# Initialize the SFTP client
sftp = client.open_sftp()

# List directories in the current directory on the server
directories = sftp.listdir()
for directory in directories:
    print(directory)

# Close the connection
sftp.close()
client.close()