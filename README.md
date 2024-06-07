# Summarize Telegram Bot

A Telegram bot that can summarize content from link.

## Usage

### Install

First, clone the repo.

```
cd /etc
git clone https://github.com/fernvenue/summarize-telegram-bot
cd ./summarize-telegram-bot
```

Create Python virtual environment.

```
apt install python3 python3-venv
python3 -m venv venv
```

Install the requirments.

```
./venv/bin/pip3 install -r requirements
```

Create environment file.

```
vim ./.env
```

Check [.env.example](./.env.example) for the details.

### Run

Once complete the installation, you can run the bot.

```
./venv/bin/python3 ./bot.py
```

If everything goes well, creae a systemd service for bot.

```
vim /etc/systemd/system/summarize-telegram-bot.service
```

Check [systemd service template](./summarize-telegram-bot.service) for the details, after that, you can run the bot as system service.

```
systemctl enable summarize-telegram-bot --now
systemctl status summarize-telegram-bot
```
