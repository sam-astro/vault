import sys
import os
from base64 import b64encode, b64decode
import hashlib
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from os.path import exists
from getpass import getpass
import colorama
from colorama import init
from colorama import Fore, Back, Style
import zlib
import json
import pwd
import re
import readline
import secrets

buffer_size = 65536 # 64kb

init()

BLOCK_SIZE = 16
salt = b'\x8a\xfe\x1f\xa7aY}\xa3It=\xc3\xccT\xc8\x94\xc11%w]A\xb7\x87G\xd8\xba\x9e\xf8\xec&\xf0'

vaultPassword = ""
vaultData = []
configData = []



ORIGINALCOMMANDS = ['encrypt', 'decrypt', 'exit', 'quit', 'list', 'new', 'create', 'append', 'remove', 'passrefresh', 'passcreate']
COMMANDS = ORIGINALCOMMANDS
RE_SPACE = re.compile('.*\s+$', re.M)

startScreenLogo = "\n██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗\n██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝\n╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   \n ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   \n  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝   \n                                        "

class Completer(object):

    def _listdir(self, root):
        "List directory 'root' appending the path separator to subdirs."
        res = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.isdir(path):
                name += os.sep
            res.append(name)
        return res

    def _complete_path(self, path=None):
        "Perform completion of filesystem path."
        if not path:
            return self._listdir('.')
        dirname, rest = os.path.split(path)
        tmp = dirname if dirname else '.'
        res = [os.path.join(dirname, p)
                for p in self._listdir(tmp) if p.startswith(rest)]
        # more than one match, or single match which does not exist (typo)
        if len(res) > 1 or not os.path.exists(path):
            return res
        # resolved to a single directory, so return list of files below it
        if os.path.isdir(path):
            return [os.path.join(path, p) for p in self._listdir(path)]
        # exact file match terminates this completion
        return [path + ' ']

    def complete_extra(self, args):
        "Completions for the 'extra' command."
        if not args:
            return self._complete_path('.')
        # treat the last arg as a path and complete it
        return self._complete_path(args[-1])

    def complete(self, text, state):
        "Generic readline completion entry point."
        buffer = readline.get_line_buffer()
        line = readline.get_line_buffer().split()
        # show all commands
        if not line:
            return [c + ' ' for c in COMMANDS][state]
        # account for last argument ending in a space
        if RE_SPACE.match(buffer):
            line.append('')
        # resolve command to the implementation function
        cmd = line[0].strip()
        if cmd in COMMANDS:
            impl = getattr(self, 'complete_%s' % cmd)
            args = line[1:]
            if args:
                return (impl(args) + [None])[state]
            return [cmd + ' '][state]
        results = [c + ' ' for c in COMMANDS if c.startswith(cmd)] + [None]
        return results[state]

# Function to AES encrypt and compress data with a password
def encrypt(data, password):
    key = PBKDF2(password, salt, dkLen=32) # Your key that you can encrypt with
    cipher = AES.new(key, AES.MODE_CFB) # CFB mode
    ciphered_data = cipher.encrypt(data) # Only need to encrypt the data, no padding required for this mode
    
    # # Create the Python dictionary with the required data
    # output_json = {
    #     'ciphertext': b64encode(ciphered_data).decode('utf-8'),
    #     'iv': b64encode(cipher.iv).decode('utf-8')
    # }
    
    # Compress ciphered data with zlib
    compressed_data = zlib.compress(cipher.iv + ciphered_data)
    
    return compressed_data
 
# Function to decompress and AES decrypt ciphered data with a password
def decrypt(enc, password):
    # Decompress ciphered data with zlib
    decompressed_data = zlib.decompress(enc)
    # Now to get all the data for decryption:
    
    key = PBKDF2(password, salt, dkLen=32) # Your key that you can decrypt with
    iv = decompressed_data[0:16] # read iv from beginning of decompressed data bytes
    ciphered_data = decompressed_data[16:len(decompressed_data)] # separate encrypted data from iv
    
    cipher = AES.new(key, AES.MODE_CFB, iv)
    original_data = cipher.decrypt(ciphered_data) # Decrypt ciphered data
    return original_data
    
def refreshCommands():
    COMMANDS = ORIGINALCOMMANDS

