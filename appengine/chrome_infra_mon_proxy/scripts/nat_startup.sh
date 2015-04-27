#!/bin/bash
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Setup a health check endpoint.
cd
echo 'OK' > index.html
python -m SimpleHTTPServer 8000 &
