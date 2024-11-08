import httpx
import xml.etree.ElementTree as ET
from fastapi import FastAPI
import endpoint
import asyncio
from static import (
    get, 
    CLOUD_ENVIRONMENT, 
    THROTTLE_STATUS, 
    CREDENTIAL_TYPE, 
    USER_STATE
)


app = FastAPI(
    openapi_url=None
)


@app.get("/osint/{search_str}")
async def getTenantInfos(search_str: str) -> dict:
    # check if the search_str is a domain or a username
    if "@" in search_str:
        domain = search_str.split("@")[1]
        username = search_str
    else:
        domain = search_str
        username = f"admin@{search_str}"


    async with httpx.AsyncClient(http2=True) as client:
        raw_odc_federationprovider = await endpoint.get_federtion_provider(client, domain)

        # check if tenant exists
        if 'tenantId' not in raw_odc_federationprovider:
            return {
                "error": "Tenant not found"
            }
        
        
        TENANT_ID = raw_odc_federationprovider["tenantId"]
        ENV = CLOUD_ENVIRONMENT[raw_odc_federationprovider["environment"]]

        async with asyncio.TaskGroup() as tg:
            task_userrealm_v1 = tg.create_task(endpoint.get_user_realm_v1(client, ENV["loginBase"], username))
            task_userrealm_v2 = tg.create_task(endpoint.get_user_realm_v2(client, ENV["loginBase"], username))
            task_userrealm_old = tg.create_task(endpoint.get_user_realm_old(client, ENV["loginBase"], username))
            task_autodiscover_federat = tg.create_task(endpoint.get_autodiscover_federation_information(client, ENV["autodiscoverBase"], domain))
            task_openid_configuration = tg.create_task(endpoint.get_openid_configuration(client, ENV["loginBase"], domain))

            if ENV == CLOUD_ENVIRONMENT["Global"]:
                task_tenant_information = tg.create_task(endpoint.get_tenant_information(client, TENANT_ID))

            if (ENV == CLOUD_ENVIRONMENT["Global"] or ENV == CLOUD_ENVIRONMENT["partner.microsoftonline.cn"]):  # and get(raw_userrealm_v2, ['NameSpaceType']) == 'Managed':
                task_credential_type = tg.create_task(endpoint.get_credential_type(client, ENV["loginBase"], username))


        raw_userrealm_v1 = task_userrealm_v1.result()
        raw_userrealm_v2 = task_userrealm_v2.result()
        raw_userrealm_old = task_userrealm_old.result()
        raw_autodiscover_federation_information = task_autodiscover_federat.result()
        raw_openid_configuration = task_openid_configuration.result()


        if ENV == CLOUD_ENVIRONMENT["Global"]:
            raw_tenant_information = task_tenant_information.result()
        else:
            raw_tenant_information = {}

        if (ENV == CLOUD_ENVIRONMENT["Global"] or ENV == CLOUD_ENVIRONMENT["partner.microsoftonline.cn"]): # and get(raw_userrealm_v2, ['NameSpaceType']) == 'Managed':
            raw_credential_type = task_credential_type.result()
        else:
            raw_credential_type = {}

        root = ET.fromstring(raw_autodiscover_federation_information)
        domains = [domain.text for domain in root.findall(".//{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domains/{http://schemas.microsoft.com/exchange/2010/Autodiscover}Domain")]
        domains.sort()

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
                "state": get(USER_STATE, [get(raw_credential_type, ['IfExistsResult'])]),
                "isManaged": not get(raw_credential_type, ['IsUnmanaged']), # todo: gives wrong result if is IsUnmanaged is None
                "throttleStatus": get(THROTTLE_STATUS, [get(raw_credential_type, ['ThrottleStatus'])]),
                "credentials": {
                    "preferedCredential": get(CREDENTIAL_TYPE, [get(raw_credential_type, ['Credentials', 'PrefCredential'])]),
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


## Examples: 
# Worldwide
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


