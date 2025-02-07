from flask import Flask, request, jsonify
import requests
import os
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)

ODOO_CONFIG = {
    'url': 'https://shop47.odoo.com',
    'db': 'shop47',
    'password': 'Aminumina2002@'
}

# Quản lý phiên làm việc
class OdooSession:
    def __init__(self):
        self.session_id = None
        self.session_timestamp = None
        
    def con_han(self):
        if not self.session_id or not self.session_timestamp:
            return False
        # Kiểm tra thời hạn phiên (1 giờ)
        return datetime.now() - self.session_timestamp < timedelta(hours=1)
    
    def xac_thuc(self):
        """Xác thực với Odoo và lấy session ID"""
        auth_endpoint = "https://shop47.odoo.com/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
            "db": ODOO_CONFIG['db'],
            "login": "dat.nguyen.huu.484@gmail.com",
            "password": ODOO_CONFIG['password']
    }
}

        try:
            response = requests.post(auth_endpoint, json=payload)
            response.raise_for_status()  # Kiểm tra lỗi HTTP
            self.session_id = response.cookies.get('session_id')
            self.session_timestamp = datetime.now()
            return self.session_id
        except requests.exceptions.RequestException as e:
            raise Exception(f"Xác thực thất bại: {str(e)}")

# Khởi tạo phiên
odoo_session = OdooSession()

# Decorator để kiểm tra xác thực
def yeu_cau_xac_thuc_odoo(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not odoo_session.con_han():
            odoo_session.xac_thuc()
        return f(*args, **kwargs)
    return decorated_function

def goi_odoo_api(model, method, args=None, kwargs=None):
    """Gọi Odoo API theo đúng format JSON-RPC"""
    if not odoo_session.con_han():
        odoo_session.xac_thuc()
    
    headers = {'Content-Type': 'application/json'}
    cookies = {'session_id': odoo_session.session_id}

    # Đảm bảo args và kwargs không bị None
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    payload = {
        "jsonrpc": "2.0",
        "params": {
            "model": model,
            "method": method,
            "args": args,
            "kwargs": kwargs
        }
    }

    try:
        response = requests.post(
            f"{ODOO_CONFIG['url']}/web/dataset/call_kw",  # Đúng endpoint của Odoo
            json=payload,
            headers=headers,
            cookies=cookies
        )
        response.raise_for_status()  # Kiểm tra lỗi HTTP
        
        result = response.json()
        if 'error' in result:
            raise Exception(f"Lỗi Odoo API: {result['error']}")
            
        return result.get('result', {})
    except requests.exceptions.RequestException as e:
        raise Exception(f"Lỗi kết nối API: {str(e)}")



@app.route('/products', methods=['GET'])
@yeu_cau_xac_thuc_odoo
def lay_danh_sach_san_pham():
    """Lấy danh sách sản phẩm từ Odoo"""
    try:
        products = goi_odoo_api(
            model="product.product",
            method="search_read",
            kwargs={
                "fields": ["id", "name", "list_price", "default_code"],
                "limit": 10
            }
        )
        return jsonify({
            "trang_thai": "thanh_cong",
            "san_pham": products
        })
    except Exception as e:
        return jsonify({
            "trang_thai": "loi",
            "thong_bao": str(e)
        }), 500


@app.route('/order', methods=['POST'])
@yeu_cau_xac_thuc_odoo
def tao_don_hang():
    """Tạo đơn hàng mới trong Odoo"""
    try:
        data = request.json
        if not all(k in data for k in ["customer_id", "product_id", "quantity", "price"]):
            return jsonify({
                "trang_thai": "loi",
                "thong_bao": "Thiếu thông tin đơn hàng"
            }), 400

        # Chuẩn bị dữ liệu đơn hàng
        order_data = {
            "partner_id": data["customer_id"],  # ID khách hàng
            "order_line": [
                [0, 0, {  
                    "product_id": data["product_id"],  # ID sản phẩm
                    "product_uom_qty": data["quantity"],  # Số lượng
                    "price_unit": data["price"]  # Giá đơn vị
                }]
            ]
        }

        # Gọi API Odoo
        order_id = goi_odoo_api(
            model="sale.order",
            method="create",
            args=[order_data],
            kwargs={}  # Odoo yêu cầu có kwargs
        )

        return jsonify({
            "trang_thai": "thanh_cong",
            "ma_don_hang": order_id
        })
    except Exception as e:
        return jsonify({
            "trang_thai": "loi", 
            "thong_bao": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Dùng PORT từ Render
    app.run(host='0.0.0.0', port=port)