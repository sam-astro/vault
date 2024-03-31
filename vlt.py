# Version used for auto-updater
__version__="1.8.2"

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
import string
import base64
from datetime import datetime
import humanize
import csv

buffer_size = 65536 # 64kb

init()

BLOCK_SIZE = 16
salt = b'\x8a\xfe\x1f\xa7aY}\xa3It=\xc3\xccT\xc8\x94\xc11%w]A\xb7\x87G\xd8\xba\x9e\xf8\xec&\xf0'

PASSWORD_ALPHABET = string.ascii_lowercase + string.digits 
PASSWORD_LENGTH = 16

vaultPassword = ""
vaultData = []
configData = []

currentVault = 0
vaultName = ""



ORIGINALCOMMANDS = ['encrypt', 'decrypt', 'exit', 'quit', 'list', 'ls', 'new', 'create', 'append', 'remove', 'passrefresh', 'passcreate', 'printeverything', 'newvault', 'edit', 'clear', 'cls', 'help', 'dbencrypt', 'importcsv']
commands = ORIGINALCOMMANDS
RE_SPACE = re.compile('.*\s+$', re.M)

startScreenLogo = """
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝   
"""

print("Vault version v" + __version__)


# Class to auto-complete the user's input
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
        line = readline.get_line_buffer()
        # show all commands
        if not line:
            return [c + ' ' for c in commands][state]
        cmd = line.strip()
        if cmd in commands:
            impl = getattr(self, 'complete_%s' % cmd)
            args = line.split()
            if args:
                return (impl(args) + [None])[state]
            return [cmd + ' '][state]
        results = [c + ' ' for c in commands if c.startswith(cmd)] + [None]
        return results[state]

# Function to AES encrypt and compress data with a password
def encrypt(data, password):
    key = PBKDF2(password, salt, dkLen=32) # Your key that you can encrypt with
    cipher = AES.new(key, AES.MODE_CFB) # CFB mode
    ciphered_data = cipher.encrypt(data) # Only need to encrypt the data, no padding required for this mode
    
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
    global commands
    commands = []
    for cc in ORIGINALCOMMANDS:
        for h in vaultData['files']:
            commands.append(cc+" "+h['title'])
    for h in vaultData['files']:
        commands.append(h['title'])

def ListToString(l):
    strout = ""
    for ob in l:
        strout += ob
        if l.index(ob) < len(l)-1:
            strout += "\n"

    return strout


###########################################################
# This is the interactive text editor for encrypted files #
###########################################################
# Credit: https://github.com/maksimKorzh/code

import curses
import sys

editedContent = ""
contentToEdit = ""

