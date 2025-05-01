import re
import datetime
import time
import os
import json
import random
from mitmproxy import http, ctx
from mitmproxy.script import concurrent
from urllib.parse import unquote, urlparse

# path to the config file that keeps the user settings for addon and frequency
config_file_path = 'config.json'


# function to read the config settings
def read_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


# read addon and frequency from the config file
data = read_json(config_file_path)

# retrieve the addon and frequency settings from the dictionary, using default values of 0 if the keys are not present
addon = data['addon']
ctx.log.info(f'addon: {addon}')
frequency = data['frequency']
ctx.log.info(f'frequency: {frequency}')

# check addon for randomness
if addon == 4:
    addon = random.randint(1, 3)

# initialize flags for all environments to test

# Match evals URLs
curr_env = re.compile(
    #r'https://evals-(.*).vercel.app(/.*)?')
    r'https://evals-(.*).vercel.app/$')

interception_allowed = False  # Initialize with a boolean, not None or string
intercepted_urls = {}  # Track URLs that have been intercepted

rand_int_set = False

refresh = False  # Initialize with a boolean, not string

# Initialize connections dictionary
connections = {}

# regular expressions for starting and ending task urls
start_url_logic = re.compile(
    r'https://example.com/Starting_(.*)')
end_url_logic = re.compile(
    r'https://example.com/Ending_(.*)')

# dictionary to keep track of server disconnect and client connect times for latency
connections = {}

# regular expression for the llm proxy pattern
llm_endpoint_path = r'https://actionengineaoai.openai.azure.com'
llm_proxy_pattern = re.compile(llm_endpoint_path)

# path to the log file
log_file = "/home/sukara/test_agisdk_new.log"

OVERLAY_JS = """
<script>
document.addEventListener("DOMContentLoaded", function popupHandler() {
    // Check if an overlay already exists to prevent duplicates
    if (document.getElementById("my-overlay")) {
        console.log("Overlay already exists, not creating another one");
        return;
    }
    
    // Check localStorage to see if the pop-up has been closed
    if (!localStorage.getItem("popupClosed")) {
        console.log("Creating overlay popup");
        
        // Create overlay
        var overlay = document.createElement("div");
        overlay.id = "my-overlay";
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100%";
        overlay.style.height = "100%";
        overlay.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
        overlay.style.display = "flex";
        overlay.style.justifyContent = "center";
        overlay.style.alignItems = "center";
        overlay.style.zIndex = "9999";
        overlay.style.pointerEvents = "auto";

        // Disable all interactions on the rest of the page
        document.body.style.pointerEvents = "none";  // Disable all pointer events on the body
        document.body.style.overflow = "hidden";  // Disable scrolling

        // Create popup
        var popup = document.createElement("div");
        popup.id = "my-popup";
        popup.style.position = "relative";
        popup.style.backgroundColor = "white";
        popup.style.padding = "20px";
        popup.style.borderRadius = "10px";
        popup.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.1)";
        popup.style.width = "400px"; // width of popup
        popup.style.height = "100px"; //` height of popup

        popup.innerHTML = `
            <span id="close-popup" style="
                position: absolute;
                top: -20px;  /* Keep the close button inside the popup */
                right: 5px;
                font-size: 24px;
                font-weight: bold;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: red;
                color: white;
                border-radius: 50%;
                cursor: pointer;
                user-select: none;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
                z-index: 10000;  /* Make sure it's above everything */
            ">✖</span>

            <p style="margin-top: 5px;">Use this code to get $10 savings: FRIENDS</p>
        `;

        // Append popup to overlay
        overlay.appendChild(popup);
        document.body.appendChild(overlay);

        // Close the popup when the X is clicked
        var closeButton = document.getElementById("close-popup");
        console.log("Close button element:", closeButton);
        
        closeButton.addEventListener("click", function() {
            console.log("Close button clicked");
            var overlayElement = document.getElementById("my-overlay");
            if (overlayElement) {
                document.body.removeChild(overlayElement);
                console.log("Overlay removed");
            }
            
            localStorage.setItem("popupClosed", "true"); // Store flag in localStorage
            document.body.style.pointerEvents = "auto";  // Re-enable pointer events after popup is closed
            document.body.style.overflow = "auto";  // Re-enable scrolling

            // Send a signal to the server to stop interception
            fetch("/popup-closed", { method: "POST" });

            // remove event listener when we remove pop-up so if we want to intercept again it can
            document.removeEventListener("DOMContentLoaded", popupHandler);
            localStorage.removeItem("popupClosed");
        });
    }
});
</script>

"""



