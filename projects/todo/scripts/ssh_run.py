"""Run a remote command over SSH using a password from the environment.

Usage:
  set TODO_SSH_PASSWORD=...  (Windows cmd) / $env:TODO_SSH_PASSWORD=... (PowerShell)
  .venv/Scripts/python.exe scripts/ssh_run.py [command...]

If no command is given, reads the command from stdin (useful for heredocs).
Never hardcode credentials in this file.
"""
import os
import sys

import paramiko

HOST = "43.133.2.85"
USER = "root"
PASSWORD = os.environ["TODO_SSH_PASSWORD"]

cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=15, look_for_keys=False, allow_agent=False)

stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
out = stdout.read().decode("utf-8", "replace")
err = stderr.read().decode("utf-8", "replace")
sys.stdout.write(out)
sys.stderr.write(err)
client.close()
sys.exit(stdout.channel.recv_exit_status())
