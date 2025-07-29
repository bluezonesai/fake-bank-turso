from flask import Blueprint, request, jsonify, session
from src.models.bank import db, User, Account, Transaction

bank_bp = Blueprint('bank', __name__)

@bank_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    pin = data.get('pin')
    account_type = data.get('account_type', 'personal')
    
    if not username or not pin:
        return jsonify({'error': 'Username and PIN are required'}), 400
    
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create new user
    user = User(username=username, pin=pin)
    db.session.add(user)
    db.session.flush()  # Get the user ID
    
    # Create account for the user
    account = Account(user_id=user.id, account_type=account_type)
    db.session.add(account)
    db.session.commit()
    
    return jsonify({
        'message': 'User and account created successfully',
        'user': user.to_dict(),
        'account': account.to_dict()
    }), 201

@bank_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    pin = data.get('pin')
    
    if not username or not pin:
        return jsonify({'error': 'Username and PIN are required'}), 400
    
    user = User.query.filter_by(username=username, pin=pin).first()
    if not user:
        return jsonify({'error': 'Invalid username or PIN'}), 401
    
    # Store user in session
    session['user_id'] = user.id
    
    # Get user's accounts
    accounts = Account.query.filter_by(user_id=user.id).all()
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'accounts': [account.to_dict() for account in accounts]
    }), 200

@bank_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@bank_bp.route('/accounts', methods=['GET'])
def get_accounts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    accounts = Account.query.filter_by(user_id=session['user_id']).all()
    return jsonify([account.to_dict() for account in accounts]), 200

@bank_bp.route('/accounts/<int:account_id>/transactions', methods=['GET'])
def get_transactions(account_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Verify account belongs to user
    account = Account.query.filter_by(id=account_id, user_id=session['user_id']).first()
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Get all transactions for this account
    transactions = Transaction.query.filter(
        (Transaction.from_account_id == account_id) | 
        (Transaction.to_account_id == account_id)
    ).order_by(Transaction.created_at.desc()).all()
    
    return jsonify([transaction.to_dict() for transaction in transactions]), 200

@bank_bp.route('/transfer', methods=['POST'])
def transfer_money():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    from_account_number = data.get('from_account_number')
    to_account_number = data.get('to_account_number')
    amount = data.get('amount')
    description = data.get('description', '')
    
    if not from_account_number or not to_account_number or not amount:
        return jsonify({'error': 'From account, to account, and amount are required'}), 400
    
    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid amount'}), 400
    
    # Get accounts
    from_account = Account.query.filter_by(account_number=from_account_number, user_id=session['user_id']).first()
    to_account = Account.query.filter_by(account_number=to_account_number).first()
    
    if not from_account:
        return jsonify({'error': 'Source account not found or not owned by you'}), 404
    
    if not to_account:
        return jsonify({'error': 'Destination account not found'}), 404
    
    if from_account.balance < amount:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    # Perform transfer
    from_account.balance -= amount
    to_account.balance += amount
    
    # Create transaction record
    transaction = Transaction(
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        amount=amount,
        description=description,
        transaction_type='transfer'
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Transfer successful',
        'transaction': transaction.to_dict(),
        'new_balance': from_account.balance
    }), 200

@bank_bp.route('/charge', methods=['POST'])
def charge_customer():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    business_account_number = data.get('business_account_number')
    customer_username = data.get('customer_username')
    customer_pin = data.get('customer_pin')
    amount = data.get('amount')
    reason = data.get('reason', '')
    description = data.get('description', '')
    
    if not all([business_account_number, customer_username, customer_pin, amount, reason]):
        return jsonify({'error': 'All fields including reason are required'}), 400
    
    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid amount'}), 400
    
    # Verify business account belongs to current user
    business_account = Account.query.filter_by(
        account_number=business_account_number, 
        user_id=session['user_id'],
        account_type='business'
    ).first()
    
    if not business_account:
        return jsonify({'error': 'Business account not found or not owned by you'}), 404
    
    # Verify customer credentials
    customer = User.query.filter_by(username=customer_username, pin=customer_pin).first()
    if not customer:
        return jsonify({'error': 'Invalid customer credentials'}), 401
    
    # Get customer's account (assuming first account)
    customer_account = Account.query.filter_by(user_id=customer.id).first()
    if not customer_account:
        return jsonify({'error': 'Customer account not found'}), 404
    
    if customer_account.balance < amount:
        return jsonify({'error': 'Customer has insufficient funds'}), 400
    
    # Perform charge
    customer_account.balance -= amount
    business_account.balance += amount
    
    # Create transaction record with reason in description
    full_description = f"INVOICE: {reason}"
    if description:
        full_description += f" - {description}"
    
    transaction = Transaction(
        from_account_id=customer_account.id,
        to_account_id=business_account.id,
        amount=amount,
        description=full_description,
        transaction_type='charge'
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Charge successful',
        'transaction': transaction.to_dict(),
        'business_new_balance': business_account.balance,
        'invoice': {
            'reason': reason,
            'amount': amount,
            'customer': customer_username,
            'business_account': business_account_number
        }
    }), 200

@bank_bp.route('/search_account', methods=['POST'])
def search_account():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    account_number = data.get('account_number')
    
    if not account_number:
        return jsonify({'error': 'Account number is required'}), 400
    
    account = Account.query.filter_by(account_number=account_number).first()
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Return limited info for privacy
    return jsonify({
        'account_number': account.account_number,
        'account_type': account.account_type,
        'owner_username': account.owner.username
    }), 200