# function to remove a specific header from response
def remove_header(response, header_name):
    if header_name in response.headers:
        del response.headers[header_name]


def request(flow: http.HTTPFlow):
    global curr_env, interception_allowed, rand_int_set, refresh, intercepted_urls
    
    # Check if this is a start URL
    if start_url_logic.search(flow.request.url):
        with open(log_file, "a") as f:
            match = start_url_logic.search(flow.request.url)
            f.write(f"Starting{match.group(1)}\n")
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('Starting task')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        interception_allowed = True  # Use boolean True instead of string
        ctx.log.info(f"[DEBUG] interception allowed changed to {interception_allowed}!!!")
        return
    
    # Check if this is an end URL
    if end_url_logic.search(flow.request.url):
        encoded_text = end_url_logic.search(flow.request.url).group(1)
        with open(log_file, "a") as f:
            f.write(f"{encoded_text}\n")
        interception_allowed = False  # Reset to boolean False instead of None
        refresh = False
        intercepted_urls = {}
        ctx.log.info('!!!!!!!!!!!!!!!!!!')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('Ending task')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('&*&*&*&*&*&*&*&*&*')
        ctx.log.info('!!!!!!!!!!!!!!!!!!')
        # Reset curr_env to its original regex pattern if needed
        curr_env = re.compile(r'https://evals-(.*).vercel.app/$')  # Uncomment if needed
        return
    
    # Handle popup closed signal for addon 1
    if addon == 1 and curr_env.search(flow.request.url) and flow.request.path == "/popup-closed" and flow.request.method == "POST":
        # For single interception frequency
        if frequency < 2:
            interception_allowed = False  # Use boolean False instead of string
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info("Popup closed. Single interception.")
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
            ctx.log.info('!!!!!!!!!!!!!!!!!!')
        else:
            interception_allowed = True  # Use boolean True instead of string
            rand_int_set = False  # Use boolean False instead of string
            ctx.log.info("POPUP CLOSED SUCCESSFULLY!#!#!# Multiple interceptions.")
        return
    
    # Record LLM proxy requests for all addons (including addon=0)
    if llm_proxy_pattern.search(flow.request.url):
        connections[flow.client_conn.id] = {
            "client_connect": datetime.datetime.now()
        }
        json_request_data = flow.request.json()
        ctx.log.info(f"Logging LLM request")

        if 'messages' in json_request_data:
            content = json_request_data['messages'][0]['content']
            with open(log_file, "a") as f:
                f.write(f"LLM Request Content: {content}\n")