class Editor:
    def __init__(self):
        self.screen = curses.initscr()
        self.screen.keypad(True)
        self.screen.nodelay(1)
        self.ROWS, self.COLS = self.screen.getmaxyx()
        self.ROWS -= 1
        curses.raw()
        curses.noecho()
        # self.lexers = {"py": PythonLexer, "c": CLexer}

    def reset(self):
        self.curx = 0
        self.cury = 0
        self.offx = 0
        self.offy = 0
        self.buff = []
        self.total_lines = 0
        self.filename = "Untitled"
        self.modified = 0
        self.search_results = []
        self.search_index = 0

    def insert_char(self, c):
        self.buff[self.cury].insert(self.curx, c)
        self.curx += 1
        self.modified += 1

    def delete_char(self):
        if self.curx:
            self.curx -= 1
            del self.buff[self.cury][self.curx]
        elif self.curx == 0 and self.cury:
            oldline = self.buff[self.cury][self.curx :]
            del self.buff[self.cury]
            self.cury -= 1
            self.curx = len(self.buff[self.cury])
            self.buff[self.cury] += oldline
            self.total_lines -= 1
        self.modified += 1

    def insert_line(self):
        oldline = self.buff[self.cury][self.curx :]
        self.buff[self.cury] = self.buff[self.cury][: self.curx]
        self.cury += 1
        self.curx = 0
        self.buff.insert(self.cury, [] + oldline)
        self.total_lines += 1
        self.modified += 1

    def delete_line(self):
        if len(self.buff) == 1:
            return
        try:
            del self.buff[self.cury]
            self.curx = 0
            self.total_lines -= 1
        except:
            pass
        self.modified += 1
        if self.cury >= self.total_lines:
            self.cury = self.total_lines - 1

    def move_cursor(self, key):
        row = self.buff[self.cury] if self.cury < self.total_lines else None
        if key == curses.KEY_LEFT:
            if self.curx != 0:
                self.curx -= 1
            elif self.cury > 0:
                self.cury -= 1
                self.curx = len(self.buff[self.cury])
        elif key == curses.KEY_RIGHT:
            if row is not None and self.curx < len(row):
                self.curx += 1
            elif (
                row is not None
                and self.curx == len(row)
                and self.cury != self.total_lines - 1
            ):
                self.cury += 1
                self.curx = 0
        elif key == curses.KEY_UP:
            if self.cury != 0:
                self.cury -= 1
            else:
                self.curx = 0
        elif key == curses.KEY_DOWN:
            if self.cury < self.total_lines - 1:
                self.cury += 1
            else:
                self.curx = len(self.buff[self.cury])
        row = self.buff[self.cury] if self.cury < self.total_lines else None
        rowlen = len(row) if row is not None else 0
        if self.curx > rowlen:
            self.curx = rowlen

    def skip_word(self, key):
        if key == 545:
            self.move_cursor(curses.KEY_LEFT)
            try:
                if self.buff[self.cury][self.curx] != ord(" "):
                    while self.buff[self.cury][self.curx] != ord(" "):
                        if self.curx == 0:
                            break
                        self.move_cursor(curses.KEY_LEFT)
                elif self.buff[self.cury][self.curx] == ord(" "):
                    while self.buff[self.cury][self.curx] == ord(" "):
                        if self.curx == 0:
                            break
                        self.move_cursor(curses.KEY_LEFT)
            except:
                pass
        if key == 560:
            self.move_cursor(curses.KEY_RIGHT)
            try:
                if self.buff[self.cury][self.curx] != ord(" "):
                    while self.buff[self.cury][self.curx] != ord(" "):
                        self.move_cursor(curses.KEY_RIGHT)
                elif self.buff[self.cury][self.curx] == ord(" "):
                    while self.buff[self.cury][self.curx] == ord(" "):
                        self.move_cursor(curses.KEY_RIGHT)
            except:
                pass

    def scroll_end(self):
        while self.cury < self.total_lines - 1:
            self.scroll_page(curses.KEY_NPAGE)

    def scroll_home(self):
        while self.cury:
            self.scroll_page(curses.KEY_PPAGE)

    def scroll_page(self, key):
        count = 0
        while count != self.ROWS:
            if key == curses.KEY_NPAGE:
                self.move_cursor(curses.KEY_DOWN)
                if self.offy < self.total_lines - self.ROWS:
                    self.offy += 1
            elif key == curses.KEY_PPAGE:
                self.move_cursor(curses.KEY_UP)
                if self.offy:
                    self.offy -= 1
            count += 1

    def scroll_buffer(self):
        if self.cury < self.offy:
            self.offy = self.cury
        if self.cury >= self.offy + self.ROWS:
            self.offy = self.cury - self.ROWS + 1
        if self.curx < self.offx:
            self.offx = self.curx
        if self.curx >= self.offx + self.COLS:
            self.offx = self.curx - self.COLS + 1

    def print_status_bar(self):
        status = "\x1b[7m"
        status += self.filename + " - " + str(self.total_lines) + " lines"
        status += " modified" if self.modified else " saved"
        status += "     Ctrl+S | Save     Ctrl+Q | Quit         "
        status += "\x1b[0m"
        status += Fore.WHITE + Back.RED + "Not saved"+Style.RESET_ALL if self.modified else Fore.BLACK + Back.GREEN + "Saved"+Style.RESET_ALL
        status += "\x1b[7m"
        pos = "Row " + str(self.cury + 1) + ", Col " + str(self.curx + 1)
        while len(status)-22 < self.COLS - len(pos) + 3:
            status += " "
        status += pos + " "
        status += "\x1b[m"
        status += (
            "\x1b["
            + str(self.cury - self.offy + 1)
            + ";"
            + str(self.curx - self.offx + 1)
            + "H"
        )
        status += "\x1b[?25h"
        return status

    def print_buffer(self):
        print_buffer = "\x1b[?25l"
        print_buffer += "\x1b[H"
        for row in range(self.ROWS):
            buffrow = row + self.offy
            if buffrow < self.total_lines:
                rowlen = len(self.buff[buffrow]) - self.offx
                if rowlen < 0:
                    rowlen = 0
                if rowlen > self.COLS:
                    rowlen = self.COLS
                print_buffer += "".join(
                    [
                        chr(c)
                        for c in self.buff[buffrow][self.offx : self.offx + rowlen]
                    ]
                )
            print_buffer += "\x1b[K"
            print_buffer += "\r\n"
        return print_buffer

    def update_screen(self):
        self.scroll_buffer()
        print_buffer = self.print_buffer()
        status_bar = self.print_status_bar()
        sys.stdout.write(print_buffer + status_bar)
        sys.stdout.flush()

    def resize_window(self):
        self.ROWS, self.COLS = self.screen.getmaxyx()
        self.ROWS -= 1
        self.screen.refresh()
        self.update_screen()

    def read_keyboard(self):
        def ctrl(c):
            return (c) & 0x1F

        c = -1
        while c == -1:
            c = self.screen.getch()
        if c == ctrl(ord("q")):
            return True
            # self.exit()
        elif c == 9:
            [self.insert_char(ord(" ")) for i in range(4)]
        elif c == 353:
            [self.delete_char() for i in range(4) if self.curx]
        # elif c == ctrl(ord("n")):
        #     self.new_file()
        elif c == ctrl(ord("s")):
            self.save_file()
        elif c == ctrl(ord("f")):
            self.search()
        elif c == ctrl(ord("g")):
            self.find_next()
        elif c == ctrl(ord("d")):
            self.delete_line()
        # elif c == ctrl(ord("t")):
        #     self.indent()
        elif c == curses.KEY_RESIZE:
            self.resize_window()
        elif c == curses.KEY_HOME:
            self.curx = 0
        elif c == curses.KEY_END:
            self.curx = len(self.buff[self.cury])
        elif c == curses.KEY_LEFT:
            self.move_cursor(c)
        elif c == curses.KEY_RIGHT:
            self.move_cursor(c)
        elif c == curses.KEY_UP:
            self.move_cursor(c)
        elif c == curses.KEY_DOWN:
            self.move_cursor(c)
        elif c == curses.KEY_BACKSPACE:
            self.delete_char()
        elif c == curses.KEY_NPAGE:
            self.scroll_page(c)
        elif c == curses.KEY_PPAGE:
            self.scroll_page(c)
        elif c == 530:
            self.scroll_end()
        elif c == 535:
            self.scroll_home()
        elif c == 560:
            self.skip_word(560)
        elif c == 545:
            self.skip_word(545)
        elif c == ord("\n"):
            self.insert_line()
        elif ctrl(c) != c:
            self.insert_char(c)

    def clear_prompt(self, line):
        command_line = "\x1b[" + str(self.ROWS + 1) + ";" + "0" + "H"
        command_line += "\x1b[7m" + line
        pos = "Row " + str(self.cury + 1) + ", Col " + str(self.curx + 1)
        while len(command_line) < self.COLS - len(pos) + 10:
            command_line += " "
        command_line += pos + " "
        command_line += "\x1b[" + str(self.ROWS + 1) + ";" + "9" + "H"
        sys.stdout.write(command_line)
        sys.stdout.flush()

    def command_prompt(self, line):
        self.clear_prompt(line)
        self.screen.refresh()
        word = ""
        c = -1
        pos = 0
        while c != 0x1B:
            c = -1
            while c == -1:
                c = self.screen.getch()
            if c == 10:
                break
            if c == curses.KEY_BACKSPACE:
                pos -= 1
                if pos < 0:
                    pos = 0
                    continue
                sys.stdout.write("\b")
                sys.stdout.write(" ")
                sys.stdout.write("\b")
                sys.stdout.flush()
                word = word[: len(word) - 1]
            if c != curses.KEY_BACKSPACE:
                pos += 1
                sys.stdout.write(chr(c))
                sys.stdout.flush()
                word += chr(c)
        self.update_screen()
        self.screen.refresh()
        return word

    def indent(self):
        indent = self.command_prompt("indent:")
        try:  # format: [rows] [cols] [+/-]
            start_row = self.cury
            end_row = self.cury + int(indent.split()[0])
            start_col = self.curx
            end_col = self.curx + int(indent.split()[1])
            dir = indent.split()[2]
            try:
                char = indent.split()[3]
            except:
                char = ""
            for row in range(start_row, end_row):
                for col in range(start_col, end_col):
                    if dir == "+":
                        self.buff[row].insert(col, ord(char if char != "" else " "))
                    if dir == "-":
                        del self.buff[row][self.curx]
            self.modified += 1
        except:
            pass

    def search(self):
        self.search_results = []
        self.search_index = 0
        word = self.command_prompt("search:")
        for row in range(len(self.buff)):
            buffrow = self.buff[row]
            for col in range(len(buffrow)):
                if "".join([chr(c) for c in buffrow[col : col + len(word)]]) == word:
                    self.search_results.append([row, col])
        if len(self.search_results):
            self.cury, self.curx = self.search_results[self.search_index]
            self.search_index += 1

    def find_next(self):
        if len(self.search_results):
            if self.search_index == len(self.search_results):
                self.search_index = 0
            try:
                self.cury, self.curx = self.search_results[self.search_index]
            except:
                pass
            self.search_index += 1

    def open_file(self, filecontent):
        global editedContent
        global editedTitle
        self.reset()
        print("filecontent: " + editedContent)
        content = editedContent.split("\n")
        for row in content:
            self.buff.append([ord(c) for c in row])
        self.buff.append([])
        self.filename = editedTitle
        self.highlight = False
        self.total_lines = len(self.buff)
        self.update_screen()

    def save_file(self):
        global editedContent
        # with open(self.filename, "w") as f:
        editedContent = ""
        for row in self.buff:
            editedContent += "".join([chr(c) for c in row])+"\n"
        # editedContent = content
        # f.write(content)
        self.modified = 0

    # def new_file(self):
    #     self.reset()
    #     self.buff.append([])
    #     self.total_lines = 1

    def exit(self):
        curses.endwin()
        # sys.exit(0)

    def start(self):
        self.update_screen()
        while True:
            if self.read_keyboard() == True:
                return
            self.update_screen()

