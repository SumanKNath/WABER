# UIAgentBenchmarkLibrary repository

## Set up mitmproxy
1. Download mitmproxy [here](https://mitmproxy.org/downloads/).
In our experiments, we use mitmproxy version [10.4.1](https://mitmproxy.org/downloads/#10.4.1/).
Since we use a Linux sandbox environment, we specifically download `mitmproxy-10.4.1-linux-x86_64.tar.gz`.
2. Extract the package by running `tar -xzf mitmproxy-10.4.1-linux-x86_64.tar.gz`.
This will create the binary executables: `mitmproxy, mitmdump, mitmweb`. 
4. Run `./mitmproxy` for the first time. This will create a `.mitmproxy` folder containing the necessary certificates to intercept HTTPS requests.
5. Run `scripts/install-certificate.sh` to install and update the certificate on your system.
6. Now, for testing, open two terminal instances. In the first terminal, run `./mitmproxy`. In the second terminal, set your proxy environment variables `export http_proxy=http://127.0.0.1:8080`, `export https_proxy=http://127.0.0.1:8080`, then run `curl https://www.google.com`. You should now see the request appear in the **first terminal** inside mitmproxy’s interactive environment. From there, you can inspect the full request and response details.

## Set up WebArena following the instructions [here](https://github.com/web-arena-x/webarena) and the environments themselves using the Docker instructions [here](https://github.com/web-arena-x/webarena/blob/main/environment_docker/README.md)

## Set up SteP agent following instructions [here](https://github.com/asappresearch/webagents-step)

## Set up AWM agent following instructions [here](https://github.com/zorazrw/agent-workflow-memory)

## Run mitmproxy with addon.py script for **efficiency** evaluation
Here are the settings for `config.json`:
```
addon:
 0: no addon 
 1: popup 
 2: server error
 3: network error
 4: random addon

frequency:
 0: first page
 1: random page once
 2: random page multiple times
```

1. Set addon: 0, frequency: 0 in `config.json`. After setting up your desired benchmark and agent, you may run `./mitmproxy -s addons.py`. This will allow you to record efficiency metrics (prompt tokens, completion tokens, latency) for each LLM call. 

## Run mitmproxy with addon.py script for **reliability** testing
Here are the settings for `config.json`:
```
addon:
 0: no addon 
 1: popup 
 2: server error
 3: network error
 4: random addon

frequency:
 0: first page
 1: random page once
 2: random page multiple times
```

1. You may choose which addon type you'd like to test your agent with, along with the frequency of its appearance. Then, you may run `./mitmproxy -s addons.py` which uses the settings defined in `config.json`. This will allow you to intercept when there is a new request made in the Docker environment, and modify the response to introduce unreliable scenarios to test the desired agent against.  



