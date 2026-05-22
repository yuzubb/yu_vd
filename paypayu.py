import aiohttp
import datetime
from useragent_changer import UserAgent

ua = UserAgent('iphone')

PROXY_URL = None

async def login(phoneNumber: str, password: str, uuid: str):
    headers = {
        'User-Agent': ua.set(),
        'Accept' : 'application/json, text/plain, */*',
        'Content-Type' : 'application/json',
        'Origin': 'https://www.paypay.ne.jp',
        'Referer':'https://www.paypay.ne.jp/app/account/sign-in',
    }
    payload = {
        "scope":"SIGN_IN",
        "client_uuid":f"{uuid}",
        "grant_type":"password",
        "username":phoneNumber,
        "password":password,
        "add_otp_prefix": True,
        "language":"ja"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://www.paypay.ne.jp/app/v1/oauth/token", headers=headers, json=payload, proxy=PROXY_URL) as login_request_response:
            return await login_request_response.json()

async def login_otp(set_uuid, otp, otpid, otp_pre):
    otp_number=otp
    headers = {
        'User-Agent': ua.set(),
        'Accept' : 'application/json, text/plain, */*',
        'Content-Type' : 'application/json',
        'Origin': 'https://www.paypay.ne.jp',
        'Referer':'https://www.paypay.ne.jp/app/account/sign-in',
    }
    payload = {
            "scope":"SIGN_IN",
            "client_uuid":f"{set_uuid}",
            "grant_type":"otp",
            "otp_prefix": str(otp_pre),
            "otp":otp_number,
            "otp_reference_id":otpid,
            "username_type":"MOBILE",
            "language":"ja"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://www.paypay.ne.jp/app/v1/oauth/token", headers=headers, json=payload, proxy=PROXY_URL) as response:
            login_response = await response.json()
            try:
                if login_response["response_type"]=="ErrorResponse":
                    return "ERR"
            except:
                return "OK"

async def check_link(cd):
    if "https://" in cd:
        cd=cd.replace("https://pay.paypay.ne.jp/","")

    headers={
        "Accept":"application/json, text/plain, */*",
        'User-Agent': ua.set(),
        "Content-Type":"application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://www.paypay.ne.jp/app/v2/p2p-api/getP2PLinkInfo?verificationCode={cd}", headers=headers, proxy=PROXY_URL) as response:
                response.raise_for_status()
                link_info = await response.json()
            
        except aiohttp.ClientError as e:
            print(f"API_REQ_EXC: {e}")
            return False
    
    result_code = link_info.get("header", {}).get("resultCode")
    if result_code != "S0000":
        return False

    order_status = link_info.get("payload", {}).get("orderStatus")
    if order_status == "PENDING":
        return link_info
    else:
        return False
    
async def link_rev(cd: str, phoneNumber: str, password: str, uuid: str, link_password: str = None):
    if "https://" in cd:
        cd=cd.replace("https://pay.paypay.ne.jp/","")
        
    async with aiohttp.ClientSession() as session:
        base_headers = {
            "Accept": "application/json, text/plain, */*",
            'User-Agent': ua.set(),
            "Content-Type": "application/json"
        }
        
        try:
            async with session.get(f"https://www.paypay.ne.jp/app/v2/p2p-api/getP2PLinkInfo?verificationCode={cd}", headers=base_headers, proxy=PROXY_URL) as response:
                response.raise_for_status()
                link_info = await response.json()

            if link_info.get("payload", {}).get("orderStatus") != "PENDING":
                return False
            
            if link_info.get("payload", {}).get("pendingP2PInfo", {}).get("isSetPasscode") and link_password is None:
                return False

        except aiohttp.ClientError as e:
            print(f"LINK_REQ_EXC: {e}")
            return False
        
        login_payload = {
            "scope":"SIGN_IN",
            "client_uuid":f"{uuid}",
            "grant_type":"password",
            "username":phoneNumber,
            "password":password,
            "add_otp_prefix": True,
            "language":"ja"
            }

        login_headers = {
            'User-Agent': ua.set(),
            'Accept' : 'application/json, text/plain, */*',
            'Content-Type' : 'application/json',
            'Origin': 'https://www.paypay.ne.jp',
            'Referer':'https://pay.paypay.ne.jp/'+cd,
        }

        async with session.post("https://www.paypay.ne.jp/app/v1/oauth/token", headers=login_headers, json=login_payload, proxy=PROXY_URL) as response:
            login_response = await response.json()
            try:
                login_response = (login_response["access_token"])
            except:
                try:
                    login_response["otp_reference_id"]
                    return "LOGINERR"
                except:
                    return "LOGINERR"
        
        receive_payload = {
            "verificationCode":cd,
            "client_uuid":uuid,
            "requestAt":str(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M:%S+0900')),
            "requestId":link_info["payload"]["message"]["data"]["requestId"],
            "orderId":link_info["payload"]["message"]["data"]["orderId"],
            "senderMessageId":link_info["payload"]["message"]["messageId"],
            "senderChannelUrl":link_info["payload"]["message"]["chatRoomId"],
            "iosMinimumVersion":"3.45.0",
            "androidMinimumVersion":"3.45.0"
            }
        
        if link_password:
            receive_payload["passcode"]=link_password

        try:
            async with session.post("https://www.paypay.ne.jp/app/v2/p2p-api/acceptP2PSendMoneyLink", json=receive_payload, headers=base_headers, proxy=PROXY_URL) as response:
                response.raise_for_status()
                receive_data = await response.json()

                if receive_data.get("header", {}).get("resultCode") == "S0000":
                    return True
                else:
                    return False

        except aiohttp.ClientError as e:
            print(f"REVERR: {e}") 
            return False

async def get_balance_rev(phoneNumber: str, password: str, uuid: str):
    """
    PayPayの残高を取得する
    
    Args:
        phoneNumber: 電話番号
        password: パスワード
        uuid: クライアントUUID
    
    Returns:
        成功時: dict {
            "money": int,        # マネー残高
            "money_light": int,  # マネーライト残高
            "all_balance": int,  # 全残高
            "useable_balance": int,  # 利用可能残高
            "points": int,       # ポイント
            "raw": dict          # 生レスポンス
        }
        失敗時: False または "LOGINERR"
    """
    async with aiohttp.ClientSession() as session:
        login_payload = {
            "scope": "SIGN_IN",
            "client_uuid": f"{uuid}",
            "grant_type": "password",
            "username": phoneNumber,
            "password": password,
            "add_otp_prefix": True,
            "language": "ja"
        }

        login_headers = {
            'User-Agent': ua.set(),
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': 'https://www.paypay.ne.jp',
            'Referer': 'https://www.paypay.ne.jp/app/account/sign-in',
        }

        async with session.post("https://www.paypay.ne.jp/app/v1/oauth/token", headers=login_headers, json=login_payload, proxy=PROXY_URL) as response:
            login_response = await response.json()
            try:
                access_token = login_response["access_token"]
            except:
                try:
                    if login_response.get("otp_reference_id"):
                        return "LOGINERR"
                except:
                    return "LOGINERR"
        
        balance_headers = {
            'User-Agent': ua.set(),
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            async with session.get(
                "https://www.paypay.ne.jp/app/v1/bff/getBalanceInfo",
                headers=balance_headers,
                proxy=PROXY_URL
            ) as response:
                balance_data = await response.json()
                
                result_code = balance_data.get("header", {}).get("resultCode")
                if result_code != "S0000":
                    return False
                
                payload = balance_data.get("payload", {})
                
                return {
                    "money": payload.get("walletDetail", {}).get("emoneyBalanceInfo", {}).get("balance", 0),
                    "money_light": payload.get("walletDetail", {}).get("prepaidBalanceInfo", {}).get("balance", 0),
                    "all_balance": payload.get("walletSummary", {}).get("allTotalBalanceInfo", {}).get("balance", 0),
                    "useable_balance": payload.get("walletSummary", {}).get("usableBalanceInfoWithoutCashback", {}).get("balance", 0),
                    "points": payload.get("walletDetail", {}).get("cashBackBalanceInfo", {}).get("balance", 0),
                    "raw": balance_data
                }
                
        except Exception as e:
            print(f"BALANCE_REQ_EXC: {e}")
            return False