def texteditor(stdscr):
    editor = Editor()
    editor.open_file(contentToEdit)
    editor.start()

def editableInput(strinput, title):
    global editedContent
    global editedTitle
    editedContent = strinput
    editedTitle = title
    curses.wrapper(texteditor)
    return editedContent


# import urllib
import urllib.request
import re
from subprocess import call
def compare_versions(vA, vB):
    """
Compares two version number strings
@param vA: first version string to compare
@param vB: second version string to compare
@return negative if vA < vB, zero if vA == vB, positive if vA > vB.
"""
    if vA == vB: return 0

    def num(s):
        if s.isdigit(): return int(s)
        return s

    splitVA = vA.split(".")
    splitVB = vB.split(".")

    vaNum = (num(splitVA[0])*100)+(num(splitVA[1])*10)+(num(splitVA[2]))
    vbNum = (num(splitVB[0])*100)+(num(splitVB[1])*10)+(num(splitVB[2]))

    if vaNum<vbNum: return -1
    if vaNum>vbNum: return 1


# Function to get the current version of this script from the server, and prompt
# to update if a newer one is available.
def update(dl_url, force_update=False):
    """
Attempts to download the update url in order to find if an update is needed.
If an update is needed, the current script is backed up and the update is
saved in its place.
"""

    # dl the first 256 bytes and parse it for version number
    try:
        http_stream = urllib.request.urlopen(dl_url)
        update_file = str(http_stream.read(256))
        http_stream.close()
    except (Exception) as e:
        print("Unable to retrieve version data: " + str(e))
        # print("Error %s: %s" % (errno, strerror))
        return

    match_regex = re.search(r'__version__ *= *"(\S+)"', update_file)
    if not match_regex:
        print("No version info could be found")
        return
    update_version = match_regex.group(1)

    if not update_version:
        print("Unable to parse version data")
        return

    if force_update:
        print("Forcing update, downloading version %s..." \
            % update_version)
    else:
        cmp_result = compare_versions(__version__, update_version)

        # Prompt user if they want to update if it is available
        if cmp_result < 0:
            print("Newer version v%s available, do you want to update?" % update_version)
            while True:
                ans = input("Y/n: ")
                if ans.upper() == "Y":
                    break
                elif ans.upper() == "N":
                    print("Skipping update...")
                    return

        if cmp_result < 0:
            print("Downloading version %s..." % update_version)
        elif cmp_result > 0:
            # print("Local version %s newer then available %s, not updating." \
            #     % (__version__, update_version))
            return
        else:
            print("You have the latest version of Vault.")
            return

    # dl, backup, and save the updated script
    app_path = os.path.realpath(sys.argv[0])

    if not os.access(app_path, os.W_OK):
        print("Cannot update -- unable to write to %s" % app_path)

    dl_path = app_path + ".new"
    backup_path = app_path + ".old"
    
    try:
        dl_file = open(dl_path, 'wb')
        http_stream = urllib.request.urlopen(dl_url)
        total_size = None
        bytes_so_far = 0
        chunk_size = 8192
        try:
            total_size = int(http_stream.info().getheader('Content-Length').strip())
        except:
            # The header is improper or missing Content-Length, just download
            dl_file.write(http_stream.read())

        while total_size:
            chunk = http_stream.read(chunk_size)
            dl_file.write(chunk)
            bytes_so_far += len(chunk)

            if not chunk:
                break

            percent = float(bytes_so_far) / total_size
            percent = round(percent*100, 2)
            sys.stdout.write("Downloaded %d of %d bytes (%0.2f%%)\r" %
                (bytes_so_far, total_size, percent))

            if bytes_so_far >= total_size:
                sys.stdout.write('\n')

        http_stream.close()
        dl_file.close()
    except (Exception) as e:
        print("Download failed: " + str(e))
        # print("Error %s: %s" % (errno, strerror))
        return

    try:
        os.rename(app_path, backup_path)
    except:
        print("Unable to rename %s to %s" \
            % (app_path, backup_path))
        return

    try:
        os.rename(dl_path, app_path)
    except:
        print("Unable to rename %s to %s" \
            % (dl_path, app_path))
        return

    try:
        import shutil
        shutil.copymode(backup_path, app_path)
    except:
        os.chmod(app_path, 755)

    print(Fore.GREEN + "New version installed as %s" % app_path)
    print(Fore.GREEN+"(previous version backed up to %s)" % (backup_path))

    # Restart script so newer update is the current process
    print(Fore.GREEN + "Restarting with newer update..." + Style.RESET_ALL)
    print()
    os.execl(sys.executable, *([sys.executable]+sys.argv))



