import requests
import xml.etree.ElementTree as ET
import json
from time import sleep


environments = {
    "Global": { # Worldwide
        "displayName": "Global",
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
        "displayName": "Office 365 operated by 21Vianet (China)",
        "loginBase": "https://login.partner.microsoftonline.cn", # login.chinacloudapi.cn
        "autodiscoverBase": "https://autodiscover-s.partner.outlook.cn",
    }
}


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
            "domain": domain,
            "returnDiagnostics": "true",
            "forceRefresh": "true"
        }
    )    
    raw_odc_federationprovider = res.json()

    tenantId = raw_odc_federationprovider["tenantId"]
    env = environments[raw_odc_federationprovider["environment"]]
    #endregion


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
    res = requests.post(
        url=f"{env['loginBase']}/common/GetCredentialType",
        json={
            "username": username,
            "isOtherIdpSupported": True
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
    raw_autodiscover_federationInformation = res.text
    #endregion


    #region: OpenID Configuration
    res = requests.get(
        url=f"{env['loginBase']}/{domain}/.well-known/openid-configuration"
    )
    raw_openid_configuration = res.json()
    #endregion


    # -- Data processing --

    # tenantEnvironment
    tenantEnvironment = {
        "tenantRegionScope": raw_openid_configuration["tenant_region_scope"],
        "tenantRegionSubScope": raw_openid_configuration.get("tenant_region_subscope", None), # only for USGov else None
        "cloudInstanceDisplayName": env["displayName"],
        "cloudInstance": raw_openid_configuration["cloud_instance_name"],
        "audienceUrn": raw_userrealm_v1["cloud_audience_urn"]
    }

    # federationInfo
    nameSpaceType = raw_userrealm_v2["NameSpaceType"]
    federationInfo = None
    if nameSpaceType == "Federated":
        federationInfo = {
            "brandName": raw_userrealm_old["FederationBrandName"],
            "protocol": raw_userrealm_v2["federation_protocol"],
            "globalVersion": raw_userrealm_old["FederationGlobalVersion"],
            "metadataUrl": raw_userrealm_v1["federation_metadata_url"],
            "activeAuthenticationUrl": raw_userrealm_v1["federation_active_auth_url"]
        }


    # loginExperiences
    loginExperiences = None
    if raw_userrealm_v2["TenantBrandingInfo"] is not None:
        brandingInfo = raw_userrealm_v2["TenantBrandingInfo"][0]
        loginExperiences = {
            "local": brandingInfo.get("Locale", None),
            "bannerLogo": brandingInfo.get("BannerLogo", None),
            "tileLogo": brandingInfo.get("TileLogo", None),
            "tileDarkLogo": brandingInfo.get("TileDarkLogo", None),
            "illustration": brandingInfo.get("Illustration", None),
            "backgroundColor": brandingInfo.get("BackgroundColor", None),
            "boilerPlateText": brandingInfo.get("BoilerPlateText", None),
            "userIdLabel": brandingInfo.get("UserIdLabel", None),
            "keepMeSignedInDisabled": brandingInfo.get("KeepMeSignedInDisabled", None),
            "useTransparentLightBox": brandingInfo.get("UseTransparentLightBox", None),
        }

    
    # userInfo
    
    

    # domains
    root = ET.fromstring(raw_autodiscover_federationInformation)
    domains = [domain.text for domain in root.findall(".//{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domains/{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domain")]
    domains.sort()  # type: ignore

    # data residency
    dataResidency = None
    if raw_odc_federationprovider["diagnosticData"]["DsApi"] is not []:
        






    #region: User Info

    loginExperiences["IsSignupAllowed"] = (credential_type["IsSignupDisallowed"] == False)

    if username:
        user_info["Exists"] = (credential_type["IfExistsResult"] == 0)
        user_info["IsManaged"] = (credential_type["IsUnmanaged"] == False)
        user_info["ThrottleStatus"] = credential_type["ThrottleStatus"]
        user_info["HasPassword"] = credential_type["Credentials"]["HasPassword"]

        if "EstsProperties" in credential_type:
            if "DesktopSsoEnabled" in credential_type["EstsProperties"]:
                user_info["DesktopSsoEnabled"] = credential_type["DesktopSsoEnabled"]
    #endregion





    return {
        "tenantId": tenantId,
        "tenantEnvironment": tenantEnvironment,
        "dataResidency": { # not always present
            "tenantCountryCode": "CH",
            "tenantTelemetryRegion": "EMEA",
            "azureAdRegion": "EU",
            "m365DataBoundary": [
                "EUDB"
            ],
            "defaultMailboxRegion": "CHE",
            "allowedMailboxRegions": [
                "CHE"
            ],
        },
        "nameSpaceType": nameSpaceType, # Federated, Managed, CloudFederated???
        "federationInfo": federationInfo,
        "loginExperiences": loginExperiences,
        "userInfo": {
            "username": "admin@ethz.ch",
            "displayName": "admin@ethz.ch",
            "authenticationUrl": "https://idbdfedin16.ethz.ch/adfs/ls/?username=admin%40ethz.ch&wa=wsignin1.0&wtrealm=urn%3afederation%3aMicrosoftOnline&wctx=",
            "userState": 2,
            "doesExist": True,
            "isManaged": True,
            "throttleStatus": 1,
            "Credentials": {
                "PrefCredential": 1,
                "HasPassword": True,
                "RemoteNgcParams": None,
                "FidoParams": None,
                "SasParams": None,
                "CertAuthParams": None,
                "GoogleParams": None,
                "FacebookParams": None,
                "OtcNotAutoSent": False
            }
        },
        "domains": domains,
        "raw": {
            "odc_federationprovider": raw_odc_federationprovider,
            "userrealm_v1": raw_userrealm_v1,
            "userrealm_v2": raw_userrealm_v2,
            "userrealm_old": raw_userrealm_old,
            "credential_type": raw_credential_type,
            "autodiscover_federationInformation": raw_autodiscover_federationInformation,
            "openid_configuration": raw_openid_configuration
        }
    }


# Worldwide
# print(json.dumps(getTenantInfos("sorba.ch"), indent=4))
# print(json.dumps(getTenantInfos("microsoft.com"), indent=4))
print(json.dumps(getTenantInfos("ethz.ch"), indent=4))
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


