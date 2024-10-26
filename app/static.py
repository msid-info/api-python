from typing import Any

def get(dictionary: dict | list, key: list[str | int], default: Any = None) -> Any:
    for k in key:
        if isinstance(k, int): 
            # key is int
            if not isinstance(dictionary, list) :
                return default
            if not k < len(dictionary):
                return default

            dictionary = dictionary[k]

        else:
            # key is str
            if not isinstance(dictionary, dict):
                return default
            if k not in dictionary:
                return default
            
            dictionary = dictionary[k]

    return dictionary


CLOUD_ENVIRONMENT = {
    "Global": { # Worldwide
        "displayName": "Worldwide",
        "loginBase": "https://login.microsoftonline.com",
        "autodiscoverBase": "https://autodiscover-s.outlook.com"
    },
    "microsoftonline.us": { # USGovGCCHigh
        "displayName": "U.S. Government GCC High",
        "loginBase": "https://login.microsoftonline.us",
        "autodiscoverBase": "https://autodiscover-s.office365.us",
    },
    "microsoftonline.mil": { # USGovDoD
        "displayName": "U.S. Government DoD",
        "loginBase": "https://login.microsoftonline.us",
        "autodiscoverBase": "https://autodiscover-s-dod.office365.us",
    },
    "partner.microsoftonline.cn": { # China
        "displayName": "Microsoft 365 operated by 21Vianet (China)",
        "loginBase": "https://login.partner.microsoftonline.cn", # login.chinacloudapi.cn
        "autodiscoverBase": "https://autodiscover-s.partner.outlook.cn",
    }
}

THROTTLE_STATUS = {
    0: "NotThrottled",
    1: "AadThrottled",
    2: "MsaThrottled"
}

CREDENTIAL_TYPE = {
    0: "None",
    1: "Password",
    2: "RemoteNGC",
    3: "OneTimeCode",
    4: "Federation",
    5: "CloudFederation",
    6: "OtherMicrosoftIdpFederation",
    7: "Fido",
    8: "GitHub",
    9: "PublicIdentifierCode",
    10: "LinkedIn",
    11: "RemoteLogin",
    12: "Google",
    13: "AccessPass",
    14: "Facebook",
    15: "Certificate",
    16: "OfflineAccount",
    17: "VerifiableCredential",
    18: "QrCodePin",
    1000: "NoPreferredCredential"
}

DOMAIN_TYPE = {
    1: "Unknown",
    2: "Consumer",
    3: "Managed",
    4: "Federated",
    5: "CloudFederated"
}

USER_STATE = {
    -1: "Unknown",
    0: "Exists",
    1: "NotExist",
    2: "Throttled",
    4: "Error",
    5: "ExistsInOtherMicrosoftIDP",
    6: "ExistsBothIDPs"
}