# Make sure vault is correctly formatted and the newest version
def upgradeVault(jDat):
    outJ = json.loads('{"files":[],"version":""}')
    # print(json.dumps(jDat, sort_keys=True, indent=4))

    # 1.5.0 Update
    # This update I started storing the version in the vault file
    try:
        vv = jDat['version']
        outJ['version'] = vv
    except:
        jDat['version'] = "1.4.0"
        outJ['version'] = "1.4.0"

    print("vault file version " + jDat['version'])

    # 1.5.0 Update
    # This checks if the vault is older than the .Json update 1.5.0,
    # where I converted each entry to a more organized json object
    if compare_versions(jDat['version'], "1.5.0") < 0:
        for i, fle in enumerate(jDat['files']):
            # If normal entry
            if fle.split("\n")[0].__contains__("-=password=") == False:
                outJ["files"].append({"title":fle.split("\n")[0],"type":"normal","content":ListToString(fle.split("\n")[1:]),"encryption":"normal"})
            # If password entry
            else:
                outJ["files"].append({"title":fle.split("\n")[0].split("-=password=")[0],"type":"password","content":ListToString(fle.split("\n")[1:]),"encryption":"normal"})
        outJ['version'] = "1.5.0" # increase the version, because the file is now updated to at least this version

    # Otherwise, the vault is compatable so just load it normally
    else:
        outJ = jDat

    # By this point the version should be the same so just make sure
    outJ['version'] = __version__

    return outJ

# Make sure vault configuration file is correctly formatted and the newest version
def upgradeConfig(jDat):
    outJ = json.loads('{"vaults":[],"version":"","updatedTime":""}')

    # 1.6.0 Update
    # This update I started storing the version in the config file
    try:
        vv = jDat['version'] # If the version is accessed then there is no problem
        outJ['version'] = vv
    except:
        jDat['version'] = "0.0.0" # If the version can't be accessed, it could be any version before 1.6.0 so just default to 0
        outJ['version'] = "0.0.0"
        # If a version cannot be determined, then at least figure out if it is the old vault config format:
        try:
            v2 = jDat['vault'] # If this test succeeds, then it is the oldest version of the config
            jDat['version'] = "0.0.0"
        except:
            jDat['version'] = "1.0.0" # Otherwise, it is at least version 1 and doesn't need old processing done first
            outJ['version'] = "1.0.0"

    # 0.0.0 Update
    # This checks if the config is older than the update 0.0.0,
    # where I started allowing multiple vault paths to be in
    # the config file
    if compare_versions(jDat['version'], "0.0.0") <= 0:
        outJ['vaults'].append(jDat['vault'])
        jDat['version'] = "1.0.0"

    # Otherwise, the config is compatable so just load it normally
    else:
        outJ = jDat


    # 1.6.1 Update
    # This update was when I added date checking to the config and updater
    if compare_versions(jDat['version'], "1.6.1") < 0:
        try:
            oT = jDat['updatedTime']
            outJ['updatedTime'] = oT
        except:
            outJ['updatedTime'] = datetime.now().strftime("%d/%m/%y %H:%M:%S")
            jDat['version'] = "1.6.1"




    # By this point the version should be the same so just make sure
    outJ['version'] = __version__

    return outJ


def ListVaultDirectory():
    print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
    print("    "+Fore.BLACK+Back.WHITE+"Title:                   "+Back.RESET+"  " + Back.WHITE+"Type:     "+Back.RESET+"  " + Back.WHITE+"Encryption Lvl:" + Style.RESET_ALL)
    print("    -------------------------  ----------  ---------------")
    for fle in vaultData['files']:
        icon = "🔑" if fle['type'] == "password" else "📝"
        encryptionLvl = fle['encryption'] if fle['encryption'] == "double" else "-"
        encryptionLvlIcon = "🔐x2" if fle['encryption'] == "double" else "  "
        print(("{:3s}{:25s}  {:10s}  {:7s}{:3s}").format(icon, fle['title'], fle['type'], encryptionLvl, encryptionLvlIcon))
    print()

