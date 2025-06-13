from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234567@localhost:5432/profile'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)



class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key = True)
    fname = db.Column(db.String(30))
    lname = db.Column(db.String(30))
    email = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(100),nullable=False)

    def __repr__(self):
        return f"User {self.fname}, {self.lname},{self.email}"


@app.route("/register", methods = ["Post"])
def register():
    data = request.get_json()
    fname = data.get("fname")
    lname = data.get("lname")
    email = data.get("email")
    password = data.get("password")

    if  not email or not password:
        return jsonify({"message": "email and password are required fields."}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"message": "User already exists"}), 409
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    new_user = User(
    fname = fname,
    lname = lname,
    email = email,
    password = hashed_password
    )
    db.session.add(new_user)
    db.session.commit()

    

    return ({"msg":"registration done!"})


@app.route("/login", methods =["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {"error": "email and password are required"}, 400
    
    user = User.query.filter_by(email= email).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return {"error": "invalid credentials"}, 401
    
    access_token = create_access_token(identity=user.id)
    return jsonify({'message': 'Login Success', 'access_token': access_token}), 200




@app.route("/update", methods = ["PUT"])
@jwt_required()
def update_user():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    new_fname = data.get("fname")
    new_lname = data.get("lname")

    user = User.query.filter_by(email=current_user_id)

    if not user:
        return jsonify({"msg":"user not found"}), 400
    
    if new_fname:
        user.fname = new_fname

    if new_lname:
        user.lname = new_lname

    db.session.commit()
    return jsonify({"msg": "profuile updted successfully"})

@app.route("/delete" , methods = ["DELETE"])
@jwt_required()
def delete_user():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(email=current_user_id)

    if not user:
        return jsonify({"eror":"user not found"}), 404
    
    db.session.delete(user)
    db.session.commit()

    return jsonify({"msg": "user profile deleted succesfully"})

    



# @app.route("/logout", methods= ["POST"])
# def logout():
#     return "logout done"

class Notes(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable = False)
    content = db.Column(db.Text)
    tags = db.Column(db.String(200))
    color = db.Column(db.String(30), default="#ffffff")
    pinned = db.Column(db.Boolean, default = False)

    def __repr__(self):
        return f"User {self.id}, {self.title}"




@app.route("/create-notes", methods=["POST"])
def create_note():
    data = request.get_json()
    note = Notes(
        title=data["title"],
        content=data["content"],
        tags=data["tags"],
        color=data["color"],
        pinned=data["pinned"],

    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"msg":"note created"})



@app.route("/get-notes", methods=["GET"])
def get_note():
    notes = Notes.query.all()
    result = []
    for n in notes:
        result.append(
            
            {"id": n.id,
        "title": n.title,
        "content": n.content,
        "tags": n.tags,
        "pinned": n.pinned,
        "color": n.color
        }

        )
    return jsonify(result),200




@app.route("/notes/<int:note_id>", methods=["PUT"])
def update_note(note_id):
    note = Notes.query.get_or_404(note_id)
    data = request.json
    note.title = data.get('title', note.title)
    note.content = data.get('content', note.content)
    note.tags = data.get('tags', note.tags)
    note.pinned = data.get('pinned', note.pinned)
    note.color = data.get('color', note.color)

    db.session.commit()
    return jsonify({"msg":"updated"})




@app.route("/delete-note/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    note = Notes.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return jsonify({"msg":"note deleted"})


if __name__ == '__main__':
    app.run(debug=True)