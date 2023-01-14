# Version used for auto-updater
__version__="1.4.3"

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

currentVault = 0
vaultName = ""



ORIGINALCOMMANDS = ['encrypt', 'decrypt', 'exit', 'quit', 'list', 'new', 'create', 'append', 'remove', 'passrefresh', 'passcreate', 'printeverything', 'newvault']
COMMANDS = ORIGINALCOMMANDS
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


###########################################################
# This is the interactive text editor for encrypted files #
###########################################################
# Credit: https://github.com/maksimKorzh/code

import curses
import sys
# from pygments.lexers import PythonLexer, CLexer
# from pygments.formatters import TerminalFormatter
# from pygments.token import (
#     Keyword,
#     Name,
#     Comment,
#     String,
#     Error,
#     Number,
#     Operator,
#     Generic,
#     Token,
#     Whitespace,
# )
# from pygments import highlight

editedContent = ""
contentToEdit = ""

# COLOR_SCHEME = {
#     Token: ("gray", "gray"),
#     Comment: ("magenta", "brightmagenta"),
#     Comment.Preproc: ("magenta", "brightmagenta"),
#     Keyword: ("blue", "**"),
#     Keyword.Type: ("green", "*brightgreen*"),
#     Operator.Word: ("**", "**"),
#     Name.Builtin: ("cyan", "brightblue"),
#     Name.Function: ("blue", "brightblue"),
#     Name.Class: ("_green_", "brightblue"),
#     Name.Decorator: ("magenta", "brightmagenta"),
#     Name.Variable: ("blue", "brightblue"),
#     String: ("yellow", "brightyellow"),
#     Number: ("blue", "brightyellow"),
# }


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
        status += "     Ctrl+S to Save     Ctrl+Q to Quit without saving         "
        status += "\x1b[0m"
        status += Fore.WHITE + Back.RED + "Not saved"+Style.RESET_ALL if self.modified else Fore.WHITE + Back.GREEN + "Saved"+Style.RESET_ALL
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
        self.reset()
        print("filecontent: " + editedContent)
        content = editedContent.split("\n")
        for row in content:
            self.buff.append([ord(c) for c in row])
        self.buff.append([])
        self.filename = content[0]
        self.highlight = False
        self.total_lines = len(self.buff)
        self.update_screen()

    def save_file(self):
        global editedContent
        # with open(self.filename, "w") as f:
        editedContent = ""
        for row in self.buff:
            editedContent += "".join([chr(c) for c in row]) + "\n"
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

def editableInput(strinput):
    global editedContent
    editedContent = strinput
    curses.wrapper(texteditor)
    return editedContent




# Function to get the current version of this script from the server, and prompt
# to update if a newer one is available.
def update(dl_url, force_update=False):
    """
Attempts to download the update url in order to find if an update is needed.
If an update is needed, the current script is backed up and the update is
saved in its place.
"""
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

