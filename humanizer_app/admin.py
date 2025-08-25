# humanizer_app/admin.py
from flask import session, redirect, url_for, request, flash, Response
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from flask_admin.contrib.sqla.filters import BooleanEqualFilter, DateBetweenFilter, FilterInList
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange
from markupsafe import Markup
import pytz
from sqlalchemy import func, or_
from datetime import date, datetime, timedelta
import csv
import io

from .models import User, Task, Wallet, Transaction, Expense
from .extensions import db

NAIROBI_TZ = pytz.timezone('Africa/Nairobi')

# --- HELPER FORMATTERS ---
def _mode_formatter(view, context, model, name):
    if isinstance(model.diff_data, dict):
        mode = model.diff_data.get('humanizer_mode', 'N/A')
        return Markup(mode.replace('_', ' ').title())
    return 'N/A'

def _date_formatter(view, context, model, name):
    date_val = getattr(model, name)
    if date_val:
        return date_val.replace(tzinfo=pytz.utc).astimezone(NAIROBI_TZ).strftime('%Y-%m-%d %H:%M')
    return 'N/A'

def _input_text_formatter(view, context, model, name):
    if not model.input_text:
        return ''
    if len(model.input_text) > 50:
        return Markup(f'{model.input_text[:50]}...')
    return model.input_text

# --- ADMIN DASHBOARD AND INDEX VIEW ---
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        return redirect(url_for('.dashboard'))

    @expose('/dashboard')
    def dashboard(self):
        if 'user' not in session: return redirect(url_for('auth.login'))
        current_user = User.query.get(session['user']['uid'])
        if not current_user or not current_user.is_admin: return redirect(url_for('main.index'))

        start_date_str = request.args.get('start_date', (date.today() - timedelta(days=6)).strftime('%Y-%m-%d'))
        end_date_str = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('.dashboard'))

        if end_date < start_date:
            flash('End date cannot be before start date.', 'danger')
            end_date = start_date

        # Metrics Calculations
        total_revenue_in_range = abs(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type.in_(['humanize_fee', 'playground_input_fee', 'playground_output_fee']),
            Transaction.created_at.between(start_date, end_date + timedelta(days=1))
        ).scalar() or 0)

        completed_tasks_in_range = Task.query.filter(
            Task.status == 'humanization_complete',
            Task.created_at.between(start_date, end_date + timedelta(days=1))
        ).count()
        
        # Chart Data
        daily_revenue = db.session.query(func.date(Transaction.created_at), func.sum(Transaction.amount)).filter(
            Transaction.transaction_type.in_(['humanize_fee', 'playground_input_fee', 'playground_output_fee']),
            Transaction.created_at.between(start_date, end_date + timedelta(days=1))
        ).group_by(func.date(Transaction.created_at)).order_by(func.date(Transaction.created_at)).all()

        daily_tasks = db.session.query(func.date(Task.created_at), func.count(Task.id)).filter(
            Task.created_at.between(start_date, end_date + timedelta(days=1))
        ).group_by(func.date(Task.created_at)).order_by(func.date(Task.created_at)).all()
        
        chart_labels = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_date - start_date).days + 1)]
        revenue_data = [0] * len(chart_labels)
        tasks_data = [0] * len(chart_labels)

        for day, total in daily_revenue:
            if day and 0 <= (day - start_date).days < len(revenue_data):
                revenue_data[(day - start_date).days] = abs(total)
        
        for day, count in daily_tasks:
            if day and 0 <= (day - start_date).days < len(tasks_data):
                tasks_data[(day - start_date).days] = count

        return self.render('admin/reports.html',
                           start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d'),
                           total_revenue_in_range=total_revenue_in_range,
                           completed_tasks_in_range=completed_tasks_in_range,
                           chart_labels=chart_labels, revenue_data=revenue_data, tasks_data=tasks_data)

    @expose('/export-corpus')
    def export_corpus(self):
        # +++ START OF MODIFIED CODE +++
        # Corrected the filter to use .as_string() for JSONB queries
        tasks = Task.query.filter(
            Task.status == 'humanization_complete',
            Task.diff_data['humanizer_mode'].as_string() != 'document_formatter'
        ).all()
        # +++ END OF MODIFIED CODE +++
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Transaction ID', 'Input Text', 'Output Text'])
        for task in tasks:
            writer.writerow([task.external_reference, task.input_text, task.humanized_output])
        output.seek(0)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=humanizer_corpus.csv"})

# --- BASE AUTHENTICATED VIEW ---
class AuthenticatedModelView(ModelView):
    def is_accessible(self):
        if 'user' in session:
            user = User.query.get(session['user']['uid'])
            return user and user.is_admin
        return False
    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('main.index'))

# --- OTHER MODEL VIEWS ---
class TaskAdminView(AuthenticatedModelView):
    can_create = False; can_edit = False; can_delete = True
    column_list = ('external_reference', 'user.email', 'status', 'input_text', 'amount_charged', 'diff_data', 'created_at')
    column_labels = {'external_reference': 'Ref ID', 'user.email': 'User', 'input_text': 'Input', 'diff_data': 'Mode', 'created_at': 'Date (EAT)', 'amount_charged': 'Cost (KSh)'}
    column_formatters = {'diff_data': _mode_formatter, 'created_at': _date_formatter, 'input_text': _input_text_formatter}
    column_searchable_list = ['external_reference', 'user.email', 'input_text']
    column_filters = ['status', 'created_at']
    form_ajax_refs = {'user': {'fields': ['email'], 'page_size': 10}}
    form_columns = ['user', 'input_text', 'phone_number', 'amount_charged', 'status', 'external_reference']

