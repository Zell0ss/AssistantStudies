

## references
https://github.com/microsoft/IoT-For-Beginners/blob/main/6-consumer/lessons/1-speech-recognition/pi-audio.md

https://pimylifeup.com/raspberry-pi-chatgpt/

https://platform.openai.com/usage
https://openai.com/pricing#language-models

## Create a service for the telegram bot
On the file sebastian.service you need to edit the lines 
```bash
WorkingDirectory=/home/user/data/sebasbot
 . . .
ExecStart=/bin/bash -c "/home/user/data/sebasbot/.venv/bin/python sebastian_bot.py"
```
so they actually point to the folder where you have the code, then it must be copied onto /etc/systemd/system/sebastian.service
```bash
host:~/data/tests $ ll /etc/systemd/system/sebastian.service 
-rw-r--r-- 1 root root 325 Jan 27  2024 /etc/systemd/system/sebastian.service
```
Once done you need to enable the service, reload the service daemon and then enable the service
```bash
sudo systemctl enable sebastian.service
sudo systemctl daemon-reload
sudo systemctl start sebastian.service
```