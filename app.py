from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # مفتاح سري لتأمين الجلسات

# إعداد الاتصال بـ SQL Server
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://@localhost/foody_db?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# نموذج المستخدم
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'chef' أو 'customer'

class Order(db.Model):
    __tablename__ = 'Orders'
    Order_ID = db.Column(db.Integer, primary_key=True)
    Customer_Username = db.Column(db.String(80), nullable=False)
    Item_ID = db.Column(db.Integer, nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    Total_Price = db.Column(db.Float, nullable=False)
    Status = db.Column(db.String(20), default='Pending')


# إنشاء الجداول إذا لم تكن موجودة
with app.app_context():
    db.create_all()

# صفحة تسجيل الدخول
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # تحقق من صحة بيانات تسجيل الدخول
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('main'))

        return "اسم المستخدم أو كلمة المرور غير صحيحة."

    return render_template('login.html')

# الصفحة الرئيسية
@app.route('/main')
def main():
    # استعلام لإحضار 5 أطباق مميزة فقط
    query = text("""
        SELECT TOP 5 Menu_Item_ID, Item_Name, info, Price, img_path 
        FROM [dbo].[Mun]
        ORDER BY NEWID()  -- اختيار عشوائي
    """)
    featured_items = db.session.execute(query).fetchall()

    # تمرير البيانات إلى القالب
    return render_template('main.html', role=session.get('role'), featured_items=featured_items)


# صفحة المطبخ (للطباخ فقط)
@app.route('/kitchen')
def kitchen():
    if 'role' in session and session['role'] == 'chef':
        # استعلام لجلب بيانات المخزن
        query = text("SELECT Item_ID, Item_Name, Quantity, Category FROM [dbo].[Kitchen]")
        inventory_items = db.session.execute(query).fetchall()

        # تمرير البيانات إلى القالب
        return render_template('kitchen.html', role=session['role'], inventory_items=inventory_items)
    return redirect(url_for('main'))


# صفحة قائمة الطعام
@app.route('/mun')
def mun():
    # جلب بيانات المنيو من قاعدة البيانات باستخدام text()
    query = text("SELECT Menu_Item_ID, Item_Name, info, Price,img_path FROM [dbo].[Mun]")
    menu_items = db.session.execute(query).fetchall()

    # تمرير البيانات إلى القالب
    return render_template('mun.html', role=session.get('role'), menu_items=menu_items)


# صفحة تسجيل الخروج
@app.route('/logout')
def logout():
    session.clear()  # مسح الجلسة
    return redirect(url_for('login'))


@app.route('/manage_orders')
def manage_orders():
    if 'role' in session and session['role'] == 'chef':
        # استعلام لجلب جميع الطلبات مع اسم المنتج بناءً على Item_ID
        query = text("""
            SELECT o.Order_ID, o.Customer_Username, o.Item_ID, o.Quantity, o.Total_Price, o.Status, m.Item_Name
            FROM Orders o
            JOIN Mun m ON o.Item_ID = m.Menu_Item_ID
        """)
        orders = db.session.execute(query).fetchall()

        # إذا كانت هناك طلبات، قم بتمريرها إلى القالب
        if orders:
            return render_template('manage_orders.html', orders=orders)
        else:
            return render_template('manage_orders.html', message="No orders available")  # رسالة إذا لم توجد طلبات
    return redirect(url_for('login'))  # إعادة التوجيه إذا لم يكن الطباخ مسجلاً الدخول



@app.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if 'role' in session and session['role'] == 'chef':
        order = Order.query.get(order_id)
        order.Status = request.form['status']
        db.session.commit()
        return redirect(url_for('manage_orders'))
    return redirect(url_for('login'))


@app.route('/order', methods=['POST'])
def place_order():
    if 'username' in session:
        customer_username = session['username']
        item_id = request.form['item_id']
        quantity = int(request.form['quantity'])
        
        # جلب سعر المنتج
        query = text("SELECT Price FROM Mun WHERE Menu_Item_ID = :item_id")
        result = db.session.execute(query, {'item_id': item_id}).fetchone()
        price = result[0]

        # حساب السعر الإجمالي
        total_price = price * quantity

        # إنشاء الطلب
        new_order = Order(
            Customer_Username=customer_username,
            Item_ID=item_id,
            Quantity=quantity,
            Total_Price=total_price
        )
        db.session.add(new_order)
        db.session.commit()
        return redirect(url_for('main'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # التحقق إذا كان المستخدم موجود بالفعل
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "اسم المستخدم موجود بالفعل. الرجاء اختيار اسم آخر."

        # إنشاء حساب جديد
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/fridge')
def fridge():
    if 'role' in session and session['role'] == 'chef':
        # استعلام لجلب بيانات الثلاجة
        query = text("SELECT Item_ID, Item_Name, Quantity, Expiry_Date FROM [dbo].[Fridgee]")
        fridge_items = db.session.execute(query).fetchall()

        return render_template('fridge.html', role=session['role'], fridge_items=fridge_items)
    return redirect(url_for('main'))




if __name__ == '__main__':
    app.run(debug=True)