@concurrent
def response(flow: http.HTTPFlow):
    global rand_int_set, interception_allowed, refresh, intercepted_urls
    
    parsed_url = urlparse(flow.request.url)
    env = f"{parsed_url.hostname}:{parsed_url.port}" if parsed_url.port else parsed_url.hostname

    # Debug: Log URL and content type
    ctx.log.info(f"[DEBUG] Processing URL: {flow.request.url}")
    if "content-type" in flow.response.headers:
        ctx.log.info(f"[DEBUG] Content-Type: {flow.response.headers['content-type']}")
        
    # Skip config endpoints and other non-webpage URLs explicitly
    if "/config" in flow.request.url or "config?run_id" in flow.request.url:
        ctx.log.info(f"[DEBUG] Skipping config endpoint: {flow.request.url}")
        return

    # Debug: Check if this is a JavaScript file
    if "content-type" in flow.response.headers and "javascript" in flow.response.headers["content-type"].lower():
        ctx.log.info(f"[DEBUG] JavaScript file detected: {flow.request.url}")
        ctx.log.info(f"[DEBUG] Global addon value: {addon}")
    
    # Handle LLM proxy responses for all addons
    if llm_proxy_pattern.search(flow.request.url):
        ctx.log.info(f"[DEBUG] LLM proxy request detected")
        connections[flow.client_conn.id]["server_disconnect"] = datetime.datetime.now()
        json_response_data = flow.response.json()

        if 'choices' in json_response_data:
            content = json_response_data['choices'][0]['message']['content']
            with open(log_file, "a") as f:
                f.write(f"LLM Response Content: {content}\n")

        if 'usage' in json_response_data:
            prompt_tokens = json_response_data['usage']['prompt_tokens']
            completion_tokens = json_response_data['usage']['completion_tokens']
            with open(log_file, "a") as f:
                f.write(f"Prompt Tokens: {prompt_tokens}\n")
                f.write(f"Completion Tokens: {completion_tokens}\n")

        log_latency(flow.client_conn.id)
        

    # For addon=0, we only log LLM metrics without any interception
    if addon == 0:
        return
        
    # Skip interception if not allowed
    if not interception_allowed:  # Fixed comparison to use boolean check
        ctx.log.info("[DEBUG] interception_allowed is False")
        return
    
    # Skip interception for start/end URLs
    if (start_url_logic.search(flow.request.url) or 
        end_url_logic.search(flow.request.url)):
        ctx.log.info("[DEBUG] Skipping interception due to URL")
        return

    if addon == 5:
        # Handle JavaScript files for addon=5
        content_type = flow.response.headers["content-type"].lower()
        is_javascript = "application/javascript" in content_type or "text/javascript" in content_type or "application/x-javascript" in content_type
        
        if is_javascript:
            ctx.log.info(f"[DEBUG] JavaScript file with addon=5: {flow.request.url}")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"[DEBUG] Starting JavaScript delay of 25 seconds for: {flow.request.url}")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            time.sleep(5)
            ctx.log.info(f"[DEBUG] JavaScript delay completed for: {flow.request.url}")
            
            #interception_allowed = False
            ctx.log.info(f"[DEBUG] interception_allowed: {interception_allowed}")

            return

    # otherwise we check if addon=1, 2, or 3 and modify response accordingly below 
    
    # Check if this URL matches our target environment pattern
    env_match = curr_env.search(flow.request.url)
    if not env_match:
        ctx.log.info(f"[DEBUG] URL does not match target environment pattern: {flow.request.url}")
        return
        
    # Only intercept HTML content for the main page
    if "content-type" not in flow.response.headers or "text/html" not in flow.response.headers["content-type"]:
        ctx.log.info(f"[DEBUG] Not HTML content, skipping: {flow.request.url}")
        return
  
    # For frequency=0 (always intercept) or first interception with frequency>0
    if frequency == 0 and refresh is False:
        ctx.log.info(f"[DEBUG] Processing interception for addon={addon}")
        
        if addon == 1:
            # Popup addon
            add_popup(flow)
        elif addon in [2, 3]:
            # Error addons
            add_error(flow, env)
        
                
    # Handle refresh flag for addon 2 or 3 with frequency=0
    # This ensures interception is disabled after refresh for these addons
    elif frequency == 0 and refresh is True and addon in [2, 3, 5]:
        ctx.log.info(f"[DEBUG] Refresh detected for addon {addon} with frequency=0, disabling further interceptions")
        interception_allowed = False
        refresh = False


