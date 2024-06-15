import requests
import xml.etree.ElementTree as ET
import json
from typing import Any
from fastapi import FastAPI
import re



from time import time
def timer_func(func): 
    # This function shows the execution time of  
    # the function object passed 
    def wrap_func(*args, **kwargs): 
        t1 = time() 
        result = func(*args, **kwargs) 
        t2 = time() 
        print(f'Function {func.__name__!r} executed in {(t2-t1):.4f}s') 
        return result 
    return wrap_func 

app = FastAPI()

token = ""

environments = {
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

throttle_status = {
    0: "NotThrottled",
    1: "AadThrottled",
    2: "MsaThrottled"
}

credential_type = {
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

domain_type = {
    1: "Unknown",
    2: "Consumer",
    3: "Managed",
    4: "Federated",
    5: "CloudFederated"
}

user_state = {
    -1: "Unknown",
    0: "Exists",
    1: "NotExist",
    2: "Throttled",
    4: "Error",
    5: "ExistsInOtherMicrosoftIDP",
    6: "ExistsBothIDPs"
}


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


@app.get("/osint/{search_str}")
@timer_func
def getTenantInfos(search_str: str) -> dict:
    # check if the search_str is a domain or a username
    if "@" in search_str:
        domain = search_str.split("@")[1]
        username = search_str
    else:
        domain = search_str
        username = f"admin@{search_str}"


    # -- Data gathering --

    #region: Get Tenant ID and Environment
    res = requests.get(
        url="https://odc.officeapps.live.com/odc/v2.1/federationprovider", 
        params={
            "domain": domain
            # "returnDiagnostics": "true",
            # "forceRefresh": "true"
        }
    )    
    raw_odc_federationprovider = res.json()

    # check if tenant exists
    if 'tenantId' not in raw_odc_federationprovider:
        return {
            "error": "Tenant not found"
        }

    tenantId = raw_odc_federationprovider["tenantId"]
    env = environments[raw_odc_federationprovider["environment"]]
    #endregion


    #region: Tenant Information (Graph API)
    if env == environments["Global"]:
        res = requests.get(
            url=f"https://graph.microsoft.com/v1.0/tenantRelationships/findTenantInformationByTenantId(tenantId='{tenantId}')",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )
        raw_tenant_information = res.json()
    else:
        raw_tenant_information = {}


    #region: User Realm V1
    res = requests.get(
        url=f"{env['loginBase']}/common/userrealm/{username}",
        params={
            "api-version": "1.0"
        }
    )
    raw_userrealm_v1 = res.json()
    #endregion


    #region: User Realm V2
    res = requests.get(
        url=f"{env['loginBase']}/common/userrealm/{username}",
        params={
            "api-version": "2.0"
        }
    )
    raw_userrealm_v2 = res.json()
    #endregion


    #region User Realm old
    res = requests.get(
        url=f"{env['loginBase']}/GetUserRealm.srf",
        params={
            "login": username
        }
    )
    raw_userrealm_old = res.json()
    #endregion

    
    #region: credential type
    # get sCtx value
    res = requests.get(
        url=env["loginBase"]
    )
    sCtx = re.search(r'"sCtx":"(.*?)"', res.text).group(1)


    res = requests.post(
        url=f"{env['loginBase']}/common/GetCredentialType",
        json={
            "username": username,
            "isOtherIdpSupported": True,
            "isRemoteNGCSupported": True,
            "isFidoSupported": True,
            "isRemoteConnectSupported": True,
            "isAccessPassSupported": True,
            "checkPhones": True,
            "isExternalFederationDisallowed": False,
            "originalRequest": sCtx
        }
    )
    raw_credential_type = res.json()
    #endregion


    #region: autodiscover GetFederationInformation
    body=f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:exm="http://schemas.microsoft.com/exchange/services/2006/messages" xmlns:ext="http://schemas.microsoft.com/exchange/services/2006/types" xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"> 
    <soap:Header>
        <a:Action soap:mustUnderstand="1">http://schemas.microsoft.com/exchange/2010/Autodiscover/Autodiscover/GetFederationInformation</a:Action>
    </soap:Header>
    <soap:Body>
        <GetFederationInformationRequestMessage xmlns="http://schemas.microsoft.com/exchange/2010/Autodiscover">
            <Request>
                <Domain>{domain}</Domain>
            </Request>
        </GetFederationInformationRequestMessage>
    </soap:Body>
</soap:Envelope>"""
    
    res = requests.post(
        url= env['autodiscoverBase'] + "/autodiscover/autodiscover.svc",
        data=body,
        headers={
            "Content-Type": "text/xml; charset=utf-8"
        }
    )
    raw_autodiscover_federation_information = res.text

    root = ET.fromstring(raw_autodiscover_federation_information)
    domains = [domain.text for domain in root.findall(".//{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domains/{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domain")]
    domains.sort()
    #endregion


    #region: OpenID Configuration
    res = requests.get(
        url=f"{env['loginBase']}/{domain}/.well-known/openid-configuration"
    )
    raw_openid_configuration = res.json()
    #endregion


    return {
        "tenantId": tenantId,
        "tenantName": get(raw_userrealm_v2, ['FederationBrandName']),
        "defaultDomain": get(raw_tenant_information, ['defaultDomainName']),
        "tenantEnvironment": {
            "tenantRegionScope": get(raw_openid_configuration, ['tenant_region_scope']),
            "tenantRegionSubScope": get(raw_openid_configuration, ['tenant_region_sub_scope']),
            "cloudInstanceDisplayName": get(env, ['displayName']),
            "cloudInstance": get(raw_openid_configuration, ['cloud_instance_name']),
            "audienceUrn": get(raw_userrealm_v1, ['cloud_audience_urn'])
        },
        "nameSpaceType": get(raw_userrealm_v2, ['NameSpaceType']),
        "federationInfo": {
            "brandName": get(raw_userrealm_old, ['FederationBrandName']),
            "protocol": get(raw_userrealm_v2, ['federation_protocol']),
            "globalVersion": get(raw_userrealm_old, ['FederationGlobalVersion']),
            "metadataUrl": get(raw_userrealm_v1, ['federation_metadata_url']),
            "activeAuthenticationUrl": get(raw_userrealm_v1, ['federation_active_auth_url'])
        },
        "loginExperiences": {
            "isSignupAllowed": not get(raw_credential_type, ['IsSignupDisallowed']),
            "local": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'Locale']),
            "bannerLogo": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'BannerLogo']),
            "tileLogo": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'TileLogo']),
            "tileDarkLogo": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'TileDarkLogo']),
            "illustration": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'Illustration']),
            "backgroundColor": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'BackgroundColor']),
            "boilerPlateText": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'BoilerPlateText']),
            "userIdLabel": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'UserIdLabel']),
            "keepMeSignedInDisabled": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'KeepMeSignedInDisabled']),
            "useTransparentLightBox": get(raw_userrealm_v2, ['TenantBrandingInfo', 0, 'UseTransparentLightBox']),
        },
        "userInfo": {
            "username": get(raw_credential_type, ['Username']),
            "displayName": get(raw_credential_type, ['Display']),
            "state": user_state[get(raw_credential_type, ['IfExistsResult'])],
            "isManaged": not get(raw_credential_type, ['IsUnmanaged']),
            "throttleStatus": throttle_status[get(raw_credential_type, ['ThrottleStatus'])],
            "credentials": {
                "preferedCredential": credential_type[get(raw_credential_type, ['Credentials', 'PrefCredential'])],
                "hasPassword": get(raw_credential_type, ['Credentials', 'HasPassword'], False),
                "HasAccessPass" : get(raw_credential_type, ['Credentials', 'HasAccessPass'], False),
                "hasDesktopSso": get(raw_credential_type, ['EstsProperties', 'DesktopSsoEnabled'], False),
                "hasRemoteNGC": get(raw_credential_type, ['Credentials', 'HasRemoteNGC'], False),
                "hasFido": get(raw_credential_type, ['Credentials', 'HasFido'], False),
                "otcNotAutoSent": get(raw_credential_type, ['Credentials', 'OtcNotAutoSent']),
                "parameters": { # if a parameter is present, it is a dict and should be presented as json in the frontend
                    "remoteNgc": get(raw_credential_type, ['Credentials', 'RemoteNgcParams']),
                    "fido": get(raw_credential_type, ['Credentials', 'FidoParams']),
                    "qrCodePin": get(raw_credential_type, ['Credentials', 'QrCodePinParams']),
                    "sas": get(raw_credential_type, ['Credentials', 'SasParams']),
                    "certAuth": get(raw_credential_type, ['Credentials', 'CertAuthParams']),
                    "google": get(raw_credential_type, ['Credentials', 'GoogleParams']),
                    "facebook": get(raw_credential_type, ['Credentials', 'FacebookParams']),
                }
            },
            "callMetadata": {
                "longRunningTransactionPartition": get(raw_credential_type, ['EstsProperties', 'CallMetadata', 'LongRunningTransactionPartition']),
                "region": get(raw_credential_type, ['EstsProperties', 'CallMetadata', 'Region']),
                "scaleUnit": get(raw_credential_type, ['EstsProperties', 'CallMetadata', 'ScaleUnit']),
                "isLongRunningTransaction": get(raw_credential_type, ['EstsProperties', 'CallMetadata', 'IsLongRunningTransaction']),
            }
        },
        "domains": domains,
        "raw": {
            "odc_federationprovider": raw_odc_federationprovider,
            "userrealm_v1": raw_userrealm_v1,
            "userrealm_v2": raw_userrealm_v2,
            "userrealm_old": raw_userrealm_old,
            "credential_type": raw_credential_type,
            "autodiscover_federationInformation": raw_autodiscover_federation_information,
            "openid_configuration": raw_openid_configuration,
            "tenant_information": raw_tenant_information
        }
    }


getTenantInfos("sorba.ch")
getTenantInfos("gd.com")
getTenantInfos("spaceforce.mil")
getTenantInfos("jd.com")

# Worldwide
#print(json.dumps(, indent=4))
# print(json.dumps(getTenantInfos("microsoft.com"), indent=4))
# print(json.dumps(getTenantInfos("ethz.ch"), indent=4))
# print(json.dumps(getTenantInfos("airforce.com"), indent=4))

# USGovGCCHigh
# print(json.dumps(getTenantInfos("gd.com"), indent=4))
# print(json.dumps(getTenantInfos("spacex.com"), indent=4))

# USGovDoD
# print(json.dumps(getTenantInfos("spaceforce.mil"), indent=4))
# print(json.dumps(getTenantInfos("army.mil"), indent=4))
# print(json.dumps(getTenantInfos("navy.mil"), indent=4))
# print(json.dumps(getTenantInfos("uscg.mil"), indent=4))

# China
# print(json.dumps(getTenantInfos("jd.com"), indent=4))
# print(json.dumps(getTenantInfos("autohome.com.cn"), indent=4))
# print(json.dumps(getTenantInfos("broadlink.com.cn"), indent=4))


