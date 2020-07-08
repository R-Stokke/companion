from companionhelper import request, post
import requests
import json

STATUS_REPORT_URL = "http://127.0.0.1:2770/report_service_status"
MAVLINK2REST_URL = "http://127.0.0.1:4777"

# holds the last status so we dont flood it
last_status = ""


class Mavlink2RestHelper:
    """
    Responsible for interfacing with Mavlink2Rest
    """

    def __init__(self):
        # store vision template data so we don't need to fetch it multiple times
        self.vision_template = """
{{
  "header": {{
    "system_id": 255,
    "component_id": 0,
    "sequence": 0
  }},
  "message": {{
    "type": "VISION_POSITION_DELTA",
    "time_usec": 0,
    "time_delta_usec": {dt},
    "angle_delta": [
      {dRoll},
      {dPitch},
      {dYaw}
    ],
    "position_delta": [
      {dx},
      {dy},
      {dz}
    ],
    "confidence": {confidence}
  }}
}}"""

        self.gps_origin_template = """
{{
  "header": {{
    "system_id": 255,
    "component_id": 0,
    "sequence": 0
  }},
  "message": {{
    "type": "SET_GPS_GLOBAL_ORIGIN",
    "latitude": {lat},
    "longitude": {lon},
    "altitude": 0,
    "target_system": 0,
    "time_usec": 0
  }}
}}
        """

        self.rangefinder_template = """
        {{
  "header": {{
    "system_id": 255,
    "component_id": 0,
    "sequence": 0
  }},
  "message": {{
    "type": "DISTANCE_SENSOR",
    "time_boot_ms": 0,
    "min_distance": 5,
    "max_distance": 5000,
    "current_distance": {0},
    "mavtype": {{
      "type": "MAV_DISTANCE_SENSOR_LASER"
    }},
    "id": 0,
    "orientation": {{
      "type": "MAV_SENSOR_ROTATION_PITCH_270"
    }},
    "covariance": 0,
    "horizontal_fov": 0.0,
    "vertical_fov": 0.0,
    "quaternion": [
      0.0,
      0.0,
      0.0,
      0.0
    ]
  }}
}}
"""

    def get_float(self, path: str) -> float:
        """
        Helper to get mavlink data from mavlink2rest
        Example: get_float('/VFR_HUD')
        Returns the data as a float or False on failure
        """
        response = request(MAVLINK2REST_URL + '/mavlink' + path)
        if not response:
            return float("nan")
        return float(response)

    def get(self, path: str) -> str:
        """
        Helper to get mavlink data from mavlink2rest
        Example: get('/VFR_HUD')
        Returns the data as text or False on failure
        """
        response = request(MAVLINK2REST_URL + '/mavlink' + path)
        if not response:
            return False
        return response

    def get_message_frequency(self, message_name):
        """
        Returns the frequency at which message "message_name" is being received, 0 if unavailable
        """
        return self.get_float('/{0}/message_information/frequency'.format(message_name))

    # TODO: Find a way to run this check for every message received without overhead
    # check https://github.com/patrickelectric/mavlink2rest/issues/9

    def ensure_message_frequency(self, message_name, msg_id, frequency):
        """
        Makes sure that a mavlink message is being received at least at "frequency" Hertz
        Returns true if successful, false otherwise
        """
        message_name = message_name.upper()
        current_frequency = self.get_message_frequency(message_name)

        # load message template from mavlink2rest helper
        try:
            data = json.loads(requests.get(
                MAVLINK2REST_URL + '/helper/message/COMMAND_LONG').text)
        except:
            return False

        # msg_id = getattr(mavutil.mavlink, 'MAVLINK_MSG_ID_' + message_name)
        data["message"]["command"] = {"type": 'MAV_CMD_SET_MESSAGE_INTERVAL'}
        data["message"]["param1"] = msg_id
        data["message"]["param2"] = int(1000/frequency)

        try:
            result = requests.post(MAVLINK2REST_URL + '/mavlink', json=data)
            return result.status_code == 200
        except Exception as error:
            report_status("Error setting message frequency: " + str(error))
            return False

    def set_param(self, param_name, param_type, param_value):
        """
        Sets parameter "param_name" of type param_type to value "value" in the autpilot
        Returns True if succesful, False otherwise
        """
        try:
            data = json.loads(requests.get(
                MAVLINK2REST_URL + '/helper/message/PARAM_SET').text)

            for i, char in enumerate(param_name):
                data["message"]["param_id"][i] = char

            data["message"]["param_type"] = {"type": param_type}
            data["message"]["param_value"] = param_value

            result = requests.post(MAVLINK2REST_URL + '/mavlink', json=data)
            return result.status_code == 200
        except Exception as error:
            print("Error setting parameter: " + str(error))
            return False

    def send_vision(self, position_deltas, rotation_deltas=[0, 0, 0], confidence=100, dt=125000):
        "Sends message VISION_POSITION_DELTA to flight controller"
        data = self.vision_template.format(dt=int(dt),
                                           dRoll=rotation_deltas[0],
                                           dPitch=rotation_deltas[1],
                                           dYaw=rotation_deltas[2],
                                           dx=position_deltas[0],
                                           dy=position_deltas[1],
                                           dz=position_deltas[2],
                                           confidence=confidence)

        # print(json.dumps(self.vision_template, indent=2))
        post(MAVLINK2REST_URL + '/mavlink', data=data)

    def send_rangefinder(self, distance: float):
        "Sends message DISTANCE_SENSOR to flight controller"
        data = self.rangefinder_template.format(int(distance*100))

        # print(json.dumps(self.vision_template, indent=2))
        post(MAVLINK2REST_URL + '/mavlink', data=data)

    def set_gps_origin(self, lat, lon):
        data = self.gps_origin_template.format(lat=int(float(lat)*1e7), lon=int(float(lon)*1e7))
        print(post(MAVLINK2REST_URL + '/mavlink', data=data))

    def get_orientation(self):
        """
        fetches ROV orientation
        """
        return self.get_float('/VFR_HUD/heading')