def add_error(flow: http.HTTPFlow, env):
    global interception_allowed, refresh
    
    # Debug logging
    ctx.log.info(f"[DEBUG] add_error called for URL: {flow.request.url}")
    
    remove_header(flow.response, "Content-Security-Policy")
    remove_header(flow.response, "Strict-Transport-Security")
    
    if "content-type" not in flow.response.headers:
        ctx.log.info("[DEBUG] No content-type header, returning")
        return
    
    if "text/html" in flow.response.headers["content-type"]:
        
        if addon == 2:
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"[DEBUG] Modifying response to 500 Server Error")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            request_url = flow.request.url
            flow.response.text = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>500 Server Error</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #5f6368;
            margin: 0;
            padding: 0;
            background-color: #f7f7f7;
            padding-top: 100px;
        }}
        .container {{
            text-align: left;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            font-size: 20px;
            font-weight: 500;
            margin-bottom: 20px;
            color: #202124;
        }}
        p {{
            font-size: 14px;
            line-height: 1.5;
            margin-bottom: 30px;
            color: #5f6368;
        }}
        .error-code {{
            margin-top: 20px;
            font-size: 14px;
            color: #5f6368;
        }}
        .reload-button {{
            display: inline-block;
            background-color: #1a73e8;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            margin-top: 20px;
        }}
        .reload-button:hover {{
            background-color: #1765cc;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>This page isn't working</h1>
        <p>{request_url} is currently unable to handle this request</p>
        <div class="error-code">HTTP ERROR 500</div>
        <button class="reload-button" onclick="window.location.reload()">Reload</button>
    </div>
</body>
</html>
"""
        elif addon == 3:
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"[DEBUG] Simulating network error with 25s delay")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
            time.sleep(2)
            flow.response.text = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No Internet</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #5f6368;
            margin: 0;
            padding: 0;
            background-color: #f7f7f7;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }
        .container {
            text-align: center;
            max-width: 600px;
            padding: 20px;
        }
        h1 {
            font-size: 24px;
            font-weight: 500;
            margin-bottom: 10px;
        }
        p {
            font-size: 16px;
            line-height: 1.5;
            margin-bottom: 20px;
        }
        ul {
            text-align: left;
            padding-left: 20px;
        }
        li {
            margin-bottom: 8px;
        }
        .error-code {
            margin-top: 30px;
            font-size: 12px;
            color: #80868b;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>No internet</h1>
        <p>Try:</p>
        <ul>
            <li>Checking the network cables, modem, and router</li>
            <li>Reconnecting to Wi-Fi</li>
            <li>Running Windows Network Diagnostics</li>
        </ul>
        <div class="error-code">ERR_INTERNET_DISCONNECTED</div>
    </div>
</body>
</html>
"""
        ctx.log.info(f"[DEBUG] Setting refresh=True")
        refresh = True


def add_popup(flow: http.HTTPFlow):
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"[DEBUG] Modifying response with popup for {flow.request.url}")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    ctx.log.info(f"!#!#!#!##!!#!#!#!#!#!#!!#!#!#!#!#!#!#!#!##!")
    remove_header(flow.response, "Content-Security-Policy")
    remove_header(flow.response, "Strict-Transport-Security")
    if "content-type" not in flow.response.headers:
        return
    if "text/html" in flow.response.headers[
            "content-type"] and flow.response.status_code == 200:
        ctx.log.info("[DEBUG] Adding overlay js")
        flow.response.text = flow.response.text.replace(
            '</html>', OVERLAY_JS + '</html>')


def log_latency(connection_id):
    # log client connection time, disconnect time, and latency
    if connection_id not in connections:
        ctx.log.info(f"[DEBUG] Connection ID {connection_id} not found in connections dictionary")
        return
        
    client_connect_time = connections[connection_id]["client_connect"]
    server_disconnect_time = connections[connection_id]["server_disconnect"]
    latency = server_disconnect_time - client_connect_time
    with open(log_file, "a") as f:
        f.write(f"Client connected at: {client_connect_time}\n")
        f.write(f"Response received at: {server_disconnect_time}\n")
        f.write(f"Latency: {latency}\n\n")
    del connections[connection_id]
