import os, requests, json, base64, urllib3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict

# Compiled Protocol Engine Buffers
import GetGiftStoreDetails_pb2
import GetWallet_pb2
import SendGift_pb2

load_dotenv()
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- SECURE MASTER CRYPTO CONFIG ---
CORE_CIPHER_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
CORE_CIPHER_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
CLIENT_AGENT_SPOOF = "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

CATEGORY_MAP_PRO = {
    "902": "Avatar Frame", "214": "Face Paint", "101": "Female Core Skills", "102": "Male Core Skills", 
    "103": "Microchips", "905": "Parachutes", "710": "Premium Bundles", "720": "Super Bundles", 
    "203": "Jackets/Tops", "204": "Pants/Bottoms", "205": "Sneakers/Shoes", "211": "Head/Hairs", "901": "Banners", 
    "131": "Pet Evolution", "130": "Pet Emotes", "903": "Loot Boxes", "904": "Tactical Backpacks", 
    "906": "Skyboards", "907": "Exotic Others", "908": "Super Vehicles", "909": "Vip Emotes", 
    "911": "SkyWings Flight", "922": "Skill Weapon Skins",
}

ZIBON_SYSTEM_CACHE = {}

def perform_aes_injection(payload_bytes):
    cipher_engine = AES.new(CORE_CIPHER_KEY, AES.MODE_CBC, CORE_CIPHER_IV)
    return cipher_engine.encrypt(pad(payload_bytes, AES.block_size))

def fetch_regional_endpoint(region_id):
    if region_id == "IND": return "https://client.ind.freefiremobile.com"
    elif region_id in ["BR", "US", "SAC", "NA"]: return "https://client.us.freefiremobile.com"
    return "https://clientbp.ggpolarbear.com"

def extract_jwt_payload(token_string):
    try:
        segment = token_string.split('.')[1]
        segment += '=' * (4 - len(segment) % 4)
        parsed_json = json.loads(base64.b64decode(segment))
        return parsed_json.get("lock_region"), parsed_json.get("external_id")
    except Exception: return None, None

def dispatch_wallet_query(jwt, login_token, region):
    req_structure = GetWallet_pb2.CSGetWalletReq(login_token=login_token, topup_rebate=False)
    api_headers = {
        "Authorization": f"Bearer {jwt}", "X-GA": "v1 1", "ReleaseVersion": "OB53", 
        "Content-Type": "application/octet-stream", "User-Agent": CLIENT_AGENT_SPOOF
    }
    try:
        endpoint = f"{fetch_regional_endpoint(region)}/GetWallet"
        encrypted_body = perform_aes_injection(req_structure.SerializeToString())
        res = requests.post(endpoint, data=encrypted_body, headers=api_headers, verify=False, timeout=10)
        if res.status_code == 200:
            wallet_pb = GetWallet_pb2.CSGetWalletRes()
            wallet_pb.ParseFromString(res.content)
            w_data = wallet_pb.wallet
            formatted_time = datetime.fromtimestamp(w_data.last_topup_time).strftime('%d-%b-%Y, %I:%M %p') if w_data.last_topup_time > 0 else "N/A"
            return {"gold": w_data.coins, "diamond": w_data.gems, "last_topup": formatted_time}
    except Exception: pass
    return {"gold": 0, "diamond": 0, "last_topup": "SYNC_FAILED"}

@app.route('/')
def serve_mainframe():
    return render_template('index.html')

@app.route('/api/image/<item_id>')
def proxy_asset_image(item_id):
    try:
        img_res = requests.get(f"{IMAGE_BASE_URL}{item_id}.png", timeout=5)
        return Response(img_res.content, mimetype='image/png')
    except Exception: return "Asset Not Resolved", 404

