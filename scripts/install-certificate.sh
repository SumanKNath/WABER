mkdir -p /usr/share/ca-certificates/mitmproxy
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem  /usr/share/ca-certificates/mitmproxy/mitmproxy-ca-cert.crt
mkdir -p /usr/local/share/ca-certificates/mitmproxy
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem  /usr/local/share/ca-certificates/mitmproxy/mitmproxy-ca-cert.crt
#sudo dpkg-reconfigure ca-certificates
sudo update-ca-certificates
