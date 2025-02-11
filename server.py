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




# @app.route('/order', methods=['POST'])
# @yeu_cau_xac_thuc_odoo
# def tao_don_hang():
#     """Tạo đơn hàng mới trong Odoo, hỗ trợ nhiều sản phẩm bằng cách gửi nhiều request"""
#     try:
#         du_lieu = request.get_json()
#         ten_khach_hang = du_lieu.get("ten_khach_hang")
#         so_dien_thoai = du_lieu.get("so_dien_thoai")
#         dia_chi = du_lieu.get("dia_chi")
#         san_pham_id = du_lieu.get("id")  # ID sản phẩm
#         so_luong = du_lieu.get("so_luong")  # Số lượng sản phẩm

#         if not (ten_khach_hang and so_dien_thoai and san_pham_id and so_luong):
#             return jsonify({
#                 "trang_thai": "loi",
#                 "thong_bao": "Thiếu thông tin bắt buộc"
#             }), 400

#         # Tìm hoặc tạo khách hàng
#         khach_hang = goi_odoo_api(
#             model="res.partner",
#             method="search_read",
#             args=[[["name", "=", ten_khach_hang]]],
#             kwargs={"fields": ["id", "phone"]}
#         )

#         if khach_hang:
#             khach_hang_id = khach_hang[0]["id"]
#             if not khach_hang[0].get("phone"):
#                 goi_odoo_api(
#                     model="res.partner",
#                     method="write",
#                     args=[[khach_hang_id], {"phone": so_dien_thoai}]
#                 )
#         else:
#             khach_hang_id = goi_odoo_api(
#                 model="res.partner",
#                 method="create",
#                 args=[{
#                     "name": ten_khach_hang,
#                     "phone": so_dien_thoai
#                 }]
#             )

#         # Tạo đơn hàng cho từng sản phẩm
#         order_id = goi_odoo_api(
#             model="sale.order",
#             method="create",
#             args=[{
#                 "partner_id": khach_hang_id,
#                 "partner_shipping_id": khach_hang_id,
#                 "order_line": [(0, 0, {"product_id": san_pham_id, "product_uom_qty": so_luong})]
#             }]
#         )

#         return jsonify({
#             "trang_thai": "thanh_cong",
#             "ma_don_hang": order_id
#         })
#     except Exception as e:
#         return jsonify({
#             "trang_thai": "loi",
#             "thong_bao": str(e)
#         }), 500




# @app.route('/order/<int:order_id>', methods=['GET'])
# @yeu_cau_xac_thuc_odoo
# def lay_thong_tin_don_hang(order_id):
#     """Lấy thông tin đơn hàng từ Odoo"""
#     try:
#         # Lấy thông tin đơn hàng
#         order = goi_odoo_api(
#             model="sale.order",
#             method="search_read",
#             kwargs={
#                 "domain": [["id", "=", order_id]],
#                 "fields": ["id", "partner_id", "partner_shipping_id", "order_line"]
#             }
#         )

#         if not order:
#             return jsonify({
#                 "trang_thai": "loi",
#                 "thong_bao": "Không tìm thấy đơn hàng"
#             }), 404

#         order = order[0]

#         # Lấy thông tin khách hàng và địa chỉ
#         customer_id = order["partner_id"][0]
#         shipping_id = order["partner_shipping_id"][0] if order["partner_shipping_id"] else customer_id

#         customer_info = goi_odoo_api(
#             model="res.partner",
#             method="search_read",
#             kwargs={
#                 "domain": [["id", "=", customer_id]],
#                 "fields": ["name", "phone"]
#             }
#         )

#         shipping_info = goi_odoo_api(
#             model="res.partner",
#             method="search_read",
#             kwargs={
#                 "domain": [["id", "=", shipping_id]],
#                 "fields": ["street", "city", "zip"]
#             }
#         )

#         customer = customer_info[0] if customer_info else {}
#         shipping = shipping_info[0] if shipping_info else {}

#         # Lấy thông tin mặt hàng trong đơn hàng
#         order_lines = goi_odoo_api(
#             model="sale.order.line",
#             method="search_read",
#             kwargs={
#                 "domain": [["order_id", "=", order_id]],
#                 "fields": ["product_id", "product_uom_qty", "price_unit"]
#             }
#         )

#         # Tạo danh sách sản phẩm và tính tổng tiền
#         items = []
#         tong_so_tien = 0

#         for line in order_lines:
#             product_id = line["product_id"][0]
#             product_name = line["product_id"][1]
#             quantity = line["product_uom_qty"]
#             price = line["price_unit"]
#             total_price = quantity * price

#             items.append({
#                 "product_id": product_id,
#                 "product_name": product_name,
#                 "quantity": quantity,
#                 "price": price,
#                 "total_price": total_price  # Tổng tiền cho từng sản phẩm
#             })

#             tong_so_tien += total_price  # Cộng dồn vào tổng số tiền đơn hàng

#         return jsonify({
#             "trang_thai": "thanh_cong",
#             "ma_don_hang": order["id"],
#             "khach_hang": {
#                 "id": customer_id,
#                 "ten": customer.get("name", ""),
#                 "so_dien_thoai": customer.get("phone", "")
#             },
#             "dia_chi_giao_hang": {
#                 "duong": shipping.get("street", ""),
#                 "thanh_pho": shipping.get("city", ""),
#                 "ma_buu_dien": shipping.get("zip", "")
#             },
#             "mat_hang": items,
#             "tong_so_tien": tong_so_tien  # Tổng số tiền của đơn hàng
#         })
#     except Exception as e:
#         return jsonify({
#             "trang_thai": "loi",
#             "thong_bao": str(e)
#         }), 500