@app.route('/api/get_store', methods=['POST'])
def fetch_matrix_store():
    payload = request.json
    jwt_token = payload.get('jwt')
    page = int(payload.get('page', 1))
    limit = int(payload.get('limit', 24))
    selected_category = payload.get('category', 'All')
    
    region, login_token = extract_jwt_payload(jwt_token)
    if not region: return jsonify({"success": False, "message": "CRITICAL: DECRYPTION REJECTED (INVALID JWT)"}), 400

    if jwt_token not in ZIBON_SYSTEM_CACHE:
        wallet_stats = dispatch_wallet_query(jwt_token, login_token, region)
        req_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsReq(store_id=1)
        api_headers = {
            "Authorization": f"Bearer {jwt_token}", "X-GA": "v1 1", "ReleaseVersion": "OB53", 
            "Content-Type": "application/octet-stream", "User-Agent": CLIENT_AGENT_SPOOF
        }
        
        try:
            endpoint = f"{fetch_regional_endpoint(region)}/GetGiftStoreDetails"
            encrypted_payload = perform_aes_injection(req_pb.SerializeToString())
            res = requests.post(endpoint, data=encrypted_payload, headers=api_headers, verify=False, timeout=15)
            
            if res.status_code == 200:
                res_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsRes()
                res_pb.ParseFromString(res.content)
                dict_converted = MessageToDict(res_pb, preserving_proto_field_name=True, always_print_fields_with_no_presence=True)
                
                compiled_items, unique_categories = [], set()
                for proto_item in dict_converted.get('items', []):
                    str_id = str(proto_item.get('item_id', '0'))
                    cat_title = CATEGORY_MAP_PRO.get(str_id[:3], f"Unassigned ({str_id[:3]})")
                    unique_categories.add(cat_title)
                    
                    diamonds = int(proto_item.get('gems_price', 0))
                    coins = int(proto_item.get('coins_price', 0))
                    
                    price_lbl = "Free Tier"
                    if diamonds > 0 and coins > 0: price_lbl = f"💎 {diamonds} / 🪙 {coins}"
                    elif diamonds > 0: price_lbl = f"💎 {diamonds}"
                    elif coins > 0: price_lbl = f"🪙 {coins}"
                    
                    expiry_timestamp = int(proto_item.get('expire_timestamp', 0))
                    date_lbl = datetime.fromtimestamp(expiry_timestamp).strftime('%d %b %Y') if expiry_timestamp > 0 else "Lifetime Asset"

                    compiled_items.append({
                        "item_id": str_id, "commodity_id": proto_item.get('commodity_id'),
                        "sort_id": int(proto_item.get('sort_id', 0)), "price_str": price_lbl,
                        "category": cat_title, "expire_date": date_lbl
                    })

                compiled_items.sort(key=lambda x: x['sort_id'], reverse=True)
                ZIBON_SYSTEM_CACHE[jwt_token] = {
                    'items': compiled_items, 'wallet': wallet_stats, 
                    'sent': dict_converted.get('send_gift_times_today', 0), 'cats': sorted(list(unique_categories))
                }
            else: return jsonify({"success": False, "message": "Garena Core Server Refused Response Code"}), 400
        except Exception as err: return jsonify({"success": False, "message": f"Fatal Core Exception: {str(err)}"}), 500

    cached_data = ZIBON_SYSTEM_CACHE[jwt_token]
    filtered_output = [x for x in cached_data['items'] if x['category'] == selected_category] if selected_category != "All" else cached_data['items']
    offset = (page - 1) * limit
    
    return jsonify({
        "success": True, "items": filtered_output[offset : offset + limit], 
        "categories": cached_data['cats'], "wallet": cached_data['wallet'], 
        "sent_today": cached_data['sent'], "has_more": (offset + limit) < len(filtered_output)
    })

@app.route('/api/send_gift', methods=['POST'])
def pipe_gift_transmission():
    req_payload = request.json
    jwt = req_payload.get('jwt')
    target_uid = req_payload.get('receiver_uid')
    comm_id = req_payload.get('commodity_id')
    unit_price = req_payload.get('price')
    currency_type = req_payload.get('currency')
    custom_message = req_payload.get('message', 'Gift Dispatch!')
    
    region, _ = extract_jwt_payload(jwt)
    if not region: return jsonify({"success": False, "message": "EXPLOIT DENIED: TOKEN AUTH DISCREPANCY"}), 400

    pb_request = SendGift_pb2.CSSendGiftReq()
    pb_request.receiver_account_ids.append(int(target_uid))
    pb_request.buddy_type = 1
    pb_request.commodity_id = int(comm_id)
    pb_request.message_content = custom_message
    pb_request.currency_type = 2 if currency_type == 'diamond' else 1
    pb_request.commodity_cnt = 1
    pb_request.unit_price = int(unit_price)

    api_headers = {
        "Authorization": f"Bearer {jwt}", "X-GA": "v1 1", "ReleaseVersion": "OB53", 
        "Content-Type": "application/octet-stream", "User-Agent": CLIENT_AGENT_SPOOF
    }
    
    try:
        endpoint_url = f"{fetch_regional_endpoint(region)}/SendGift"
        encrypted_body = perform_aes_injection(pb_request.SerializeToString())
        res = requests.post(endpoint_url, data=encrypted_body, headers=api_headers, verify=False, timeout=15)
        
        if res.status_code == 200:
            if jwt in ZIBON_SYSTEM_CACHE: del ZIBON_SYSTEM_CACHE[jwt] # Flush out cache state
            return jsonify({"success": True, "message": f"✓ SUCCESS: Packet injected. Gift transmitted to UID: {target_uid}"})
        else:
            try: return_error = res.content.decode('utf-8').strip()
            except Exception: return_error = f"HTTP STATUS CODE: {res.status_code}"
            return jsonify({"success": False, "message": f"✖ TRANSMIT REFUSED: {return_error}"})
    except Exception as e: 
        return jsonify({"success": False, "message": f"💥 CRITICAL PIPELINE CORRUPTION: {str(e)}"})

if __name__ == '__main__':
    app.run(port=8080)
