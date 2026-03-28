from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import os

app = Flask(__name__)

# --- DATABASE SETUP ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'mart.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Unique name
    price = db.Column(db.Float, nullable=False)
    total_pieces = db.Column(db.Integer, default=0)
    pcs_per_case = db.Column(db.Integer, default=1)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100))
    qty_sold = db.Column(db.Integer)
    total_bill = db.Column(db.Float)
    payment_method = db.Column(db.String(50))

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_products')
def get_products():
    # BUG FIX 1: Only show products where stock is GREATER THAN 0
    products = Product.query.filter(Product.total_pieces > 0).order_by(Product.id.desc()).all()
    return jsonify([{"id":p.id, "name":p.name, "price":p.price, "total_pieces":p.total_pieces, "ppc":p.pcs_per_case} for p in products])

@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.json
    try:
        new_stock = int(data['cases']) * int(data['ppc'])
        
        # BUG FIX 2: Check if product name already exists
        existing_p = Product.query.filter_by(name=data['name']).first()
        
        if existing_p:
            # Update existing product stock instead of creating new one
            existing_p.total_pieces += new_stock
            existing_p.price = float(data['price']) # Update price in case it changed
            existing_p.pcs_per_case = int(data['ppc'])
        else:
            # Create brand new product
            new_p = Product(
                name=data['name'], 
                price=float(data['price']), 
                total_pieces=new_stock, 
                pcs_per_case=int(data['ppc'])
            )
            db.session.add(new_p)
            
        db.session.commit()
        return jsonify({"message": "Inventory Synchronized"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process_payment', methods=['POST'])
def process_payment():
    try:
        data = request.json
        p = Product.query.get(data['id'])
        qty = int(data['qty'])
        actual_pcs = qty * p.pcs_per_case if data['mode'] == 'case' else qty

        if p.total_pieces < actual_pcs:
            return jsonify({"error": "Insufficient Stock!"}), 400

        p.total_pieces -= actual_pcs
        bill = actual_pcs * p.price
        
        new_sale = Sale(product_name=p.name, qty_sold=actual_pcs, total_bill=bill, payment_method=data['payment_type'])
        db.session.add(new_sale)
        db.session.commit()
        return jsonify({"bill": round(bill, 2), "method": data['payment_type']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_stats')
def get_stats():
    revenue = db.session.query(func.sum(Sale.total_bill)).scalar() or 0
    items = db.session.query(func.sum(Sale.qty_sold)).scalar() or 0
    top_item = db.session.query(Sale.product_name, func.sum(Sale.qty_sold)).group_by(Sale.product_name).order_by(func.sum(Sale.qty_sold).desc()).first()
    return jsonify({"revenue": f"{revenue:,.2f}", "sold": int(items), "most_sold": top_item[0] if top_item else "None"})

@app.route('/delete_product/<int:id>', methods=['DELETE'])
def delete_product(id):
    p = Product.query.get(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Deleted"})

if __name__ == '__main__':
    app.run(debug=True)