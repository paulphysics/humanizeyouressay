"""
This module defines the database models for the application.
"""
from datetime import datetime
from .extensions import db
from sqlalchemy.sql import func

class User(db.Model):
    """
    Represents a user in the database.
    """
    __tablename__ = 'user'
    id = db.Column(db.String(128), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # --- REFERRAL SYSTEM ADDITIONS START ---
    referral_code = db.Column(db.String(20), unique=True, nullable=True)
    referred_by = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=True)
    upline = db.Column(db.String, nullable=True)  # Stores comma-separated list of referrer IDs for MLM
    # --- REFERRAL SYSTEM ADDITIONS END ---
    
    tasks = db.relationship('Task', back_populates='user', lazy=True)
    wallet = db.relationship('Wallet', back_populates='user', uselist=False, cascade="all, delete-orphan")
    
    # --- NEW: Relationship to Conversation ---
    conversations = db.relationship('Conversation', back_populates='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} email='{self.email}'>"

class Task(db.Model):
    """
    Represents a humanization task in the database.
    """
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key=True)
    external_reference = db.Column(db.String(120), unique=True, nullable=False, index=True)
    input_text = db.Column(db.Text, nullable=False)
    
    # --- THIS IS THE CHANGE ---
    phone_number = db.Column(db.String(20), nullable=True)
    amount_charged = db.Column(db.Float, nullable=True)
    # --------------------------
    
    status = db.Column(db.String(50), nullable=False, default='payment_initiated')
    humanized_output = db.Column(db.Text, nullable=True)
    output_word_count = db.Column(db.Integer, nullable=True)
    diff_data = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=True)

    # ✅ FIX: Added the missing output_format column
    output_format = db.Column(db.String(50), nullable=True)

    user = db.relationship('User', back_populates='tasks')

    def __repr__(self):
        return f"<Task id={self.id} ref='{self.external_reference}' status='{self.status}'>"

class Wallet(db.Model):
    """
    Represents a user's wallet with a balance.
    """
    __tablename__ = 'wallet'
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False, unique=True)
    user = db.relationship('User', back_populates='wallet')
    transactions = db.relationship('Transaction', backref='wallet', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Wallet id={self.id} user_id='{self.user_id}' balance={self.balance}>"

class Transaction(db.Model):
    """
    Represents a single transaction (top-up or deduction) in a wallet.
    """
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    is_reversed = db.Column(db.Boolean, nullable=True, server_default='f')

    def __repr__(self):
        return f"<Transaction id={self.id} type='{self.transaction_type}' amount={self.amount}>"

class Conversation(db.Model):
    """
    Represents a single chat conversation.
    """
    __tablename__ = 'conversation'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False, default="New Conversation")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- NEW: Store the chosen model for this conversation ---
    model_key = db.Column(db.String(50), nullable=False)
    
    # --- UPDATED: Relationships with back_populates ---
    user = db.relationship('User', back_populates='conversations')
    messages = db.relationship('ChatMessage', back_populates='conversation', lazy=True, cascade="all, delete-orphan")

class ChatMessage(db.Model):
    """
    Represents a single message within a conversation.
    """
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) # e.g., 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- NEW: Relationship back to Conversation ---
    conversation = db.relationship('Conversation', back_populates='messages')

class Expense(db.Model):
    """
    Represents a business expense.
    """
    __tablename__ = 'expense'
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Expense id={self.id} service='{self.service_name}' amount={self.amount}>"
