sudo mkdir -p /usr/share/ca-certificates/mitmproxy
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem  /usr/share/ca-certificates/mitmproxy/mitmproxy-ca-cert.crt
sudo mkdir -p /usr/local/share/ca-certificates/mitmproxy
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem  /usr/local/share/ca-certificates/mitmproxy/mitmproxy-ca-cert.crt
sudo update-ca-certificates