# Check for update
update("https://raw.githubusercontent.com/sam-astro/vault/main/vlt.py")

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
                validDirectory = dir
            else:
                print(Fore.RED + "Not a valid directory"+Style.RESET_ALL)
                mke = input("\nThis directory does not exist. Create it?\nY/n >  ")
                if mke.upper() == "Y":
                    try:
                        os.mkdirs(dir)
                        if os.path.isdir(dir):
                            validDirectory = dir
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
                
            dataIn = {}
            dataIn['files'] = []
            fw = open(os.path.abspath(validDirectory), 'wb')
            fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
            fw.close()
            vaultPassword = password
            vaultName = nam
        
        data = {'vaults' : vaultFiles}
        with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf", 'w') as outfile:
            json.dump(data, outfile)
            
    with open("/home/"+pwd.getpwuid(os.getuid()).pw_name+"/vault/va.conf") as json_file:
        # Load config file data
        configData = json.load(json_file)
        
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
                g = input("Which vault do you want to load?\n(0-"+str(len(configData['vaults'])-1)+") >  ")
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
            print("You only have 1 vault file, automatically loading it: " + Fore.GREEN+os.path.basename(configData['vaults'][0])+Fore.RESET)
            
        
        # If the vault file specified in the config is invalid, ask to create new one
        if exists(configData['vaults'][currentVault]) == False:
            print("Vault file at '%s' could not be found. Create new one?" % configData['vaults'][currentVault])
            cnoA = input("Y/n >  ")
            if cnoA.upper() == "Y":
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
                fw = open(os.path.abspath(configData['vaults'][currentVault]), 'wb')
                fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
                fw.close()
                vaultPassword = password
                vaultName = configData['vaults'][currentVault]
                
            else:
                exit()
        # Otherwise ask for password and decrypt it
        else:
            while True:
                password = getpass(Fore.BLACK + Back.WHITE + "Enter password: " + Style.RESET_ALL)
                fr = open(configData['vaults'][currentVault], 'rb')
                data = decrypt(fr.read(), password)
                fr.close()
                try:
                    vaultData = json.loads(data)
                    break;
                except:
                    print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                    continue
            vaultPassword = password
            vaultName = configData['vaults'][currentVault]
            if len(vaultData) > 1:
                for f in vaultData['files']:
                    COMMANDS.append(f.split("\n")[0])
    
    # If there are no arguments specified, enter interactive mode
    if len(sys.argv) <= 1:
        # Print logo and list files in vault
        print(Fore.YELLOW + startScreenLogo + Style.RESET_ALL)
        print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
        for fle in vaultData['files']:
            print("   -  " + fle.split("\n")[0])
            
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
                                    
                            fw = open(configData['vaults'][currentVault], 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                        else:
                            print("Invalid =password= file.\nCreate one with command:\npasscreate [entry's name]")
                    else:
                        print("Invalid =password= file.\nCreate one with command:\npasscreate [entry's name]")
                else:
                    print("Password Refresh format:\npassrefresh <entry's name>")

            # Command to create a new password entry `passcreate <name>`
            elif inputArgs[0].upper() == "PASSCREATE":
                if len(inputArgs) == 2:
                    vaultData['files'].append(inputArgs[1] + "-=password=\nold-password:\n\ncurrent-password:\n")
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
                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                for f in vaultData['files']:
                    print("   -  " + f.split("\n")[0])
                
            # Command to clear terminal `clear/cls`
            elif inputArgs[0].upper() == "CLEAR" or  inputArgs[0].upper() == "CLS":
                os.system('cls' if os.name == 'nt' else 'clear')
                    
            # Command to create a new entry `new/create <name>`
            elif inputArgs[0].upper() == "NEW" or inputArgs[0].upper() == "CREATE":
                if len(inputArgs) >= 2:
                    vaultData['files'].append(inputArgs[1]+"\n\n")
                    # Create new entry data
                    # vaultData['files'][len(vaultData['files'])-1]=editableInput("This is an editable input\nmore\n")
                    # Open terminal text editor to start editing entry
                    vaultData['files'][-1] = editableInput(vaultData['files'][-1].replace("\t", "    "))
                    # Save new entry to vault
                    fw = open(configData['vaults'][currentVault], 'wb')
                    fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                    fw.close()
                    
                    refreshCommands()
                    for h in vaultData['files']:
                        COMMANDS.append(h.split("\n")[0])
                    
                    print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                    for f in vaultData['files']:
                        print("   -  " + f.split("\n")[0])
                else:
                    print("New entry format:\nnew <entry's name>")
                    
            # Command to append string to an entry `append <name> <content>`
            elif inputArgs[0].upper() == "APPEND":
                if len(inputArgs) >= 3:
                    for n, f in enumerate(vaultData['files']):
                        if inputArgs[1] == vaultData['files'][n].split("\n")[0].replace("\t", "    ").strip():
                            vaultData['files'][n] += "\n" + inputArgs[2].replace("\t", "    ")
                            print(vaultData['files'][n])
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
                        if inputArgs[1] == f.split("\n")[0].strip():
                            
                            mke = input(Fore.YELLOW+"Are you sure? This will permanently remove this entry."+Style.RESET_ALL+"\nY/n >  ")
                            
                            if mke.upper() == "Y":
                                vaultData['files'].remove(f)

                                fw = open(configData['vaults'][currentVault], 'wb')
                                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                                fw.close()

                                refreshCommands()
                                for h in vaultData['files']:
                                    COMMANDS.append(h.split("\n")[0])

                                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                                for f in vaultData['files']:
                                    print("   -  " + f.split("\n")[0])
                            else:
                                print("Cancelled remove operation")
                                
                            break
                else:
                    print("Remove entry format:\nremove <entry's name>")

            # Command to edit an entry `edit <name>`
            elif inputArgs[0].upper() == "EDIT":
                if len(inputArgs) >= 2:
                    for i, f in enumerate(vaultData['files']):
                        if inputArgs[1] == f.split("\n")[0].strip():
                            # Open terminal text editor to start editing entry
                            vaultData['files'][i] = editableInput(f.replace("\t", "    ")).replace("\t", "    ")
                            # Save newly edited data to vault
                            fw = open(configData['vaults'][currentVault], 'wb')
                            fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                            fw.close()
                            
                            break
                else:
                    print("Edit entry format:\edit <entry's name>")
            
            # Command to print all contained data `printeverything`
            elif inputArgs[0].upper() == "PRINTEVERYTHING":
                mke = input(Fore.YELLOW+"Are you sure? This will print the contents of ALL entries to the terminal."+Style.RESET_ALL+"\nY/n >  ")
                if mke.upper() == "Y":
                    while True:
                        passw = getpass(Fore.BLACK + Back.WHITE + "Enter password to continue: " + Style.RESET_ALL)
                        fr = open(configData['vaults'][currentVault], 'rb')
                        dat = decrypt(fr.read(), password)
                        fr.close()
                        try:
                            jsdat = json.loads(dat)
                            print(json.dumps(jsdat, indent=2).replace("\\n", "\n"))
                            break
                        except:
                            print(Fore.RED + "Incorrect Password" + Fore.WHITE)
                            continue
            
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
                    
                dataIn = {}
                dataIn['files'] = []
                fw = open(validDirectory+newValDir, 'wb')
                fw.write(encrypt(bytes(json.dumps(dataIn), "utf-8"), password))
                fw.close()

                sw = input("Switch to new vault? " + Fore.GREEN + nam + Fore.RESET + "\nY/n >  ")
                if sw.upper() == "Y":
                    vaultName = configData['vaults'][-1]
                    currentVault = len(configData['vaults'])-1
                    vaultData = dataIn
                
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
        Command to create a new entry with <name>. Make sure to use
        quotes to have multiple words, and use escape \\n to do newline.

    append <name> "<content (in quotes)>"
        Command to append a string to existing entry

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
"""
                print(helpText)
                
            # If not a command, check if the user is trying to view a file
            else:
                occurrences = 0
                for f in vaultData['files']:
                    if inputArgs[0] == f.split("\n")[0].strip():
                        # If the file is found more than once, then delete the other version
                        if occurrences >= 1:
                            vaultData['files'].remove(f)
                            fw = open(configData['vaults'][currentVault], 'wb')
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
                fw = open(configData['vaults'][currentVault], 'wb')
                fw.write(encrypt(bytes(json.dumps(vaultData), "utf-8"), vaultPassword))
                fw.close()
                
                print(Fore.BLACK + Back.GREEN + "Files in Vault: " + Style.RESET_ALL)
                for f in vaultData['files']:
                    print("     " + f.split("\n")[0])
                    
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

                    fw = open(configData['vaults'][currentVault], 'wb')
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
