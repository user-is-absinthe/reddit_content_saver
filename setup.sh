#!/bin/bash

# Создание пользователя
sudo useradd -m -s /bin/bash reddit_archiver

# Копирование файлов
sudo mkdir -p /home/reddit_archiver/reddit-archiver
sudo cp -r . /home/reddit_archiver/reddit-archiver/
sudo chown -R reddit_archiver:reddit_archiver /home/reddit_archiver/reddit-archiver

# Установка зависимостей
cd /home/reddit_archiver/reddit-archiver || exit
sudo -u reddit_archiver python3 -m pip install -r requirements.txt

# Установка systemd сервиса
sudo cp systemd/reddit-archiver.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.py with your credentials"
echo "2. Start the service: sudo systemctl start reddit-archiver"
echo "3. Check status: sudo systemctl status reddit-archiver"
echo "4. View logs: sudo journalctl -u reddit-archiver -f"
