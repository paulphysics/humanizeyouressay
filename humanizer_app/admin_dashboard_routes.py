from flask_admin import AdminIndexView
from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from sqlalchemy import func, case
from datetime import datetime, timedelta
from .models import ReferralWithdrawal
import pytz

from .models import db, User, Task, Transaction, Wallet, Conversation
from .auth_routes import auth_required

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')
NAIROBI_TZ = pytz.timezone('Africa/Nairobi')

def get_display_name(user):
    if user and user.name:
        return user.name.split(' ')[0]
    elif user and user.email:
        return user.email.split('@')[0]
    return "Admin"

def get_start_of_day_utc():
    now_nairobi = datetime.now(NAIROBI_TZ)
    start_of_day_nairobi = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day_nairobi.astimezone(pytz.utc)

def get_start_of_week_utc():
    now_nairobi = datetime.now(NAIROBI_TZ)
    start_of_day_nairobi = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week_nairobi = start_of_day_nairobi - timedelta(days=now_nairobi.weekday())
    return start_of_week_nairobi.astimezone(pytz.utc)

@admin_dashboard_bp.route('/dashboard')
@auth_required
def dashboard():
    user = User.query.get(session['user']['uid'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    # --- Time Boundaries ---
    start_of_day = get_start_of_day_utc()
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # --- Calculate All Statistics ---
    # ... (all your stat calculations are correct and stay here) ...
    total_users = db.session.query(func.count(User.id)).scalar()
    new_users_today = db.session.query(func.count(User.id)).filter(User.created_at >= start_of_day).scalar()
    active_users_week = db.session.query(func.count(func.distinct(Transaction.wallet_id))).filter(Transaction.created_at >= seven_days_ago).scalar()
    total_in_wallets = db.session.query(func.sum(Wallet.balance)).scalar() or 0
    revenue_today = abs(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.created_at >= start_of_day,
        Transaction.transaction_type.like('%fee%')
    ).scalar() or 0)
    total_revenue = abs(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.transaction_type.like('%fee%')
    ).scalar() or 0)
    topups_today = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.created_at >= start_of_day,
        Transaction.transaction_type == 'top-up'
    ).scalar() or 0
    avg_task_cost = abs(db.session.query(func.avg(Transaction.amount)).filter(
        Transaction.transaction_type.like('%fee%')
    ).scalar() or 0)
    tasks_stats = db.session.query(
        func.count(Task.id),
        func.sum(case((Task.status == 'humanization_complete', 1), else_=0)),
        func.sum(case((Task.status.like('%failed%'), 1), else_=0)),
        func.sum(case((Task.status.in_(['payment_pending', 'topup_pending', 'processing']), 1), else_=0))
    ).first()
    total_tasks, total_tasks_completed, total_tasks_failed, pending_tasks = tasks_stats
    tasks_today = db.session.query(func.count(Task.id)).filter(Task.created_at >= start_of_day).scalar()
    total_playground_chats = db.session.query(func.count(Conversation.id)).scalar()
    tasks_last_7_days = db.session.query(func.count(Task.id)).filter(Task.created_at >= seven_days_ago).scalar()
    users_with_zero_balance = Wallet.query.filter(Wallet.balance <= 0).count()


    # --- THIS IS THE FIX ---
    # Create a placeholder object that has all the attributes the base template needs.
    class MockAdminView:
        def __init__(self, name):
            self.name = name
            self.category = None
            self.admin = {'name': 'AI Humanizer Admin', 'endpoint': 'admin'} # The endpoint is the key
        
        def get_menu(self): return []
        def get_menu_links(self): return []

    # Prepare context for the template
    context = {
        'admin_view': MockAdminView('Dashboard Overview'),
        'get_url': url_for,
        'total_users': total_users,
        'new_users_today': new_users_today,
        'active_users_week': active_users_week,
        'total_in_wallets': total_in_wallets,
        'revenue_today': revenue_today,
        'total_revenue': total_revenue,
        'topups_today': topups_today,
        'avg_task_cost': avg_task_cost,
        'total_tasks': total_tasks or 0,
        'total_tasks_completed': total_tasks_completed or 0,
        'total_tasks_failed': total_tasks_failed or 0,
        'pending_tasks': pending_tasks or 0,
        'tasks_today': tasks_today,
        'total_playground_chats': total_playground_chats,
        'tasks_last_7_days': tasks_last_7_days,
        'users_with_zero_balance': users_with_zero_balance
    }

    return render_template('admin/dashboard.html', **context)


@admin_dashboard_bp.route("/approve_withdrawal/<int:withdrawal_id>", methods=["POST"])
@admin_required
def approve_withdrawal(withdrawal_id):
    from app.models import ReferralWithdrawal, Transaction
    withdrawal = ReferralWithdrawal.query.get_or_404(withdrawal_id)
    user = User.query.get_or_404(withdrawal.user_id)

    if withdrawal.status != "pending":
        flash("This withdrawal request has already been processed.", "warning")
        return redirect(url_for("admin.referral_withdrawals"))

    # Create withdrawal transaction (negative amount)
    txn = Transaction(
        wallet=user.wallet,
        amount=-withdrawal.amount,
        transaction_type="withdrawal",
        description="Approved referral commission withdrawal"
    )
    db.session.add(txn)

    # Deduct from wallet balance
    user.wallet.balance -= withdrawal.amount

    # Update withdrawal request status
    withdrawal.status = "approved"
    db.session.commit()

    flash(f"Withdrawal of KSh {withdrawal.amount:.2f} approved for {user.name}.", "success")
    return redirect(url_for("admin.referral_withdrawals"))
    

@admin_dashboard_bp.route('/reject-referral-withdrawal/<int:withdrawal_id>', methods=['POST'])
@auth_required
def reject_referral_withdrawal(withdrawal_id):
    admin_user = User.query.get(session['user']['uid'])
    if not admin_user or not admin_user.is_admin:
        return redirect(url_for('main.index'))

    withdrawal = ReferralWithdrawal.query.get_or_404(withdrawal_id)

    if withdrawal.status != "pending":
        flash("This withdrawal cannot be rejected as it is already processed.", "warning")
        return redirect(url_for("admin_dashboard.dashboard"))

    user = User.query.get_or_404(withdrawal.user_id)

    # ✅ Restore funds to ReferralLedger
    from .models import ReferralLedger
    restored_entry = ReferralLedger(user_id=user.id, amount=withdrawal.amount)
    db.session.add(restored_entry)

    # ✅ Update withdrawal status
    withdrawal.status = "rejected"
    withdrawal.processed_at = datetime.utcnow()

    db.session.commit()

    flash(f"Withdrawal of KSh {withdrawal.amount:.2f} rejected for {user.name}. Amount restored.", "success")
    return redirect(url_for("admin_dashboard.dashboard"))