@app.route('/order', methods=['POST'])
@yeu_cau_xac_thuc_odoo
def tao_don_hang():
    """Tạo hoặc cập nhật đơn hàng trong Odoo"""
    try:
        du_lieu = request.get_json()
        ten_khach_hang = du_lieu.get("ten_khach_hang")
        so_dien_thoai = du_lieu.get("so_dien_thoai")
        dia_chi = du_lieu.get("dia_chi")
        product_id = du_lieu.get("id")
        so_luong = du_lieu.get("so_luong", 1)

        if not (ten_khach_hang and so_dien_thoai and product_id):
            return jsonify({
                "trang_thai": "loi",
                "thong_bao": "Thiếu thông tin bắt buộc"
            }), 400

        # Tìm hoặc tạo khách hàng
        khach_hang = goi_odoo_api(
            model="res.partner",
            method="search_read",
            args=[[["phone", "=", so_dien_thoai]]],
            kwargs={"fields": ["id"]}
        )

        if khach_hang:
            khach_hang_id = khach_hang[0]["id"]
        else:
            khach_hang_id = goi_odoo_api(
                model="res.partner",
                method="create",
                args=[{
                    "name": ten_khach_hang,
                    "phone": so_dien_thoai,
                    "street": dia_chi or ""
                }]
            )

        # Kiểm tra xem khách hàng đã có đơn hàng chưa
        don_hang = goi_odoo_api(
            model="sale.order",
            method="search_read",
            args=[[["partner_id", "=", khach_hang_id], ["state", "=", "draft"]]],
            kwargs={"fields": ["id"]}
        )

        if don_hang:
            order_id = don_hang[0]["id"]
        else:
            order_id = goi_odoo_api(
                model="sale.order",
                method="create",
                args=[{
                    "partner_id": khach_hang_id,
                    "partner_shipping_id": khach_hang_id
                }]
            )

        # Thêm sản phẩm vào đơn hàng
        goi_odoo_api(
            model="sale.order.line",
            method="create",
            args=[{
                "order_id": order_id,
                "product_id": product_id,
                "product_uom_qty": so_luong
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


@app.route('/order', methods=['GET'])
@yeu_cau_xac_thuc_odoo
def lay_thong_tin_don_hang():
    """Lấy thông tin đơn hàng gần nhất của khách hàng từ Odoo"""
    try:
        so_dien_thoai = request.args.get("so_dien_thoai")
        if not so_dien_thoai:
            return jsonify({"trang_thai": "loi", "thong_bao": "Thiếu số điện thoại"}), 400

        # Tìm khách hàng theo số điện thoại
        khach_hang = goi_odoo_api(
            model="res.partner",
            method="search_read",
            kwargs={
                "domain": [["phone", "=", so_dien_thoai]],
                "fields": ["id", "name", "street", "city", "state_id", "country_id"]
            }
        )
        if not khach_hang:
            return jsonify({"trang_thai": "loi", "thong_bao": "Không tìm thấy khách hàng"}), 404

        khach_hang = khach_hang[0]
        khach_hang_id = khach_hang["id"]

        # Ghép địa chỉ lại từ các trường
        dia_chi = f"{khach_hang.get('street', '')}, {khach_hang.get('city', '')}, {khach_hang.get('state_id', [''])[1] if khach_hang.get('state_id') else ''}, {khach_hang.get('country_id', [''])[1] if khach_hang.get('country_id') else ''}".strip(", ")

        # Tìm đơn hàng nháp hoặc đơn hàng gần nhất
        don_hang = goi_odoo_api(
            model="sale.order",
            method="search_read",
            kwargs={
                "domain": [["partner_id", "=", khach_hang_id]],
                "fields": ["id", "partner_id", "order_line", "amount_total", "state"],
                "order": "date_order desc",
                "limit": 1
            }
        )
        if not don_hang:
            return jsonify({"trang_thai": "loi", "thong_bao": "Không tìm thấy đơn hàng"}), 404

        don_hang = don_hang[0]
        order_id = don_hang["id"]

        # Lấy danh sách sản phẩm trong đơn hàng
        order_lines = goi_odoo_api(
            model="sale.order.line",
            method="search_read",
            kwargs={
                "domain": [["order_id", "=", order_id]],
                "fields": ["product_id", "product_uom_qty", "price_unit", "price_subtotal"]
            }
        )

        # Tính tổng tiền
        tong_tien = sum(line["price_subtotal"] for line in order_lines)

        items = [{
            "product_id": line["product_id"][0],
            "product_name": line["product_id"][1],
            "quantity": line["product_uom_qty"],
            "price": line["price_unit"],
            "subtotal": line["price_subtotal"]
        } for line in order_lines]

        return jsonify({
            "trang_thai": "thanh_cong",
            "ma_don_hang": order_id,
            "khach_hang": {
                "id": khach_hang_id,
                "ten": khach_hang["name"],
                "so_dien_thoai": so_dien_thoai,
                "dia_chi": dia_chi
            },
            "trang_thai_don_hang": don_hang["state"],
            "tong_tien": tong_tien,
            "mat_hang": items
        })
    except Exception as e:
        return jsonify({"trang_thai": "loi", "thong_bao": str(e)}), 500






if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Dùng PORT từ Render
    app.run(host='0.0.0.0', port=port)