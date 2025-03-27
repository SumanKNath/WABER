import re
import datetime
import time
import os
import json
import random
from mitmproxy import http, ctx
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
env_flags = {
    '127.0.0.1:9999': None,  # reddit
    '127.0.0.1:7770': None,  # shopping
    '127.0.0.1:7780': None,  # shopping_admin 
    '127.0.0.1:8023': None,  # gitlab
    '127.0.0.1:8888': None  # wikipedia
}

# regular expressions for starting and ending task urls
start_url_logic = lambda key: re.compile(
    rf'http://{key}/\?logging=Starting(.*)')
end_url_logic = lambda key: re.compile(rf'http://{key}/\?logging=Ending(.*)')

# set the flags for each environment
for key in env_flags.keys():
    env_flags[key] = {
        "addon": None,
        "interception_allowed": None,
        "refresh": None,
        "rand_int_set": "False",
        "start_url": start_url_logic(key),
        "end_url": end_url_logic(key),
    }

# initialize current environment to an empty string
curr_env = ""

# dictionary to keep track of server disconnect and client connect times for latency
connections = {}

# regular expression for the llm proxy pattern
llm_proxy_pattern = re.compile(r'{llm_endpoint_path}')

# path to the log file
log_file = "{path_to_log_file}"

OVERLAY_JS = """
<script>
document.addEventListener("DOMContentLoaded", function popupHandler() {
    // Check localStorage to see if the pop-up has been closed
    if (!localStorage.getItem("popupClosed")) {
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
        overlay.style.zIndex = "9999";
        overlay.style.pointerEvents = "auto";

        // Disable all interactions on the rest of the page
        document.body.style.pointerEvents = "none";  // Disable all pointer events on the body
        document.body.style.overflow = "hidden";  // Disable scrolling

        // Create popup
        var popup = document.createElement("div");
        popup.style.position = "relative";
        popup.style.backgroundColor = "white";
        popup.style.padding = "20px";
        popup.style.borderRadius = "10px";
        popup.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.1)";
        popup.style.top = "700px"; // distance from the top
        popup.style.left = "600px"; // distance from the left
        popup.style.width = "400px"; // width of popup
        popup.style.height = "100px"; // height of popup

        popup.innerHTML = `
            <span id="close-popup" style="
                position: absolute;
                top: -20px;  /* Moves the close button higher */
                right: 5px;
                font-size: 24px;
                font-weight: bold;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: red;
                color: white;
                border-radius: 50%;
                cursor: pointer;
                user-select: none;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
            ">✖</span>

            <p style="margin-top: 30px;">This is a test popup!</p>
        `;

        // Append popup to overlay
        overlay.appendChild(popup);
        document.body.appendChild(overlay);

        // Close the popup when the X is clicked
        document.getElementById("close-popup").addEventListener("click", function() {
            document.body.removeChild(overlay);
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
    global env_flags, curr_env
    # no addon
    if addon == 0:
        parsed_url = urlparse(flow.request.url)
        env = f"{parsed_url.hostname}:{parsed_url.port}" if parsed_url.port else parsed_url.hostname
        match = env_flags[env]["start_url"].search(
            flow.request.url) if env in env_flags.keys() else False

        if match:
            encoded_text = match.group(1)
            decoded_text = unquote(unquote(encoded_text))
            with open(log_file, "a") as f:
                f.write(f"Starting{decoded_text}\n")
            ctx.log.info('Starting task')
            curr_env = env
            return

        match = env_flags[env]["end_url"].search(
            flow.request.url) if env in env_flags.keys() else False
        if match:
            encoded_text = match.group(1)
            decoded_text = unquote(unquote(encoded_text))
            with open(log_file, "a") as f:
                f.write(f"Ending{decoded_text}\n")
            ctx.log.info('Ending task')
            curr_env = ""
            return

        # only record efficiency metrics
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

        return

    # popup
    if addon == 1 and curr_env != "" and flow.request.path == "/popup-closed" and flow.request.method == "POST":
        # single interception
        if frequency < 2:
            env_flags[curr_env]["interception_allowed"] = "False"
            ctx.log.info("Popup closed. Single interception.")
        else:
            env_flags[curr_env]["interception_allowed"] = "True"
            env_flags[curr_env]["rand_int_set"] = "False"
            ctx.log.info(
                "POPUP CLOSED SUCCESSFULLY!#!#!# Multiple interceptions.")
        return

    parsed_url = urlparse(flow.request.url)
    env = f"{parsed_url.hostname}:{parsed_url.port}" if parsed_url.port else parsed_url.hostname

    # when task is starting, initialize flags
    match = env_flags[env]["start_url"].search(
        flow.request.url) if env in env_flags.keys() else False
    if match:
        encoded_text = match.group(1)
        decoded_text = unquote(encoded_text)
        with open(log_file, "a") as f:
            f.write(f"{decoded_text}\n")

        # initialize flags for that specific environment
        env_flags[env]["addon"] = "False"
        env_flags[env]["interception_allowed"] = "True"
        if addon > 1:
            env_flags[env]["refresh"] = "False"

        ctx.log.info('Starting task')
        curr_env = env
        return

    # when task is ending, reset all flags for each environment
    match = env_flags[env]["end_url"].search(
        flow.request.url) if env in env_flags.keys() else False
    if match:
        encoded_text = match.group(1)
        decoded_text = unquote(encoded_text)
        with open(log_file, "a") as f:
            f.write(f"{decoded_text}\n")
        env_flags[env]["addon"] = None
        env_flags[env]["interception_allowed"] = None
        if addon > 1:
            env_flags[env]["refresh"] = False
        ctx.log.info('Ending task')
        curr_env = ""
        return

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

        ctx.log.info("curr env: " + curr_env)
        if curr_env != "" and env_flags[curr_env]["addon"] is not None:
            val = env_flags[curr_env]["addon"]
            ctx.log.info("val: " + val)
            if env_flags[curr_env]['interception_allowed'] == "True":
                env_flags[curr_env]['addon'] = "True"
            ctx.log.info("Addon set to True")


def response(flow: http.HTTPFlow) -> None:
    # no addon
    if addon == 0:
        # only record efficiency metrics
        if llm_proxy_pattern.search(flow.request.url):
            connections[flow.client_conn.
                        id]["server_disconnect"] = datetime.datetime.now()
            json_response_data = flow.response.json()

            if 'choices' in json_response_data:
                content = json_response_data['choices'][0]['message'][
                    'content']
                with open(log_file, "a") as f:
                    f.write(f"LLM Response Content: {content}\n")

            if 'usage' in json_response_data:
                prompt_tokens = json_response_data['usage']['prompt_tokens']
                completion_tokens = json_response_data['usage'][
                    'completion_tokens']
                with open(log_file, "a") as f:
                    f.write(f"Prompt Tokens: {prompt_tokens}\n")
                    f.write(f"Completion Tokens: {completion_tokens}\n")

            log_latency(flow.client_conn.id)
        return

    global env_flags

    parsed_url = urlparse(flow.request.url)
    env = f"{parsed_url.hostname}:{parsed_url.port}" if parsed_url.port else parsed_url.hostname

    if llm_proxy_pattern.search(flow.request.url):
        connections[flow.client_conn.
                    id]["server_disconnect"] = datetime.datetime.now()
        json_response_data = flow.response.json()

        if 'choices' in json_response_data:
            content = json_response_data['choices'][0]['message']['content']
            with open(log_file, "a") as f:
                f.write(f"LLM Response Content: {content}\n")

        if 'usage' in json_response_data:
            prompt_tokens = json_response_data['usage']['prompt_tokens']
            completion_tokens = json_response_data['usage'][
                'completion_tokens']
            with open(log_file, "a") as f:
                f.write(f"Prompt Tokens: {prompt_tokens}\n")
                f.write(f"Completion Tokens: {completion_tokens}\n")

        log_latency(flow.client_conn.id)

    if env in env_flags.keys() and env_flags[env]["addon"] is not None:
        ctx.log.info("addon is not None")
        ctx.log.info(env_flags[env])
        if env_flags[env]['addon'] == "True" and env_flags[env][
                'interception_allowed'] == "True":
            ctx.log.info("addon and interception_allowed are both true")
            if addon == 1:
                if (env_flags[env]["start_url"].search(flow.request.url)
                        or env_flags[env]["end_url"].search(flow.request.url)
                        or (frequency > 0
                            and flow.response.headers.get("Content-Type")
                            != "text/html; charset=UTF-8") or
                    (frequency == 2 and 'popup-closed' in flow.request.url)):
                    return

                if frequency == 0:
                    add_popup(flow)
                else:
                    if env_flags[env]["rand_int_set"] == "False":
                        rand_int = random.randint(0, 1)
                        ctx.log.info(f"rand_int: {rand_int}")
                        if rand_int == 0:
                            ctx.log.info(flow)
                            env_flags[env]["rand_int_set"] = "True"
                            add_popup(flow)
                        else:
                            ctx.log.info(flow)
                            ctx.log.info(
                                f"rand_int is {rand_int} so i must just return.."
                            )
                            return
                    else:
                        add_popup(flow)
            else:
                if (env_flags[env]['start_url'].search(flow.request.url)
                        or env_flags[env]['end_url'].search(flow.request.url)
                        or (frequency > 0
                            and flow.response.headers.get("Content-Type")
                            != "text/html; charset=UTF-8")):
                    return

                if frequency == 0:
                    add_error(flow, env)
                else:
                    if env_flags[env]["refresh"] == "True":
                        if frequency == 1:
                            ctx.log.info(
                                f"Refresh detected for {flow.request.url}, allowing original response"
                            )
                            ctx.log.info(env_flags[env])
                            env_flags[env]['interception_allowed'] = "False"
                            ctx.log.info(env_flags[env])
                            return
                        else:
                            ctx.log.info(
                                f"Refresh detected for {flow.request.url}, allowing original response"
                            )
                            env_flags[env]['refresh'] = "False"
                            return

                    rand_int = random.randint(0, 1)
                    ctx.log.info(f"rand_int: {rand_int}")
                    if rand_int == 0:
                        add_error(flow, env)
                    else:
                        ctx.log.info(flow)
                        ctx.log.info(
                            f"rand_int is {rand_int} so i must just return")
                        return


def add_error(flow: http.HTTPFlow, env):
    global env_flags
    remove_header(flow.response, "Content-Security-Policy")
    remove_header(flow.response, "Strict-Transport-Security")
    if "content-type" not in flow.response.headers:
        return
    if "text/html" in flow.response.headers["content-type"]:
        if frequency == 0 and env_flags[env]["refresh"] == "True":
            ctx.log.info(
                f"Refresh detected for {flow.request.url}, allowing original response"
            )
            ctx.log.info(env_flags[env])
            env_flags[env]['interception_allowed'] = "False"
            ctx.log.info(env_flags[env])
            return

        if addon == 2:
            ctx.log.info(
                f"Modifying response for {flow.request.url} to 500 Server Error"
            )
            #flow.response.status_code = 500
            flow.response.text = "<html><body><h1>500 Server Error</h1><p>There was an error processing your request.</p></body></html>"
        elif addon == 3:
            ctx.log.info(
                f"Simulating network error: Delaying response for {flow.request.url} by 10 seconds"
            )
            env_flags[env]["og_response"] = flow.response.copy()
            time.sleep(30)
            flow.response.text = "<html><body><h1>Network Connection Error.</h1><p>Could not establish an internet connection. Trying to reconnect...</p></body></html>"

        env_flags[env]["refresh"] = "True"


def add_popup(flow: http.HTTPFlow):
    ctx.log.info(f"Modifying response for {flow.request.url}")
    remove_header(flow.response, "Content-Security-Policy")
    remove_header(flow.response, "Strict-Transport-Security")
    if "content-type" not in flow.response.headers:
        return
    if "text/html" in flow.response.headers[
            "content-type"] and flow.response.status_code == 200:
        ctx.log.info("Adding overlay js")
        flow.response.text = flow.response.text.replace(
            '</html>', OVERLAY_JS + '</html>')


def log_latency(connection_id):
    # log client connection time, disconnect time, and latency
    client_connect_time = connections[connection_id]["client_connect"]
    server_disconnect_time = connections[connection_id]["server_disconnect"]
    latency = server_disconnect_time - client_connect_time
    with open(log_file, "a") as f:
        f.write(f"Client connected at: {client_connect_time}\n")
        f.write(f"Response received at: {server_disconnect_time}\n")
        f.write(f"Latency: {latency}\n\n")
    del connections[connection_id]