class TransferForm(FlaskForm):
    amount = FloatField('Amount (KSh)', validators=[DataRequired(), NumberRange(min=0.01)])
    recipient_id = HiddenField('Recipient ID')
    submit = SubmitField('Transfer Funds')

class UserAdminView(AuthenticatedModelView):
    column_list = ['email', 'is_admin', 'wallet.balance']
    column_labels = {'wallet.balance': 'Wallet Balance (KSh)'}
    column_searchable_list = ['email']
    column_filters = [BooleanEqualFilter(User.is_admin, 'Is Admin')]
    can_create = False; can_edit = True
    form_columns = ['is_admin']

    @action('transfer_funds', 'Transfer Funds', 'Are you sure?')
    def action_transfer_funds(self, ids):
        if len(ids) > 1:
            flash('Please select only one user.', 'error')
            return
        return redirect(url_for('.transfer_funds_view', user_id=ids[0]))

    @expose('/transfer-funds/', methods=['GET', 'POST'])
    def transfer_funds_view(self):
        form = TransferForm()
        user_id = request.args.get('user_id')
        recipient = User.query.get(user_id)
        if not recipient:
            flash('Recipient user not found.', 'error')
            return redirect(url_for('.index_view'))
    
        if form.validate_on_submit():
            amount = form.amount.data
            
            # --- Start of New Logic ---
            try:
                if not recipient.wallet:
                    flash(f'Error: User {recipient.email} does not have a wallet.', 'error')
                    return redirect(url_for('.index_view'))
    
                # 1. Update the user's wallet balance
                recipient.wallet.balance += amount
    
                # 2. Create a new transaction record for the credit
                admin_credit_transaction = Transaction(
                    wallet_id=recipient.wallet.id,
                    amount=amount,
                    transaction_type='admin_credit',  # New transaction type
                    description=f'Admin credit by {session["user"]["email"]}.',
                    is_reversed=False
                )
                db.session.add(admin_credit_transaction)
    
                # 3. Commit both changes to the database at once
                db.session.commit()
                
                flash(f'Successfully transferred KSh {amount:.2f} to {recipient.email}.', 'success')
    
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred: {e}', 'error')
            # --- End of New Logic ---
                
            return redirect(url_for('.index_view'))
    
        admin_balance_display = "Infinite"
    
        return self.render('admin/transfer_funds.html', 
                           form=form, 
                           recipient=recipient, 
                           admin_balance=admin_balance_display)

class TransactionAdminView(AuthenticatedModelView):
    column_list = ['wallet.user.email', 'amount', 'transaction_type', 'is_reversed', 'created_at', 'description']
    column_formatters = { 'created_at': _date_formatter }
    column_labels = {'wallet.user.email': 'User', 'is_reversed': 'Reversed?', 'created_at': 'Date (EAT)'}
    column_filters = [
        FilterInList(Transaction.transaction_type, 'Type', options=[('top-up', 'Top-Up'), ('humanize_fee', 'Humanize Fee')]),
        BooleanEqualFilter(Transaction.is_reversed, 'Reversed?'), DateBetweenFilter(Transaction.created_at, 'Date')
    ]
    can_create = False; can_edit = False; can_delete = False
    column_searchable_list = ['description']

    def get_query(self):
        return super().get_query().join(Wallet).join(User)

    def get_count_query(self):
        return super().get_count_query().join(Wallet).join(User)

    @action('reverse', 'Reverse Transaction', 'Are you sure?')
    def action_reverse(self, ids):
        try:
            transactions = Transaction.query.filter(Transaction.id.in_(ids)).all()
            for trans in transactions:
                if not trans.is_reversed:
                    trans.wallet.balance -= trans.amount
                    trans.is_reversed = True
            db.session.commit()
            flash(f'Successfully reversed {len(transactions)} transaction(s).', 'success')
        except Exception as ex:
            db.session.rollback()
            flash(f'Failed to reverse. Error: {ex}', 'error')

class ExpenseAdminView(AuthenticatedModelView):
    column_list = ['service_name', 'amount', 'expense_date', 'description']
    column_labels = {'service_name': 'Service', 'amount': 'Amount (KSh)', 'expense_date': 'Date'}
    form_columns = ['service_name', 'amount', 'expense_date', 'description']
    column_searchable_list = ['service_name', 'description']
    column_filters = ['service_name', 'expense_date']

# --- INITIALIZE ADMIN ---
def init_admin(app, db):
    admin = Admin(app, name='AI Humanizer Admin', template_mode='bootstrap4', index_view=MyAdminIndexView(name='Dashboard', url='/admin'))
    admin.add_view(TaskAdminView(Task, db.session, name='All Tasks', endpoint='all-tasks'))
    admin.add_view(UserAdminView(User, db.session))
    admin.add_view(TransactionAdminView(Transaction, db.session))
    admin.add_view(ExpenseAdminView(Expense, db.session, name='Expenses'))
