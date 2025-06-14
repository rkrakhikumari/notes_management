import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize app and config
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# Association Table for Many-to-Many Relationship
note_tags = db.Table(
    'note_tags',
    db.Column('note_id', db.Integer, db.ForeignKey('notes.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'))
)

# ============================= MODELS ============================= #

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    fname = db.Column(db.String(30))
    lname = db.Column(db.String(30))
    email = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"User {self.fname}, {self.lname}, {self.email}"


class Tag(db.Model):
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

    def __repr__(self):
        return f"<Tag {self.name}>"


class Notes(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    color = db.Column(db.String(30), default="#ffffff")
    pinned = db.Column(db.Boolean, default=False)
    trashed = db.Column(db.Boolean, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship("User", backref="notes")

    tags = db.relationship("Tag", secondary=note_tags, backref=db.backref("notes", lazy="dynamic"))

    def __repr__(self):
        return f"<Note id={self.id} title={self.title}>"


# ============================= AUTH ROUTES ============================= #

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    fname = data.get("fname")
    lname = data.get("lname")
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "email and password are required fields."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"}), 409

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    new_user = User(fname=fname, lname=lname, email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "registration done!"})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {"error": "email and password are required"}, 400

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return {"error": "invalid credentials"}, 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({'message': 'Login Success', 'access_token': access_token}), 200


@app.route("/update", methods=["PUT"])
@jwt_required()
def update_user():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"msg": "user not found"}), 400

    user.fname = data.get("fname", user.fname)
    user.lname = data.get("lname", user.lname)

    db.session.commit()
    return jsonify({"msg": "profile updated successfully"})


@app.route("/delete", methods=["DELETE"])
@jwt_required()
def delete_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "user not found"}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({"msg": "user profile deleted successfully"})


# ============================= NOTES ROUTES ============================= #

@app.route("/create-notes", methods=["POST"])
@jwt_required()
def create_note():
    data = request.get_json()
    user_id = get_jwt_identity()
    tag_names = data.get("tags", [])
    tags = []

    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)

    note = Notes(
        title=data.get("title"),
        content=data.get("content"),
        tags=tags,
        color=data.get("color"),
        pinned=data.get("pinned", False),
        trashed=data.get("trashed", False),
        user_id=user_id
    )

    db.session.add(note)
    db.session.commit()
    return jsonify({"msg": "note created"}), 201


@app.route("/get-notes", methods=["GET"])
@jwt_required()
def get_note():
    current_user_id = get_jwt_identity()
    notes = Notes.query.filter_by(user_id=current_user_id, trashed=False).all()

    result = [{
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "tags": [t.name for t in n.tags],
        "pinned": n.pinned,
        "color": n.color
    } for n in notes]

    return jsonify(result), 200


@app.route("/filter-notes", methods=["GET"])
@jwt_required()
def filter_notes_by_tags():
    current_user_id = get_jwt_identity()
    tag_names = request.args.getlist("tag")

    notes = Notes.query.join(Notes.tags).filter(
        Notes.user_id == current_user_id,
        Tag.name.in_(tag_names),
        Notes.trashed == False
    ).all()

    result = [{
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "tags": [t.name for t in n.tags],
        "pinned": n.pinned,
        "color": n.color
    } for n in notes]

    return jsonify(result), 200


@app.route("/trash-note/<int:note_id>", methods=["PUT"])
@jwt_required()
def trash_note(note_id):
    current_user_id = get_jwt_identity()
    note = Notes.query.filter_by(id=note_id, user_id=current_user_id).first()

    if not note:
        return jsonify({"error": "note not found"}), 404

    note.trashed = True
    db.session.commit()
    return jsonify({"msg": "note moved to trash"}), 200


@app.route("/get-trashed-note", methods=["GET"])
@jwt_required()
def get_trashed_note():
    current_user_id = get_jwt_identity()
    notes = Notes.query.filter_by(user_id=current_user_id, trashed=True).all()

    result = [{
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "tags": [t.name for t in n.tags],
        "pinned": n.pinned,
        "color": n.color
    } for n in notes]

    return jsonify(result), 200


@app.route("/notes/<int:note_id>", methods=["PUT"])
@jwt_required()
def update_note(note_id):
    current_user_id = get_jwt_identity()
    note = Notes.query.filter_by(id=note_id, user_id=current_user_id).first()

    if not note:
        return jsonify({"error": "Note not found"}), 404

    data = request.get_json()
    note.title = data.get('title', note.title)
    note.content = data.get('content', note.content)
    note.pinned = data.get('pinned', note.pinned)
    note.color = data.get('color', note.color)

    tag_names = data.get('tags', [])
    if tag_names:
        new_tags = []
        for name in tag_names:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            new_tags.append(tag)
        note.tags = new_tags

    db.session.commit()
    return jsonify({"msg": "note updated"}), 200


@app.route("/delete-note/<int:note_id>", methods=["DELETE"])
@jwt_required()
def delete_note(note_id):
    current_user_id = get_jwt_identity()
    note = Notes.query.filter_by(id=note_id, user_id=current_user_id).first()

    if not note:
        return jsonify({"error": "note not found"}), 404

    db.session.delete(note)
    db.session.commit()
    return jsonify({"msg": "note deleted"}), 200


# ============================= MAIN ============================= #

if __name__ == '__main__':
    app.run(debug=True)
