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
        du_lieu = request.get_json()
        ten_khach_hang = du_lieu.get("ten_khach_hang")
        so_dien_thoai = du_lieu.get("so_dien_thoai")
        dia_chi = du_lieu.get("dia_chi")
        san_pham = du_lieu.get("san_pham")

        if not (ten_khach_hang and so_dien_thoai and san_pham):
            return jsonify({
                "trang_thai": "loi",
                "thong_bao": "Thiếu thông tin bắt buộc"
            }), 400

        # Tìm khách hàng theo tên
        khach_hang = goi_odoo_api(
            model="res.partner",
            method="search_read",
            args=[[["name", "=", ten_khach_hang]]],
            kwargs={"fields": ["id", "phone", "street", "zip", "city"]}
        )

        if khach_hang:
            khach_hang_id = khach_hang[0]["id"]
            cap_nhat_du_lieu = {}

            # Cập nhật số điện thoại nếu chưa có
            if not khach_hang[0].get("phone"):
                cap_nhat_du_lieu["phone"] = so_dien_thoai

           # Cập nhật địa chỉ nếu chưa có và nếu có dữ liệu từ request
            if dia_chi:
                if not khach_hang[0].get("street"):
                    cap_nhat_du_lieu["street"] = dia_chi
            if "zip" in du_lieu and du_lieu["zip"]:  # Kiểm tra nếu zip có trong request và không rỗng
                if not khach_hang[0].get("zip"):
                    cap_nhat_du_lieu["zip"] = du_lieu["zip"]
            if "city" in du_lieu and du_lieu["city"]:  # Kiểm tra nếu city có trong request và không rỗng
                if not khach_hang[0].get("city"):
                    cap_nhat_du_lieu["city"] = du_lieu["city"]


            if cap_nhat_du_lieu:
                goi_odoo_api(
                    model="res.partner",
                    method="write",
                    args=[[khach_hang_id], cap_nhat_du_lieu]
                )
        else:
            # Nếu khách hàng chưa tồn tại, tạo mới
            khach_hang_id = goi_odoo_api(
                model="res.partner",
                method="create",
                args=[{
                    "name": ten_khach_hang,
                    "phone": so_dien_thoai,
                    "street": dia_chi or "",
                    "zip": "700000",
                    "city": "Hồ Chí Minh"
                }]
            )

        # Tạo đơn hàng với partner_shipping_id là khách hàng để lưu địa chỉ
        order_id = goi_odoo_api(
            model="sale.order",
            method="create",
            args=[{
                "partner_id": khach_hang_id,
                "partner_shipping_id": khach_hang_id,
                "order_line": [
                    (0, 0, {"product_id": sp["id"], "product_uom_qty": sp["so_luong"]})
                    for sp in san_pham
                ]
            }]
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



@app.route('/order/<int:order_id>', methods=['GET'])
@yeu_cau_xac_thuc_odoo
def lay_thong_tin_don_hang(order_id):
    """Lấy thông tin đơn hàng từ Odoo"""
    try:
        order = goi_odoo_api(
            model="sale.order",
            method="search_read",
            kwargs={
                "domain": [["id", "=", order_id]],
                "fields": ["id", "partner_id", "partner_shipping_id", "order_line"]
            }
        )

        if not order:
            return jsonify({
                "trang_thai": "loi",
                "thong_bao": "Không tìm thấy đơn hàng"
            }), 404

        order = order[0]

        # Lấy thông tin khách hàng và địa chỉ
        customer_id = order["partner_id"][0]
        shipping_id = order["partner_shipping_id"][0] if order["partner_shipping_id"] else customer_id

        customer_info = goi_odoo_api(
            model="res.partner",
            method="search_read",
            kwargs={
                "domain": [["id", "=", customer_id]],
                "fields": ["name", "phone"]
            }
        )

        shipping_info = goi_odoo_api(
            model="res.partner",
            method="search_read",
            kwargs={
                "domain": [["id", "=", shipping_id]],
                "fields": ["street", "city", "zip"]
            }
        )

        customer = customer_info[0] if customer_info else {}
        shipping = shipping_info[0] if shipping_info else {}

        # Lấy thông tin mặt hàng trong đơn hàng
        order_lines = goi_odoo_api(
            model="sale.order.line",
            method="search_read",
            kwargs={
                "domain": [["order_id", "=", order_id]],
                "fields": ["product_id", "product_uom_qty", "price_unit"]
            }
        )

        items = [{
            "product_id": line["product_id"][0],
            "product_name": line["product_id"][1],
            "quantity": line["product_uom_qty"],
            "price": line["price_unit"]
        } for line in order_lines]

        return jsonify({
            "trang_thai": "thanh_cong",
            "ma_don_hang": order["id"],
            "khach_hang": {
                "id": customer_id,
                "ten": customer.get("name", ""),
                "so_dien_thoai": customer.get("phone", "")
            },
            "dia_chi_giao_hang": {
                "duong": shipping.get("street", ""),
                "thanh_pho": shipping.get("city", ""),
                "ma_buu_dien": shipping.get("zip", "")
            },
            "mat_hang": items
        })
    except Exception as e:
        return jsonify({
            "trang_thai": "loi",
            "thong_bao": str(e)
        }), 500



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Dùng PORT từ Render
    app.run(host='0.0.0.0', port=port)