try:
    # Make sure config folder exists
    if os.path.isdir("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault") == False:
        os.mkdir("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault")
    # Make sure config file exists, if it doesn't then enter setup
    if exists("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf") == False:
        # Prompt user for vault directory
        validDirectory = ""
        while validDirectory == "":
            dir = input("\nEnter directory to store existing or new vaults\n(ex. \"/home/vault/\")\n >  ")
            if os.path.isdir(dir):
                if not (dir.endswith("/") and dir.endswith("\\")):
                    dir += "/"
                validDirectory = os.path.abspath(dir)
            else:
                print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                mke = input("\nThis directory does not exist. Create it?\nY/n >  ")
                if mke.upper() == "Y":
                    try:
                        os.mkdirs(dir)
                        if os.path.isdir(dir):
                            validDirectory = os.path.abspath(dir)
                    except OSError as error:
                        print("Directory '%s' can not be created: %s" % (dir, error))
        
        # Check if any vaults are present in the directory
        vaultFiles = []
        for filename in os.listdir(validDirectory):
            if filename.endswith(".vlt"):
                vaultFiles.append(os.path.join(validDirectory, filename))
        
        # If there are no existing vaults, create one
        if len(vaultFiles) == 0:
            # Prompt user for vault name
            nam = input("\nEnter name of new vault\n(ex. \"MyVault\")\n >  ")
            if len(nam)>0:
                if nam.endswith(".vlt"):
                    validDirectory += "./"+nam
                else:
                    validDirectory += "./"+nam+".vlt"
            else:
                validDirectory += "./MyVault.vlt"
            vaultFiles.append(os.path.abspath(validDirectory))
            # Create vault file
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
                
            dataIn = {'files':[],'version':__version__}
            fw = open(os.path.abspath(validDirectory), 'wb')
            fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
            fw.close()
            vaultPassword = password
            vaultName = nam
            vaultData = upgradeVault(dataIn)
        
        data = {'vaults' : vaultFiles, 'version' : __version__, 'updatedTime' : datetime.now().strftime("%d/%m/%y %H:%M:%S")}
        with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
            json.dump(data, outfile)
            
    with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf") as json_file:
        # Load config file data
        configData = upgradeConfig(json.load(json_file))

        # Check if the user needs update by comparing last updated time to now
        currentTime = datetime.now()
        difference = currentTime-datetime.strptime(configData['updatedTime'], "%d/%m/%y %H:%M:%S")
        if difference.seconds//3600 >= 5: # If it has been at leat 5 hours since the last update, then try updating again.
            print("Last checked for updates " + Fore.YELLOW+humanize.naturaltime(datetime.now() - difference) + Style.RESET_ALL)
            update("https://raw.githubusercontent.com/sam-astro/vault/main/vlt.py")
            configData['updatedTime'] = datetime.now().strftime("%d/%m/%y %H:%M:%S") # Update last time to now

        # Save updated config data
        with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
            json.dump(configData, outfile)
        
        # List all known vaults, and ask which one the user wants to load
        print("\nVaults:")
        for i, vaultDir in enumerate(configData['vaults']):
            if exists(configData['vaults'][i]):
                print(Fore.BLACK + Back.GREEN +"\t" + str(i) + "." + Back.RESET+Fore.GREEN+" " + os.path.basename(vaultDir)+"  "+Fore.CYAN+ os.path.dirname(vaultDir)+"/"+ Style.RESET_ALL)
            else:
                print(Fore.YELLOW + Back.RED +"\t" + str(i) + ". " + os.path.basename(vaultDir) + Style.RESET_ALL + "  not found at  "+Fore.CYAN+ os.path.dirname(vaultDir)+"/"+ Style.RESET_ALL)
        
        # If the number of vaults is more than 1, ask user which one they want to use this time
        if len(configData['vaults'])>1:
            valAccepted = False
            while valAccepted == False:
                g = input("\nWhich vault do you want to load?\n(0-"+str(len(configData['vaults'])-1)+") >  ")
                try:
                    ii = int(g)
                    if ii < len(configData['vaults']) and ii >= 0:
                        currentVault = ii
                        valAccepted = True
                    else:
                        print(Fore.RED + "Invalid value, please enter valid index" + Style.RESET_ALL)
                except:
                    print(Fore.RED + "Invalid value, please enter valid index" + Style.RESET_ALL)
        else:
            print("\nYou only have 1 vault file, automatically loading it: " + Fore.GREEN+os.path.basename(configData['vaults'][0])+Fore.RESET)
            
        
        # If the vault file specified in the config is invalid, ask to create new one
        if exists(configData['vaults'][currentVault]) == False:
            print("Vault file at '%s' could not be found. Create new one?" % configData['vaults'][currentVault])
            cnoA = input("Y/n >  ")
            if cnoA.upper() == "Y" or cnoA.upper() == "YES":
                passwordAccepted = False
                while passwordAccepted == False:
                    vaultPassword = getpass(Fore.BLACK + Back.WHITE + "Create vault password: " + Style.RESET_ALL)
                    confirmedPassword = getpass(Fore.BLACK + Back.WHITE + "Confirm password: " + Style.RESET_ALL)
                    if vaultPassword == "":
                        print(Fore.RED + "Password is invalid")
                    elif vaultPassword == confirmedPassword:
                        passwordAccepted = True
                    elif vaultPassword != confirmedPassword:
                        print(Fore.RED + "Passwords don't match")
                    
                dataIn = {'files':[],'version':__version__}
                fw = open(os.path.abspath(configData['vaults'][currentVault]), 'wb')
                fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), vaultPassword))
                fw.close()
                vaultName = configData['vaults'][currentVault]
                vaultData = upgradeVault(dataIn)
                
            elif cnoA.upper() == "N" or cnoA.upper() == "NO":
                print(Fore.YELLOW + "Would you like to remove this vault from your configuration then?" + Style.RESET_ALL)
                cnoA = input("Y/n >  ")

                if cnoA.upper() == "Y" or cnoA.upper() == "YES":
                    configData['vaults'].remove(configData['vaults'][currentVault])

                    # Save updated config data
                    with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
                        json.dump(configData, outfile)
        
                exit()
                
            else:
                exit()
        # Otherwise ask for password and decrypt it
        else:
            while True:
                vaultPassword = getpass(Fore.BLACK + Back.WHITE + "Enter password: " + Style.RESET_ALL)
                fr = open(configData['vaults'][currentVault], 'rb')
                data = decrypt(fr.read(), vaultPassword)
                fr.close()
                try:
                    vaultData = upgradeVault(json.loads(data))
                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()

                    break;
                except Exception as e:
                    print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                    continue
            vaultName = configData['vaults'][currentVault]
            if len(vaultData['files']) > 1:
                refreshCommands()
                
    
    # If there are no arguments specified, enter interactive mode
    if len(sys.argv) <= 1:
        # Print logo and list files in vault
        print(Fore.LIGHTYELLOW_EX + startScreenLogo + Style.RESET_ALL)
        ListVaultDirectory()
            
        while True:
            refreshCommands()
            
            comp = Completer()
            # we want to treat '\' as part of a word, so override the delimiters
            readline.set_completer_delims('\t\n;')
            readline.parse_and_bind("tab: complete")
            readline.set_completer(comp.complete)
            # Ask user for input and wait for command
            inputArgs = input("Vault ("+Fore.GREEN+vaultName+Style.RESET_ALL+") >  ").split()
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

            # If there is no input then just prompt again
            if len(inputArgs) <= 0:
                continue
            
            print("")
            
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
                if exists(inputArgs[1]):
                    fr = open(inputArgs[1], 'rb')
                    data = fr.read()
                    fr.close()
                    password = getpass(Fore.BLACK + Back.WHITE + "Enter password: " + Style.RESET_ALL)
                        
                    decryptedData = decrypt(data, password)
                    
                    print("\n       " + decryptedData.replace("\n", "\n       ") + "\n")
                    
                    if inputArgs[len(inputArgs) - 2].upper() == "-O":
                        fw = open(inputArgs[len(inputArgs) - 1].replace(".ef", ""), 'wb')
                        fw.write(decryptedData)
                        fw.close()
                    
            # Command to refresh a password entry `passrefresh <name>`
            elif inputArgs[0].upper() == "PASSREFRESH":
                if len(inputArgs) == 2:
                    found = False
                    for n, f in enumerate(vaultData['files']):
                        if inputArgs[1] == vaultData['files'][n]['title']:
                            if vaultData['files'][n]['type'] == "password":
                                # If the encryption is normal, edit normally. Otherwise do double decryption
                                if f['encryption'] == "normal":
                                    lines = vaultData['files'][n]['content'].split("\n")
                                    lines[1] = lines[3]
                                    lines[3] = ''.join(secrets.choice(PASSWORD_ALPHABET) for i in range(PASSWORD_LENGTH)) 
                                    strval = ListToString(lines)
                                    vaultData['files'][n]['content'] = strval.strip()
                                    print("\n       " + vaultData['files'][n]['content'].replace("\n", "\n       ") + "\n")
                                # Double encrypted, decrypt
                                elif f['encryption'] == "double":
                                    print(Fore.YELLOW+"This entry is double encrypted, please input a second password for this file"+Style.RESET_ALL)
                                    b64 = base64.urlsafe_b64decode(f['content'])
                                    encdat = b64
                                    while True:
                                        passw = getpass(Fore.BLACK + Back.WHITE + "Enter this entry's individual password: " + Style.RESET_ALL)
                                        try:
                                            # Decode and decrypt
                                            decdat = decrypt(encdat, passw)
                                            decodedDecryptedString = decdat.decode("utf-8")

                                            # Generate new password
                                            lines = decodedDecryptedString.split("\n")
                                            lines[1] = lines[3]
                                            lines[3] = ''.join(secrets.choice(PASSWORD_ALPHABET) for i in range(PASSWORD_LENGTH)) 
                                            strval = ListToString(lines)
                                            decodedDecryptedString = strval.strip()
                                            print("\n       " + decodedDecryptedString.replace("\n", "\n       ") + "\n")

                                            # Save new password and encrypt into vault
                                            vaultData['files'][n]['content'] = str(base64.urlsafe_b64encode(encrypt(bytes(decodedDecryptedString, "utf-8"), passw)), "utf-8")
                                            fw = open(configData['vaults'][currentVault], 'wb')
                                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                            fw.close()

                                            break
                                        except Exception as e:
                                            print(Fore.RED + "Incorrect Password" + Fore.RESET)
                                            continue
                            else:
                                print("This is not a valid Password file.\nCreate one with command:\npasscreate [entry's name]")
                                break
                            found = True
                    
                    if found == False:
                        print("Invalid Password file.\nCreate one with command:\npasscreate [entry's name]")
                            
                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                else:
                    print("Password Refresh format:\npassrefresh <entry's name>")

            # Command to create a new password entry `passcreate <name>`
            elif inputArgs[0].upper() == "PASSCREATE":
                if len(inputArgs) == 2:
                    vaultData['files'].append({"title":inputArgs[1],"type":"password","content":"old-password:\n\ncurrent-password:\n","encryption":"normal"})
                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                else:
                    print("Password Create format:\npasscreate <entry's name>")
                        
            # Command to safely exit the vault `exit/quit`
            elif inputArgs[0].upper() == "EXIT" or inputArgs[0].upper() == "QUIT":
                os.system('cls' if os.name == 'nt' else 'clear')
                exit()
                
            # Command to list all entries `list`
            elif inputArgs[0].upper() == "LIST" or  inputArgs[0].upper() == "LS":
                ListVaultDirectory()
                
            # Command to clear terminal `clear/cls`
            elif inputArgs[0].upper() == "CLEAR" or  inputArgs[0].upper() == "CLS":
                os.system('cls' if os.name == 'nt' else 'clear')
                    
            # Command to create a new entry `new/create <name>`
            elif inputArgs[0].upper() == "NEW" or inputArgs[0].upper() == "CREATE":
                if len(inputArgs) >= 2:
                    # Make sure file with this name does not already exist
                    doesExist = False
                    for n, f in enumerate(vaultData['files']):
                        if inputArgs[1].lower() == vaultData['files'][n]['title'].lower():
                            doesExist = True
                    
                    # If the file doesn't already exist, continue
                    if doesExist == False:
                        vaultData['files'].append({"title":inputArgs[1],"type":"normal","content":"","encryption":"normal"})
                        # Open terminal text editor to start editing entry
                        vaultData['files'][-1]['content'] = editableInput(vaultData['files'][-1]['content'].replace("\t", "    "), inputArgs[1])
                        # Save new entry to vault
                        fw = open(configData['vaults'][currentVault], 'wb')
                        fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                        fw.close()
                        
                        refreshCommands()
                        
                        ListVaultDirectory()
                    else:
                        print("An entry with this name already exists, please \nchoose another name or edit/delete the other entry.")
                else:
                    print("New entry format:\nnew <entry's name>")
                    
            # Command to append string to an entry `append <name> <content>`
            elif inputArgs[0].upper() == "APPEND":
                if len(inputArgs) >= 3:
                    for n, f in enumerate(vaultData['files']):
                        if inputArgs[1] == vaultData['files'][n]['title'].replace("\t", "    ").strip():
                            vaultData['files'][n]['content'] += "\n" + inputArgs[2].replace("\t", "    ")
                            print(vaultData['files'][n]['content'])
                            break
                            
                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                else:
                    print("Append format:\nappend <entry's name> \"<content (in quotes)>\"")
                    
            
            # Command to remove an entry `remove <name>`
            elif inputArgs[0].upper() == "REMOVE":
                if len(inputArgs) >= 2:
                    for f in vaultData['files']:
                        if inputArgs[1] == f['title'].strip():
                            
                            mke = input(Fore.YELLOW+"Are you sure? This will permanently remove this entry."+Style.RESET_ALL+"\nY/n >  ")
                            
                            if mke.upper() == "Y":
                                vaultData['files'].remove(f)

                                fw = open(configData['vaults'][currentVault], 'wb')
                                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                fw.close()

                                refreshCommands()

                                ListVaultDirectory()
                            else:
                                print("Cancelled remove operation")
                                
                            break
                else:
                    print("Remove entry format:\nremove <entry's name>")

            # Command to edit an entry `edit <name>`
            elif inputArgs[0].upper() == "EDIT":
                if len(inputArgs) >= 2:
                    for i, f in enumerate(vaultData['files']):
                        if inputArgs[1] == f['title']:
                            # If the encryption is normal, edit normally. Otherwise do double decryption
                            if f['encryption'] == "normal":
                                # Open terminal text editor to start editing entry
                                vaultData['files'][i]['content'] = editableInput(f['content'].replace("\t", "    "), inputArgs[1]).replace("\t", "    ")
                                # Save newly edited data to vault
                                fw = open(configData['vaults'][currentVault], 'wb')
                                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                fw.close()
                            # Double encrypted, decrypt
                            elif f['encryption'] == "double":
                                print(Fore.YELLOW+"This entry is double encrypted, please input the second password for this file"+Style.RESET_ALL)
                                b64 = base64.urlsafe_b64decode(f['content'])
                                encdat = b64
                                while True:
                                    passw = getpass(Fore.BLACK + Back.WHITE + "Enter this entry's individual password: " + Style.RESET_ALL)
                                    try:
                                        decdat = decrypt(encdat, passw)
                                        decodedDecryptedString = decdat.decode("utf-8")

                                        # Open terminal text editor to start editing entry
                                        decodedDecryptedString = editableInput(decodedDecryptedString.replace("\t", "    "), inputArgs[1]).replace("\t", "    ")
                                        vaultData['files'][i]['content'] = str(base64.urlsafe_b64encode(encrypt(bytes(decodedDecryptedString, "utf-8"), passw)), "utf-8")
                                        # Save newly edited data to vault
                                        fw = open(configData['vaults'][currentVault], 'wb')
                                        fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                        fw.close()

                                        break
                                    except Exception as e:
                                        print(Fore.RED + "Incorrect Password" + Fore.RESET)
                                        continue
                                
                            
                            break
                else:
                    print("Edit entry format:\nedit <entry's name>")

            # Command to double encrypt an entry `dbencrypt <name>`
            elif inputArgs[0].upper() == "DBENCRYPT":
                if len(inputArgs) >= 2:
                    for i, f in enumerate(vaultData['files']):
                        if inputArgs[1] == f['title']:
                            # Make sure they actually want to encrypt it
                            mke = input(Fore.YELLOW+"Are you sure you want to double encrypt? This file will require a password (that is different from your master password) to fully decrypt."+Style.RESET_ALL+"\nY/n >  ")
                            if mke.upper() == "Y":
                                # Only double encrypt if this entry is normal
                                if f['encryption'] == "normal":
                                    # Prompt user for new password
                                    passwordAccepted = False
                                    while passwordAccepted == False:
                                        password = getpass(Fore.BLACK + Back.WHITE + "Create entry password: " + Style.RESET_ALL)
                                        confirmedPassword = getpass(Fore.BLACK + Back.WHITE + "Confirm entry password: " + Style.RESET_ALL)
                                        if password == "":
                                            print(Fore.RED + "Password is invalid")
                                        elif password == confirmedPassword:
                                            passwordAccepted = True
                                        elif password != confirmedPassword:
                                            print(Fore.RED + "Passwords don't match")
                                    # Encrypt the content of this file with new double password
                                    vaultData['files'][i]['content'] = str(base64.urlsafe_b64encode(encrypt(bytes(f['content'], "utf-8"), password)), "utf-8")
                                    vaultData['files'][i]['encryption'] = "double"
                                    # Save newly edited data to vault
                                    fw = open(configData['vaults'][currentVault], 'wb')
                                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                    fw.close()
                                    ListVaultDirectory()
                                    print(Fore.YELLOW+"Write this password down somewhere (preferably not inside this vault). This file will not be recoverable if you forget it."+Style.RESET_ALL)
                                # If the entry has already been double encrypted, skip
                                elif f['encryption'] == "double":
                                    print(Fore.YELLOW+"This entry is already double encrypted, you can't encrypt again."+Fore.RESET)
                                
                            break
                else:
                    print("dbencrypt format:\ndbencrypt <entry's name>")
            
            # Command to print all contained data `printeverything`
            elif inputArgs[0].upper() == "PRINTEVERYTHING":
                mke = input(Fore.YELLOW+"Are you sure? This will print the contents of ALL entries to the terminal."+Style.RESET_ALL+"\nY/n >  ")
                if mke.upper() == "Y":
                    while True:
                        passw = getpass(Fore.BLACK + Back.WHITE + "Enter password to continue: " + Style.RESET_ALL)
                        fr = open(configData['vaults'][currentVault], 'rb')
                        dat = decrypt(fr.read(), passw)
                        fr.close()
                        try:
                            jsdat = json.loads(dat)
                            print(json.dumps(jsdat, indent=2).replace("\\n", "\n"))
                            break
                        except:
                            print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                            continue

            # Command to import passwords from .CSV file -- exported from browser usually
            elif inputArgs[0].upper() == "IMPORTCSV":
                with open(inputArgs[1], mode ='r') as file:
                    csvFile = csv.reader(file)
                    #for lines in csvFile:
                    #    print(lines)
                    mke = input(Fore.YELLOW+"Do you wish to create a new vault with these entries? Selecting 'No' will add them to this existing vault."+Style.RESET_ALL+"\nY/n >  ")

                    if mke.upper() == "Y" or mke.upper() == "YES":
                        
                        # Prompt user for vault name
                        newValDir = ""
                        nam = ""
                        while len(nam) <= 0:
                            nam = input("Enter name of new vault\n(ex. \"MyVault\")\n >  ")
                            if len(nam)>0:
                                if nam.endswith(".vlt"):
                                    newValDir += "./"+nam
                                else:
                                    newValDir += "./"+nam+".vlt"
                            
                        # Prompt user for vault directory
                        validDirectory = ""
                        while validDirectory == "":
                            dir = input("\nEnter directory to store new vault\n(ex. \"/home/vault/\")\n >  ")
                            if os.path.isdir(dir):
                                if not (dir.endswith("/") and dir.endswith("\\")):
                                    dir += "/"
                                validDirectory = dir
                            elif len(dir)>0:
                                print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                                mke = input("\nThis directory does not exist. Create it?\nY/n >  ")
                                if mke.upper() == "Y":
                                    try:
                                        os.mkdirs(dir)
                                        if os.path.isdir(dir):
                                            validDirectory = dir
                                    except OSError as error:
                                        print("Directory '%s' can not be created: %s" % (dir, error))
                            else:
                                print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                                        
                        configData['vaults'].append(os.path.abspath(validDirectory+newValDir))
                        # Save path of vault to config file
                        data = {'vaults' : configData['vaults']}
                        with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
                            json.dump(data, outfile)
                            
                        # Prompt user for new password
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
                        
                        entriesArray = []
                        for lines in csvFile:
                            if lines[0] == "name":
                                continue

                            entryTitle = lines[0]
                            if entryTitle.startswith("https://"):
                                entryTitle = entryTitle.replace("https://", "")
                            if entryTitle.startswith("http://"):
                                entryTitle = entryTitle.replace("http://", "")
                            if entryTitle.startswith("www."):
                                entryTitle = entryTitle.replace("www.", "")

                            entriesArray.append({"title":entryTitle,"type":"normal","content":"user: "+lines[2]+"\npass: "+lines[3],"encryption":"normal"})
                            #vaultData['files'].append({"title":inputArgs[1],"type":"password","content":"old-password:\n\ncurrent-password:\n","encryption":"normal"})

                        dataIn = {'files':entriesArray,'version':__version__}
                        fw = open(validDirectory+newValDir, 'wb')
                        fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
                        fw.close()

                        sw = input("Switch to new vault? " + Fore.GREEN + nam + Fore.RESET + "\nY/n >  ")
                        if sw.upper() == "Y":
                            vaultName = configData['vaults'][-1]
                            currentVault = len(configData['vaults'])-1
                            vaultData = upgradeVault(dataIn)
                        
                        print()

            
            # Command to create a new, empty vault `newvault`
            elif inputArgs[0].upper() == "NEWVAULT":
                
                # Prompt user for vault name
                newValDir = ""
                nam = ""
                while len(nam) <= 0:
                    nam = input("Enter name of new vault\n(ex. \"MyVault\")\n >  ")
                    if len(nam)>0:
                        if nam.endswith(".vlt"):
                            newValDir += "./"+nam
                        else:
                            newValDir += "./"+nam+".vlt"
                    
                # Prompt user for vault directory
                validDirectory = ""
                while validDirectory == "":
                    dir = input("\nEnter directory to store new vault\n(ex. \"/home/vault/\")\n >  ")
                    if os.path.isdir(dir):
                        if not (dir.endswith("/") and dir.endswith("\\")):
                            dir += "/"
                        validDirectory = dir
                    elif len(dir)>0:
                        print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                        mke = input("\nThis directory does not exist. Create it?\nY/n >  ")
                        if mke.upper() == "Y":
                            try:
                                os.mkdirs(dir)
                                if os.path.isdir(dir):
                                    validDirectory = dir
                            except OSError as error:
                                print("Directory '%s' can not be created: %s" % (dir, error))
                    else:
                        print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                                
                configData['vaults'].append(os.path.abspath(validDirectory+newValDir))
                # Save path of vault to config file
                data = {'vaults' : configData['vaults']}
                with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
                    json.dump(data, outfile)
                    
                # Prompt user for new password
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
                    
                dataIn = {'files':[],'version':__version__}
                fw = open(validDirectory+newValDir, 'wb')
                fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
                fw.close()

                sw = input("Switch to new vault? " + Fore.GREEN + nam + Fore.RESET + "\nY/n >  ")
                if sw.upper() == "Y":
                    vaultName = configData['vaults'][-1]
                    currentVault = len(configData['vaults'])-1
                    vaultData = upgradeVault(dataIn)
                
                print()
                
            # Command to print the help menu `help`
            elif inputArgs[0].upper() == "HELP":
                helpText = """Help Menu:

    encrypt [-rm] <file>
        Encrypts a file, (optional: [-rm] (DELETES original file))

    decrypt <file> [-o <output file>]
        Decrypt a .EF file (optional: [-o <output file>] specify the
        output destination for decrypted data)

    passcreate <name>
        Create password entry in vault, which has the ability to be
        randomly generated
        
    passrefresh <password entry>
        Randomly generates a new password inside the password entry,
        and keeps the old one just in case you need it to change to
        the new one.

    exit/quit
        Safely exit and clear terminal of any viewed data. Ctrl+C
        also does this.

    help
        Show this help menu

    list/ls
        List the name of all the entries present in this vault, like
        a directory

    clear/cls
        Clear the terminal window of all text, this should be used
        after you access sensitive information and passwords so
        nobody can see previous printouts

    new/create <name>
        Command to create a new entry with <name>

    append <name> "<content (in quotes)>"
        Command to append a line to an existing entry

    remove <name>
        PERMANENTLY delete an entry. This process is irreversible

    printeverything
        Print the entire vault json data to the terminal. !! (This
        process shows all of the unencrypted entries, and is only
        recommended for debugging)
        
    newvault
        Start the process of creating a new, separate vault

    edit <name>
        Edit contents of an existing entry, will open in-terminal text editor.
            Text editor commands:
            * Ctrl+S   Save the entry
            * Ctrl+F   Search for word
            * Ctrl+G   Find next word (after search)
            * Ctrl+D   Delete current line
            * Ctrl+Q   Quit entry editor and return to vault

    dbencrypt <name>
        Encrypt the contents of an entry a second time with a different
        password that is separate from your master pass

    importcsv <path>
        Imports a .CSV file containing comma-separated website, user, password
        (These are usually the exported files from browser password managers)
"""
                print(helpText)
                
            # If not a command, check if the user is trying to view a file
            else:
                occurrences = 0
                for f in vaultData['files']:
                    if inputArgs[0] == f['title']:
                        # If the file is found more than once, then delete the other version
                        if occurrences >= 1:
                            vaultData['files'].remove(f)
                            fw = open(configData['vaults'][currentVault], 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                        else:
                            # If the encryption is normal, print. Otherwise do double decryption
                            if f['encryption'] == "normal":
                                print("      " + f['content'].replace("\n", "\n      ") + "\n")
                            # Double encrypted
                            elif f['encryption'] == "double":
                                print(Fore.YELLOW+"This entry is double encrypted, please input the second password for this file"+Style.RESET_ALL)
                                b64 = base64.urlsafe_b64decode(f['content'])
                                encdat = b64
                                while True:
                                    passw = getpass(Fore.BLACK + Back.WHITE + "Enter this entry's individual password: " + Style.RESET_ALL)
                                    try:
                                        decdat = decrypt(encdat, passw)
                                        print("      " + decdat.decode("utf-8").replace("\n", "\n      ") + "\n")
                                        break
                                    except Exception as e:
                                        print(Fore.RED + "Incorrect Password" + Fore.RESET)
                                        continue
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
                fw = open(configData['vaults'][currentVault], 'wb')
                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                fw.close()
                
                ListVaultDirectory()
                    
                if sys.argv[2].upper() != "-K":
                    os.remove(sys.argv[len(sys.argv) - 1])
                     
        if sys.argv[1].upper() == "COMBINE":
            if len(sys.argv) >= 2:
                if exists(sys.argv[len(sys.argv)-1]):
                    while True:
                        otherPass = getpass(Fore.BLACK + Back.WHITE + "Enter other vault's password: " + Style.RESET_ALL)
                        fr = open(sys.argv[len(sys.argv) - 1], 'rb')
                        data = decrypt(fr.read(), otherPass)
                        fr.close()
                        try:
                            otherVaultData = upgradeVault(json.loads(data))
                            break
                        except:
                            print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                            continue

                    for f in otherVaultData['files']:
                        occurred = False
                        for h in vaultData['files']:
                            if f['title'] == h['title']:
                                occurred = True
                        if occurred == False:
                            vaultData['files'].append(f)

                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()

                    ListVaultDirectory()

                    if sys.argv[2].upper() == "-RM":
                        os.remove(sys.argv[len(sys.argv) - 1])

                   
        if sys.argv[1].upper() == "ADDVAULT":
            if len(sys.argv) >= 2:
                if exists(sys.argv[2]):
                    configData['vaults'].append(os.path.abspath(sys.argv[2]))
                    # Save updated config data
                    with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
                        json.dump(configData, outfile)

                   
        if sys.argv[1].upper() == "UPDATE":
            update("https://raw.githubusercontent.com/sam-astro/vault/main/vlt.py", True)
            configData['updatedTime'] = datetime.now().strftime("%d/%m/%y %H:%M:%S") # Update last time to now
     

# Clear screen so no data is left in the terminal on exit
except KeyboardInterrupt:
    print("\nExiting...")
    os.system('cls' if os.name == 'nt' else 'clear')
    
os.system('cls' if os.name == 'nt' else 'clear')
