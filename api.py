import os, requests, json, base64, urllib3
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict

# Compiled Protos
import GetGiftStoreDetails_pb2
import GetWallet_pb2
import SendGift_pb2

load_dotenv()
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- CONFIG ---
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
USER_AGENT = "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

PREFIX_MAP = {
    "902": "Avatar", "214": "Facepaint", "101": "Female Skills", "102": "Male Skills",
    "103": "Microchip", "905": "Parachute", "710": "Bundle", "720": "Bundle2",
    "203": "Top", "204": "Bottom", "205": "Shoes", "211": "Head", "901": "Banner",
    "131": "Pet2", "130": "Pets/Emotes", "903": "Loot Box", "904": "Backpack",
    "906": "Skyboard", "907": "Others", "908": "Vehicles", "909": "Emote",
    "911": "SkyWings", "922": "Skill Skin",
}

def encrypt_payload(data):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def get_server_url(region):
    if region == "IND":
        return "https://client.ind.freefiremobile.com"
    elif region in ["BR", "US", "SAC", "NA"]:
        return "https://client.us.freefiremobile.com"
    else:
        return "https://clientbp.ggpolarbear.com"

def decode_jwt(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        dec = json.loads(base64.b64decode(p))
        return dec.get("lock_region"), dec.get("external_id")
    except:
        return None, None

# GET API: Wallet check with URL parameters
@app.route('/wallet', methods=['GET'])
def wallet_check():
    jwt_token = request.args.get('jwt')
    
    if not jwt_token:
        return jsonify({
            "success": False, 
            "message": "JWT token is required. Usage: /wallet?jwt=YOUR_JWT_TOKEN"
        }), 400
    
    region, login_token = decode_jwt(jwt_token)
    if not region:
        return jsonify({"success": False, "message": "Invalid JWT token"}), 400
    
    try:
        req = GetWallet_pb2.CSGetWalletReq(login_token=login_token, topup_rebate=False)
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/octet-stream",
            "User-Agent": USER_AGENT
        }
        
        r = requests.post(
            f"{get_server_url(region)}/GetWallet",
            data=encrypt_payload(req.SerializeToString()),
            headers=headers,
            verify=False,
            timeout=10
        )
        
        if r.status_code == 200:
            res_pb = GetWallet_pb2.CSGetWalletRes()
            res_pb.ParseFromString(r.content)
            w = res_pb.wallet
            ts = datetime.fromtimestamp(w.last_topup_time).strftime('%d %b %Y, %I:%M %p') if w.last_topup_time > 0 else "Never"
            
            return jsonify({
                "success": True,
                "region": region,
                "data": {
                    "gold": w.coins,
                    "diamond": w.gems,
                    "last_topup": ts
                }
            })
        else:
            return jsonify({"success": False, "message": f"Garena Error: {r.status_code}"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# GET API: Store items with URL parameters
@app.route('/store', methods=['GET'])
def store_items():
    jwt_token = request.args.get('jwt')
    
    if not jwt_token:
        return jsonify({
            "success": False,
            "message": "JWT token is required. Usage: /store?jwt=YOUR_JWT_TOKEN"
        }), 400
    
    region, _ = decode_jwt(jwt_token)
    if not region:
        return jsonify({"success": False, "message": "Invalid JWT token"}), 400
    
    try:
        req_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsReq(store_id=1)
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/octet-stream",
            "User-Agent": USER_AGENT
        }
        
        r = requests.post(
            f"{get_server_url(region)}/GetGiftStoreDetails",
            data=encrypt_payload(req_pb.SerializeToString()),
            headers=headers,
            verify=False,
            timeout=15
        )
        
        if r.status_code == 200:
            res_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsRes()
            res_pb.ParseFromString(r.content)
            res_dict = MessageToDict(res_pb, preserving_proto_field_name=True, always_print_fields_with_no_presence=True)
            
            all_items = []
            for item in res_dict.get('items', []):
                item_id_str = str(item.get('item_id', '0'))
                category = PREFIX_MAP.get(item_id_str[:3], f"Other ({item_id_str[:3]})")
                
                g, c = int(item.get('gems_price', 0)), int(item.get('coins_price', 0))
                
                all_items.append({
                    "item_id": item_id_str,
                    "commodity_id": item.get('commodity_id'),
                    "category": category,
                    "diamond_price": g,
                    "gold_price": c,
                    "expire_timestamp": int(item.get('expire_timestamp', 0))
                })
            
            all_items.sort(key=lambda x: x['expire_timestamp'], reverse=True)
            
            return jsonify({
                "success": True,
                "region": region,
                "data": {
                    "total_items": len(all_items),
                    "items": all_items[:20]  # First 20 items for quick response
                }
            })
        else:
            return jsonify({"success": False, "message": f"Garena Error: {r.status_code}"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Simple GET API: Like system (example format)
@app.route('/like', methods=['GET'])
def like_system():
    uid = request.args.get('uid')
    server_name = request.args.get('server_name')
    jwt_token = request.args.get('jwt')
    
    if not all([uid, server_name]):
        return jsonify({
            "success": False,
            "message": "Required parameters: uid, server_name. Optional: jwt"
        }), 400
    
    # If JWT provided, also return wallet info
    wallet_info = None
    if jwt_token:
        region, login_token = decode_jwt(jwt_token)
        if region:
            try:
                req = GetWallet_pb2.CSGetWalletReq(login_token=login_token, topup_rebate=False)
                headers = {
                    "Authorization": f"Bearer {jwt_token}",
                    "X-GA": "v1 1",
                    "ReleaseVersion": "OB53",
                    "Content-Type": "application/octet-stream",
                    "User-Agent": USER_AGENT
                }
                r = requests.post(
                    f"{get_server_url(region)}/GetWallet",
                    data=encrypt_payload(req.SerializeToString()),
                    headers=headers,
                    verify=False,
                    timeout=10
                )
                if r.status_code == 200:
                    res_pb = GetWallet_pb2.CSGetWalletRes()
                    res_pb.ParseFromString(r.content)
                    w = res_pb.wallet
                    wallet_info = {
                        "gold": w.coins,
                        "diamond": w.gems
                    }
            except:
                pass
    
    response_data = {
        "success": True,
        "message": f"Liked user {uid} on {server_name} server!",
        "user_details": {
            "uid": uid,
            "server": server_name
        }
    }
    
    if wallet_info:
        response_data["wallet"] = wallet_info
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)