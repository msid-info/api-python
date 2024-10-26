import httpx
import re


async def get_federtion_provider(client: httpx.Client, domain: str) -> dict:
    response = await client.get(
        url="https://odc.officeapps.live.com/odc/v2.1/federationprovider",
        params={
            "domain": domain
            # "returnDiagnostics": "true",
            # "forceRefresh": "true"
        }
    )
    return response.json()


async def get_tenant_information(client: httpx.Client, graph_token: str, tenant_id: str) -> dict:
    response = await client.get(
        url=f"https://graph.microsoft.com/v1.0/tenantRelationships/findTenantInformationByTenantId(tenantId='{tenant_id}')",
        headers={
            "Authorization": f"Bearer {graph_token}"
        }
    )
    return response.json()


async def get_user_realm_v1(client: httpx.Client, login_base: str, username: str) -> dict:
    response = await client.get(
        url=f"{login_base}/common/userrealm/{username}",
        params={
            "api-version": "1.0"
        }
    )
    return response.json()


async def get_user_realm_v2(client: httpx.Client, login_base: str, username: str) -> dict:
    response = await client.get(
        url=f"{login_base}/common/userrealm/{username}",
        params={
            "api-version": "2.0"
        }
    )
    return response.json()


async def get_user_realm_old(client: httpx.Client, login_base: str, username: str) -> dict:
    response = await client.get(
        url=f"{login_base}/GetUserRealm.srf",
        params={
            "login": username
        }
    )
    return response.json()


async def get_credential_type(client: httpx.Client, login_base: str, username: str) -> dict:
    response = await client.get(url=login_base, follow_redirects=True)
    sCtx = re.search(r'"sCtx":"(.*?)"', response.text).group(1)

    response = await client.post(
        url=f"{login_base}/common/GetCredentialType",
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
    return response.json()


async def get_autodiscover_federation_information(client: httpx.Client, autodiscover_base: str, domain: str) -> str:
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
    response = await client.post(
        url= f"{autodiscover_base}/autodiscover/autodiscover.svc",
        data=body,
        headers={
            "Content-Type": "text/xml; charset=utf-8"
        }
    )
    return response.text


async def get_openid_configuration(client: httpx.Client, login_base: str, domain: str) -> dict:
    response = await client.get(
        url=f"{login_base}/{domain}/.well-known/openid-configuration"
    )
    return response.json()
