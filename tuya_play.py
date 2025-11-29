import hashlib
import hmac
import json
import time
import requests

TO_B_TOKEN_API = "/v1.0/token"

class TuyaTokenInfo:
    def __init__(self, token_response=None):
        result = token_response.get("result", {})

        self.expire_time = (
            token_response.get("t", 0)
            + result.get("expire", result.get("expire_time", 0)) * 1000
        )
        self.access_token = result.get("access_token", "")
        self.refresh_token = result.get("refresh_token", "")
        self.uid = result.get("uid", "")


def calculate_sign(method, path, params, body, access_id, access_key, token_info=None):
    str_to_sign = method
    str_to_sign += "\n"

    content_to_sha256 = (
        "" if body is None or len(body.keys()) == 0 else json.dumps(body)
    )

    str_to_sign += hashlib.sha256(content_to_sha256.encode("utf8")).hexdigest().lower()
    str_to_sign += "\n"
    str_to_sign += "\n"
    str_to_sign += path

    if params is not None and len(params.keys()) > 0:
        str_to_sign += "?"

        query_builder = ""
        params_keys = sorted(params.keys())

        for key in params_keys:
            query_builder += f"{key}={params[key]}&"
        str_to_sign += query_builder[:-1]

    t = int(time.time() * 1000)

    message = access_id
    if token_info is not None:
        message += token_info.access_token
    message += str(t) + str_to_sign
    
    sign = (
        hmac.new(
            access_key.encode("utf8"),
            msg=message.encode("utf8"),
            digestmod=hashlib.sha256,
        )
        .hexdigest()
        .upper()
    )
    return sign, t


def request(method, path, params, body, access_id, access_key, api_endpoint, token_info=None):
    access_token = ""
    if token_info:
        access_token = token_info.access_token

    sign, t = calculate_sign(method, path, params, body, access_id, access_key, token_info)
    
    headers = {
        "client_id": access_id,
        "sign": sign,
        "sign_method": "HMAC-SHA256",
        "access_token": access_token,
        "t": str(t),
        "lang": "en",
    }
    headers["dev_lang"] = "python"
    headers["dev_version"] = "0.1.2"
    headers["dev_channel"] = "cloud_"

    url = f"{api_endpoint}{path}"
    
    try:
        if method == "GET":
            response = requests.get(url=url, params=params, json=body, headers=headers, timeout=10)
        else:
            response = requests.post(url=url, params=params, json=body, headers=headers, timeout=10)

        result = response.json()
        return result
    except Exception as e:
        print(f"Request error: {e}")
        return {"success": False, "msg": str(e)}


def get_power_voltage_current(device_id, access_id, access_key, api_endpoint, token_info):
    try:
        path = f"/v1.0/devices/{device_id}/status"
        result = request("GET", path, None, None, access_id, access_key, api_endpoint, token_info)
        
        if result.get("success"):
            status = result.get("result", [])
            
            voltage = None
            current = None
            power = None
            
            for item in status:
                code = item.get("code")
                value = item.get("value")
                
                if value is None or not isinstance(value, (int, float)):
                    continue

                if code in ["cur_voltage", "voltage", "v"]:
                    voltage = value / 10

                elif code in ["cur_current", "current", "i"]:
                    current = value / 1000
                
                elif code in ["cur_power", "power", "p"]:
                    power = value / 10

            if power is not None or voltage is not None or current is not None:
                return power, voltage, current
        
        path = f"/v2.0/cloud/thing/{device_id}/shadow/properties"
        result = request("GET", path, None, None, access_id, access_key, api_endpoint, token_info)

        if not result.get("success"):
            return None, None, None

        properties = result.get("result", {}).get("properties", [])

        voltage = None
        current = None
        power = None

        for prop in properties:
            code = prop.get("code")
            value = prop.get("value")
            
            if value is None or not isinstance(value, (int, float)):
                continue
            
            if code in ["output_voltage", "voltage", "cur_voltage", "v"]:
                voltage = value / 10

            elif code in ["output_current", "current", "cur_current", "i"]:
                current = value / 1000

            elif code in ["output_power", "power", "cur_power", "p"]:
                power = value / 10

        return power, voltage, current
    
    except Exception as e:
        print(f"Error getting power data: {e}")
        return None, None, None


def get_device_switch(device_id, access_id, access_key, api_endpoint, token_info, switch_code="switch"):
    try:
        path = f"/v1.0/devices/{device_id}/status"
        result = request("GET", path, None, None, access_id, access_key, api_endpoint, token_info)
        
        if not result.get("success"):
            return None
        
        status = result.get("result", [])

        for item in status:
            if item.get("code") == switch_code:
                return item.get("value")

        if switch_code == "switch_1":
            for item in status:
                if item.get("code") == "switch":
                    return item.get("value")

        if switch_code == "switch":
            for item in status:
                if item.get("code") == "switch_1":
                    return item.get("value")
        
        return None
    except Exception as e:
        print(f"Error getting switch status: {e}")
        return None


def set_device_switch(value: bool, device_id, access_id, access_key, api_endpoint, token_info, switch_code="switch"):
    try:
        path = f"/v1.0/devices/{device_id}/commands"
        body = {"commands": [{"code": switch_code, "value": value}]}
        result = request("POST", path, None, body, access_id, access_key, api_endpoint, token_info)
        
        if not result.get("success"):
            error_msg = str(result.get("msg", "")).lower()
            if "does not exist" in error_msg or "not support" in error_msg:
                alt_code = "switch_1" if switch_code == "switch" else "switch"
                body = {"commands": [{"code": alt_code, "value": value}]}
                result = request("POST", path, None, body, access_id, access_key, api_endpoint, token_info)

                if result.get("success"):
                    print(f"Device uses '{alt_code}' instead of '{switch_code}'")
                    return True, alt_code
        
        if result.get("success"):
            print(f"Device {'ON' if value else 'OFF'} successfully.")
            return True, switch_code
        else:
            print("Failed to control device:", result)
            return False, switch_code
    except Exception as e:
        print(f"Error setting switch: {e}")
        return False, switch_code