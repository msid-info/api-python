import requests
import xml.etree.ElementTree as ET
from typing import Any
from fastapi import FastAPI
import re
import os
import static


app = FastAPI()

GRAPH_TOKEN = os.environ['GRAPH_TOKEN']


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
def getTenantInfos(search_str: str) -> dict:
    # check if the search_str is a domain or a username
    if "@" in search_str:
        domain = search_str.split("@")[1]
        username = search_str
    else:
        domain = search_str
        username = f"admin@{search_str}"


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

    TENANT_ID = raw_odc_federationprovider["tenantId"]
    ENV = static.CLOUD_ENVIRONMENT[raw_odc_federationprovider["environment"]]
    #endregion


    #region: Tenant Information (Graph API)
    raw_tenant_information = {}
    if ENV == static.CLOUD_ENVIRONMENT["Global"]:
        res = requests.get(
            url=f"https://graph.microsoft.com/v1.0/tenantRelationships/findTenantInformationByTenantId(tenantId='{TENANT_ID}')",
            headers={
                "Authorization": f"Bearer {GRAPH_TOKEN}"
            }
        )
        raw_tenant_information = res.json()
    #endregion


    #region: User Realm V1
    res = requests.get(
        url=f"{ENV['loginBase']}/common/userrealm/{username}",
        params={
            "api-version": "1.0"
        }
    )
    raw_userrealm_v1 = res.json()
    #endregion


    #region: User Realm V2
    res = requests.get(
        url=f"{ENV['loginBase']}/common/userrealm/{username}",
        params={
            "api-version": "2.0"
        }
    )
    raw_userrealm_v2 = res.json()
    #endregion


    #region User Realm old
    res = requests.get(
        url=f"{ENV['loginBase']}/GetUserRealm.srf",
        params={
            "login": username
        }
    )
    raw_userrealm_old = res.json()
    #endregion

    
    #region: credential type
    raw_credential_type = {}
    if (ENV == static.CLOUD_ENVIRONMENT["Global"] or ENV == static.CLOUD_ENVIRONMENT["partner.microsoftonline.cn"]) and get(raw_userrealm_v2, ['NameSpaceType']) == 'Managed':
        # get sCtx value
        res = requests.get(
            url=ENV["loginBase"]
        )
        sCtx = re.search(r'"sCtx":"(.*?)"', res.text).group(1)


        res = requests.post(
            url=f"{ENV['loginBase']}/common/GetCredentialType",
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
        url= ENV['autodiscoverBase'] + "/autodiscover/autodiscover.svc",
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
        url=f"{ENV['loginBase']}/{domain}/.well-known/openid-configuration"
    )
    raw_openid_configuration = res.json()
    #endregion


    return {
        "tenantId": TENANT_ID,
        "tenantName": get(raw_userrealm_v2, ['FederationBrandName']),
        "defaultDomain": get(raw_tenant_information, ['defaultDomainName']),
        "tenantEnvironment": {
            "tenantRegionScope": get(raw_openid_configuration, ['tenant_region_scope']),
            "tenantRegionSubScope": get(raw_openid_configuration, ['tenant_region_sub_scope']),
            "cloudInstanceDisplayName": get(ENV, ['displayName']),
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
            "state": get(static.USER_STATE, [get(raw_credential_type, ['IfExistsResult'])]),
            "isManaged": not get(raw_credential_type, ['IsUnmanaged']), # todo: gives wrong result if is IsUnmanaged is None
            "throttleStatus": get(static.THROTTLE_STATUS, [get(raw_credential_type, ['ThrottleStatus'])]),
            "credentials": {
                "preferedCredential": get(static.CREDENTIAL_TYPE, [get(raw_credential_type, ['Credentials', 'PrefCredential'])]),
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

import time
start = time.time()
print(getTenantInfos("jmueller@sorba.ch"))
end = time.time()
print(end - start)
# getTenantInfos("gd.com")
# getTenantInfos("spaceforce.mil")
# getTenantInfos("jd.com")

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


