# vault

## How to install:

I reccommend adding it to your `~/.bashrc` file so you can access vault from any directory or without knowing it's full path.
1. Open ~/.bashrc file (or your shell config file) with nano or text editor with admin permissions.
```
sudo nano ~/.bashrc
```
2. Scroll to the very end, and add an alias to the directory `vlt.py` is in. For example, if you downloaded vault to your home directory, the `vlt.py` file would be `~/vault/vlt.py`. So you would add this to the end of the `~/.bashrc` file:
```
alias vault='python3 ~/vault/vlt.py'
```

Now you can run vault anywhere by just typing `vault`!
