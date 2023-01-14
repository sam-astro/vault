# vault

## How to install:
1. Download vault:
```
git clone https://github.com/sam-astro/vault.git
cd ./vault
```

2. Install requirements:
```
pip3 install -r requirements.txt
```

3. I reccommend adding it to your `~/.bashrc` or `~/.zshrc` file so you can access vault from any directory and without knowing it's full path, like a normal command. Open ~/.bashrc file (or your shell config file) with nano or text editor with admin permissions.
```
sudo nano ~/.bashrc
```

4. Scroll to the very end, and add an alias to the directory `vlt.py` is in. For example, if you downloaded vault to your home directory, the `vlt.py` file would be `~/vault/vlt.py`. So you would add this to the end of the `~/.bashrc` file:
```bash
alias vault='python3 ~/vault/vlt.py'
```

Now you can run vault anywhere by just typing `vault`!

## Use

After adding the alias to vault like above (which I highly reccommend but isn't necessary), run the command with no arguments.
```ruby
$ vault
```
You will be prompted with a screen like this:
```
Vault version v1.x.x
You have the latest version of Vault.
Enter directory to store existing or new vaults
(ex. "/home/vault/")
 >  _
```
Enter the path to a place you want to store your vault files. I reccommend choosing a location that you won't accidentally delete, like in `/home/`. If the folder doesn't exist it will be created.

Now you will be prompted for the name of the vault:
```
Enter name of new vault
(ex. "MyVault")
 >  _
```
This will be used to identify the vault, you can name it anything you want, but avoid special characters like `@#$%^&*{}[]`, as well as spaces.

Finally just create a master password. Each vault can have it's own unique master password. You should make sure it is very secure, I reccommend at least 12 digits, and randomly generated. Enter and confirm your password
```
Create vault password:
Confirm password:
```

### Your first vault was created! Now what?

Vaults are perfect for storing sensitive text files and passwords. To create your first encrypted text file, type:
```
>  new <name>
```
Replace \<name\> with the name of your file, such as `SecretDoc`.

This command will create a new entry, as well as open the text editor. Use the arrow keys to navigate and type in any information you want. ***Remember: The first line of a file is automatically used as it's title. Do not edit this line unless you are purposely trying to change the title.***

After you make all of your changes, press `Ctrl+S` to save, then `Ctrl+Q` to exit the text editor. When you return, you will see something like: 
```
Files in Vault:
   -  SecretDoc
```
This is your vault listing. It shows all of the files that are held in your vault. you can show this at any time using the command `list` or `ls`.

To edit an entry you already made, use the command:
```
>  edit <name>
```

### Other commands:
These are all of the other commands you can use in vault:

#### encrypt [-rm] \<file\>
        Encrypts a file, (optional: [-rm] (DELETES original file))

#### decrypt \<file\> [-o <output file>]
        Decrypt a .EF file (optional: [-o <output file>] specify the
        output destination for decrypted data)

#### passcreate \<name\>
        Create password entry in vault, which has the ability to be
        randomly generated
        
#### passrefresh \<password entry\>
        Randomly generates a new password inside the password entry,
        and keeps the old one just in case you need it to change to
        the new one.

#### exit/quit
        Safely exit and clear terminal of any viewed data. Ctrl+C
        also does this.

#### help
        Show this help menu

#### list/ls
        List the name of all the entries present in this vault, like
        a directory

#### clear/cls
        Clear the terminal window of all text, this should be used
        after you access sensitive information and passwords so
        nobody can see previous printouts

#### new/create <name>
        Command to create a new entry with <name>. Make sure to use
        quotes to have multiple words, and use escape \\n to do newline.

#### append <name> "\<content (in quotes)\>"
        Command to append a string to existing entry

#### remove <name>
        PERMANENTLY delete an entry. This process is irreversible

#### printeverything
        Print the entire vault json data to the terminal. !! (This
        process shows all of the unencrypted entries, and is only
        recommended for debugging)
        
#### newvault
        Start the process of creating a new, separate vault

#### edit <name>
        Edit contents of an existing entry, will open in-terminal text editor.
            Text editor commands:
            * Ctrl+S   Save the entry
            * Ctrl+F   Search for word
            * Ctrl+G   Find next word (after search)
            * Ctrl+D   Delete current line
            * Ctrl+Q   Quit entry editor and return to vault