def ListToString(l):
    strout = ""
    for ob in l:
        strout += ob
        if l.index(ob) < len(l)-1:
            strout += "\n"

    return strout

try:
    if os.path.isdir("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault") == False:
        os.mkdir("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault")
    if exists("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf") == False:
        validDirectory = ""
        while validDirectory == "":
            dir = input("First time setup, enter directory of new or existing vault file\n >  ")
            if os.path.isdir(dir):
                validDirectory = dir
            else:
                print(Fore.RED + "Not a valid directory")
        
        data = {'vault' : validDirectory}
        with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
            json.dump(data, outfile)
            
    with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf") as json_file:
        configData = json.load(json_file)
        if exists(configData['vault'] + "/vault.vlt") == False:
            passwordAccepted = False
            while passwordAccepted == False:
                password = getpass(Fore.BLACK + Back.WHITE + "Create vault password: " + Style.RESET_ALL)
                confirmedPassword = getpass(Fore.BLACK + Back.WHITE + "Confirm password: " + Style.RESET_ALL)
                if password == "":
                    print(Fore.RED + "Password is invalid")
                elif password == confirmedPassword:
                    passwordAccepted = True
                elif password != confirmedPassword:
                    print(Fore.RED + "Passwords don't match")
                    
            dataIn = {}
            dataIn['files'] = []
            fw = open(configData['vault'] + "/vault.vlt", 'wb')
            fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
            fw.close()
            vaultPassword = password
        else:
            while True:
                password = getpass(Fore.BLACK + Back.WHITE + "Enter password: " + Style.RESET_ALL)
                fr = open(configData['vault'] + "/vault.vlt", 'rb')
                data = decrypt(fr.read(), password)
                fr.close()
                try:
                    vaultData = json.loads(data)
                    break;
                except:
                    print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                    continue
            vaultPassword = password
            if len(vaultData) > 1:
                for f in vaultData['files']:
                    COMMANDS.append(f.split("\n")[0])
    
    # If there are no arguments specified, enter interactive mode
    if len(sys.argv) <= 1:
        # Print logo and list files in vault
        print(Fore.YELLOW + startScreenLogo + Style.RESET_ALL)
        print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
        for f in vaultData['files']:
            print("   -  " + f.split("\n")[0])
            
        while True:
            refreshCommands()
            for h in vaultData['files']:
                COMMANDS.append(h.split("\n")[0])
            
            comp = Completer()
            # we want to treat '\' as part of a word, so override the delimiters
            readline.set_completer_delims(' \t\n;')
            readline.parse_and_bind("tab: complete")
            readline.set_completer(comp.complete)
            # Ask user for input and wait for command
            inputArgs = input("\nVault >  ").split()
            combining = False
            newInputArray = []
            for u, i in enumerate(inputArgs):
                if '"' in inputArgs[u] and combining == False:
                    newInputArray.append(inputArgs[u].replace("\"", ""))
                    combining = True
                elif '"' in inputArgs[u] and combining == True:
                    newInputArray[len(newInputArray)-1] += " " + inputArgs[u].replace("\"", "")
                    combining = False
                elif combining == True:
                    newInputArray[len(newInputArray)-1] += " " + inputArgs[u].replace("\"", "")
                else:
                    newInputArray.append(inputArgs[u].replace("\"", ""))
                
            inputArgs = newInputArray
            
            # Process whatever command the user enters

            # Command to encrypt a file `encrypt <file> (optional: -rm (Deletes original file))`
            if inputArgs[0].upper() == "E" or inputArgs[0].upper() == "ENCRYPT":
                if exists(inputArgs[len(inputArgs) - 1]):
                    # Read byte data from file
                    fr = open(inputArgs[len(inputArgs) - 1], 'rb')
                    data = fr.read()
                    fr.close()
                    # Create and confirm password from user
                    passwordAccepted = False
                    while passwordAccepted == False:
                        password = getpass(Fore.BLACK + Back.WHITE + "Enter new password: " + Style.RESET_ALL)
                        confirmedPassword = getpass(Fore.BLACK + Back.WHITE + "Confirm password: " + Style.RESET_ALL)
                        if password == "":
                            print(Fore.RED + "Password is invalid" + Style.RESET_ALL)
                        elif password == confirmedPassword:
                            passwordAccepted = True
                        elif password != confirmedPassword:
                            print(Fore.RED + "Passwords don't match" + Style.RESET_ALL)
                        
                    # Encrypt data and save it to new file with same name but ending with ".ef"
                    encryptedData = encrypt(data, password)
                    fw = open(inputArgs[len(inputArgs) - 1] + ".ef", 'wb')
                    fw.write(data)
                    fw.close()

                    print(Fore.CYAN + "Encrypted file to " + inputArgs[len(inputArgs) - 1] + ".ef" + Style.RESET_ALL)
                    
                    # Remove the original file if the user specified it with "-rm"
                    if inputArgs[1].upper() == "-RM":
                        os.remove(inputArgs[len(inputArgs) - 1])
            
            # Command to decrypt a file that was encrypted by Vault `decrypt <file> (optional: -o <outputname>)`
            elif inputArgs[0].upper() == "D" or inputArgs[0].upper() == "DECRYPT":
                if exists(inputArgs[len(inputArgs) - 1]):
                    fr = open(inputArgs[len(inputArgs) - 1], 'rb')
                    data = fr.read()
                    fr.close()
                    password = getpass(Fore.BLACK + Back.WHITE + "Enter password: " + Style.RESET_ALL)
                        
                    decryptedData = decrypt(data, password)
                    
                    print("\n       " + decryptedData.replace("\n", "\n       ") + "\n")
                    
                    if inputArgs[1].upper() == "-O":
                        fw = open(inputArgs[len(inputArgs) - 1].replace(".ef", ""), 'wb')
                        fw.write(decryptedData)
                        fw.close()
                    
            # Command to refresh a password entry `passrefresh <name>`
            elif inputArgs[0].upper() == "PASSREFRESH":
                if len(inputArgs) == 2:
                    if len(inputArgs[1].split("-"))>=2:
                        if inputArgs[1].split("-")[1] == "=password=":
                            found = False
                            for n, f in enumerate(vaultData['files']):
                                if inputArgs[1] == vaultData['files'][n].split("\n")[0].strip():
                                    lines = vaultData['files'][n].split("\n")
                                    lines[2] = lines[4]
                                    lines[4] = secrets.token_urlsafe(16)
                                    strval = ListToString(lines)
                                    vaultData['files'][n] = strval.strip()
                                    print("\n       " + vaultData['files'][n].replace("\n", "\n       ") + "\n")
                                    found = True
                                    break
                            
                            if found == False:
                                print("Invalid =password= file.\nCreate one with command:\npasscreate [entry's name]")
                                    
                            fw = open(configData['vault'] + "/vault.vlt", 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                        else:
                            print("Invalid =password= file.\nCreate one with command:\npasscreate [entry's name]")
                    else:
                        print("Invalid =password= file.\nCreate one with command:\npasscreate [entry's name]")
                else:
                    print("Password Refresh format:\npassrefresh [entry's name]")

            # Command to create a new password entry `passcreate <name>`
            elif inputArgs[0].upper() == "PASSCREATE":
                if len(inputArgs) == 2:
                    vaultData['files'].append(inputArgs[1] + "-=password=\nold-password:\n\ncurrent-password:\n")
                    fw = open(configData['vault'] + "/vault.vlt", 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                else:
                    print("Password Create format:\npasscreate [entry's name]")
                        
            # Command to safely exit the vault `exit/quit`
            elif inputArgs[0].upper() == "EXIT" or inputArgs[0].upper() == "QUIT":
                os.system('cls' if os.name == 'nt' else 'clear')
                exit()
                
            # Command to list all entries `list`
            elif inputArgs[0].upper() == "LIST":
                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                for f in vaultData['files']:
                    print("   -  " + f.split("\n")[0])
                    
            # Command to create a new entry `new/create <name> "<content (in quotes)>"`
            elif inputArgs[0].upper() == "NEW" or inputArgs[0].upper() == "CREATE":
                if len(inputArgs) >= 3:
                    vaultData['files'].append(inputArgs[1] + "\n" + inputArgs[2].replace("\\n", chr(10)))
                    fw = open(configData['vault'] + "/vault.vlt", 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                    
                    refreshCommands()
                    for h in vaultData['files']:
                        COMMANDS.append(h.split("\n")[0])
                    
                    print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                    for f in vaultData['files']:
                        print("   -  " + f.split("\n")[0])
                else:
                    print("New entry format:\nnew [entry's name] \"[content (in quotes)]\"")
                    
            # Command to append text to an entry `append <name> <content>`
            elif inputArgs[0].upper() == "APPEND":
                if len(inputArgs) >= 3:
                    for n, f in enumerate(vaultData['files']):
                        if inputArgs[1] == vaultData['files'][n].split("\n")[0].strip():
                            vaultData['files'][n] += "\n" + inputArgs[2]
                            print(vaultData['files'][n])
                            break
                            
                    fw = open(configData['vault'] + "/vault.vlt", 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                else:
                    print("Append format:\nappend [entry's name] [content]")
            
            # Command to remove an entry `remove <name>`
            elif inputArgs[0].upper() == "REMOVE":
                if len(inputArgs) >= 2:
                    for f in vaultData['files']:
                        if inputArgs[1] == f.split("\n")[0].strip():
                            vaultData['files'].remove(f)
                            
                            fw = open(configData['vault'] + "/vault.vlt", 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                    
                            refreshCommands()
                            for h in vaultData['files']:
                                COMMANDS.append(h.split("\n")[0])
                            
                            print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                            for f in vaultData['files']:
                                print("   -  " + f.split("\n")[0])
                                
                            break
                else:
                    print("Remove entry format:\nremove [entry's name]")
                
            # If not a command, check if the user is trying to view a file
            else:
                occurrences = 0
                for f in vaultData['files']:
                    if inputArgs[0] == f.split("\n")[0].strip():
                        # If the file is found more than once, then delete the other version
                        if occurrences >= 1:
                            vaultData['files'].remove(f)
                            fw = open(configData['vault'] + "/vault.vlt", 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                        else:
                            print("\n       " + f.replace("\n", "\n       ") + "\n")
                        occurrences += 1
                # No file was found either, print unknown command
                if occurrences == 0:
                    print("Unknown command: " + inputArgs[0] + "\n")
    
    # If there are arguments specified execute that argument and exit
    elif len(sys.argv) > 1:
        if sys.argv[1].upper() == "ADD":
            if exists(sys.argv[len(sys.argv)-1]):
                fr = open(sys.argv[len(sys.argv) - 1], 'r')
                data = fr.read()
                fr.close()
                vaultData['files'].append(sys.argv[len(sys.argv)-1].replace(" ", "_") + "\n" + data)
                fw = open(configData['vault'] + "/vault.vlt", 'wb')
                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                fw.close()
                
                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                for f in vaultData['files']:
                    print("     " + f.split("\n")[0])
                    
                if sys.argv[2].upper() != "-K":
                    os.remove(sys.argv[len(sys.argv) - 1])
                    
        if sys.argv[1].upper() == "COMBINE" or sys.argv[1].upper() == "-C":
            if exists(sys.argv[len(sys.argv)-1]):
                while True:
                    otherPass = getpass(Fore.BLACK + Back.WHITE + "Enter other vault's password: " + Style.RESET_ALL)
                    fr = open(sys.argv[len(sys.argv) - 1], 'rb')
                    data = decrypt(fr.read(), otherPass)
                    fr.close()
                    try:
                        otherVaultData = json.loads(data)
                        break
                    except:
                        print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                        continue
                        
                for f in otherVaultData['files']:
                    occurred = False
                    for h in vaultData['files']:
                        if f == h:
                            occurred = True
                    if occurred == False:
                        vaultData['files'].append(f)
                    
                fw = open(configData['vault'] + "/vault.vlt", 'wb')
                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                fw.close()
                
                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                for f in vaultData['files']:
                    print("     " + f.split("\n")[0])
                    
                if sys.argv[2].upper() != "-K":
                    os.remove(sys.argv[len(sys.argv) - 1])


# Clear screen so no data is left in the terminal on exit
except KeyboardInterrupt:
    print("\nExiting...")
    os.system('cls' if os.name == 'nt' else 'clear')
    
os.system('cls' if os.name == 'nt' else 'clear')