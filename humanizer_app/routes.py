# humanizer_app/routes.py
import os
import PyPDF2
import docx
import io
import uuid
import re
import json
import threading
import logging
from datetime import datetime, timedelta
from flask import (Blueprint, request, render_template, jsonify, send_file,
                 redirect, url_for, flash, current_app, session, abort)
from werkzeug.exceptions import RequestEntityTooLarge 
from sqlalchemy import desc, or_
import pytz
import difflib

from .extensions import db
from .models import Task, User, Wallet, Transaction, Conversation, ChatMessage
from .payment_service import (initiate_payhero_payment, WORDS_PER_UNIT,
                              PRICE_PER_UNIT, ESSAY_PRICE_PER_UNIT)
from .document_formatter import create_formatted_document
from .humanizer_service.utils import count_words
from .humanizer_service.exceptions import AllModelsFailedError
from .auth_routes import auth_required
from .humanizer_service.api_clients import call_single_openai_model
from .humanizer_service.api_clients import openai_client
from .tasks import process_playground_chat_task, process_humanization_task

main_bp = Blueprint('main', __name__)
KENYAN_PHONE_REGEX = re.compile(r"^(0|\+254)7[0-9]{8}$")
logger = logging.getLogger(__name__)

WHATSAPP_NUMBER = "254712345678"
MAX_WORDS = 1925
NAIROBI_TZ = pytz.timezone('Africa/Nairobi')

def sanitize_filename(filename):
    if not filename:
        return "document"
    filename = filename.strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', filename)

def get_display_name(user):
    """Gets the user's first name, with a fallback to their email."""
    if user and user.name:
        return user.name.split(' ')[0]
    elif user and user.email:
        return user.email.split('@')[0]
    return "User"

@main_bp.route("/")
def index():
    """
    Renders the appropriate page based on login status and user role.
    """
    if 'user' in session:
        # Gracefully handle cases where the user ID in the session is no longer valid.
        user = User.query.get(session['user']['uid'])
        if not user:
            # If user not found, the session is invalid. Clear it and redirect.
            session.clear()
            return redirect(url_for('main.index'))

        if user.is_admin:
            return redirect(url_for('admin_dashboard.dashboard'))
        
        return redirect(url_for('main.playground'))
    else:
        # This part for non-logged-in users remains the same
        firebase_config = {
            "apiKey": os.getenv("FIREBASE_API_KEY"), "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
            "projectId": os.getenv("FIREBASE_PROJECT_ID"), "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"), "appId": os.getenv("FIREBASE_APP_ID"),
            "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
        }
        return render_template("home.html",
                               username=None,
                               WORDS_PER_UNIT=WORDS_PER_UNIT,
                               PRICE_PER_UNIT=PRICE_PER_UNIT + 10,
                               ESSAY_PRICE_PER_UNIT=ESSAY_PRICE_PER_UNIT + 10,
                               firebase_config=firebase_config)

@main_bp.app_errorhandler(413)
@main_bp.app_errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    """Handles the 'Request Entity Too Large' error for file uploads."""
    if request.path == url_for('main.extract_text_from_file'):
        return jsonify(error="File is too large. Please upload files under 10MB."), 413
    return "File is too large.", 413

@main_bp.route('/api/get-models')
def get_models():
    """
    API endpoint to provide model data to the frontend.
    """
    models_config = current_app.config.get('MODELS', {})
    model_list = [
        {
            'value': key,
            'label': details['label'],
            'price': details['price_per_word'],
            'selected': key == current_app.config.get('DEFAULT_MODEL', 'gpt-5')
        }
        for key, details in models_config.items()
    ]
    return jsonify(model_list)

@main_bp.route("/transaction-history", methods=['GET'])
@auth_required
def transaction_history():
    user = User.query.get_or_404(session['user']['uid'])
    if not user.wallet:
        flash("No wallet found for this user.", "error")
        return redirect(url_for('main.home'))

    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    pagination = Transaction.query.filter_by(wallet_id=user.wallet.id).order_by(desc(Transaction.created_at)).paginate(page=page, per_page=per_page, error_out=False)
    
    transactions = pagination.items
    
    if transactions:
        current_balance = user.wallet.balance
        
        sum_of_newer_transactions = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.wallet_id == user.wallet.id,
            Transaction.created_at > transactions[0].created_at
        ).scalar() or 0.0

        balance_after = current_balance - sum_of_newer_transactions
        
        for t in transactions:
            t.balance_after = balance_after
            balance_after -= t.amount

    for t in transactions:
        if hasattr(t, 'created_at') and t.created_at:
             t.created_at_local_str = t.created_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Africa/Nairobi')).strftime('%Y-%m-%d %H:%M')
        else:
             t.created_at_local_str = 'N/A'

        t.task = None
        t.display_title = t.description or 'N/A'

        if t.transaction_type == 'humanize_fee' and t.description:
            task = Task.query.filter_by(external_reference=t.description).first()
            if task and task.status == 'humanization_complete':
                t.task = task
                t.display_title = f"Humanizer Task: {task.external_reference}"
        
        elif t.transaction_type == 'playground_fee' and t.description and t.description.startswith('CONV-'):
            try:
                conv_id_str = t.description.split(':')[0].split('-')[1]
                conv_id = int(conv_id_str)
                conversation = Conversation.query.get(conv_id)
                if conversation:
                    t.display_title = conversation.title
            except (IndexError, ValueError):
                pass

    username = get_display_name(user)
    return render_template("transaction_history.html", 
                           user=user,
                           transactions=transactions, 
                           username=username, 
                           pagination=pagination,
                           wallet_balance=user.wallet.balance,
                           is_admin=user.is_admin)

@main_bp.route("/playground_chat", methods=['POST'])
@auth_required
def playground_chat():
    user = User.query.get_or_404(session['user']['uid'])
    data = request.get_json() or {}
    input_parts = data.get('input', [])
    model_key = data.get('model')
    conversation_id = data.get('conversation_id')

    if not isinstance(input_parts, list) or not input_parts:
        return jsonify({"error": "No input provided."}), 400

    try:
        # 1) Create or load a conversation synchronously so the UI gets a stable ID
        if conversation_id:
            conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first_or_404()
        else:
            # Title from first text chunk (fallback if empty)
            raw_title = " ".join(
                p.get("text", "").strip()
                for p in input_parts
                if p.get("type") == "input_text"
            ).strip()
            title = (raw_title[:60] or "New chat")
            conversation = Conversation(user_id=user.id, title=title, model_key=model_key)
            db.session.add(conversation)
            db.session.flush()  # get conversation.id without a separate transaction
            conversation_id = conversation.id

        # 2) Persist the user's message now, so history exists for the worker
        db.session.add(ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=json.dumps(input_parts)
        ))

        # 3) Create the Task and enqueue the worker
        task_ref = f"PLAYGROUND-{uuid.uuid4()}"
        task_data = {
            "user_input_parts": input_parts,
            "model_key": model_key,
            "conversation_id": conversation_id,
        }

        new_task = Task(
            user_id=user.id,
            external_reference=task_ref,
            status='queued',
            diff_data=task_data,
            input_text="Playground Chat",
        )
        db.session.add(new_task)
        db.session.commit()

        process_playground_chat_task.delay(new_task.id)

        # Immediately return the task ID and the stable conversation_id
        return jsonify({
            "status": "processing_started",
            "task_id": new_task.id,
            "conversation_id": conversation_id
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Playground chat submission error for user {user.id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to start the chat task."}), 500

@main_bp.route("/get_playground_task_status/<int:task_id>", methods=['GET'])
@auth_required
def get_playground_task_status(task_id):
    task = Task.query.get_or_404(task_id)

    # Security check: ensure the user owns this task
    if task.user_id != session['user']['uid']:
        return jsonify({"error": "Unauthorized"}), 403

    if task.status == 'humanization_complete':
        # On completion, send back the final response and conversation ID
        return jsonify({
            "status": "complete",
            "response": task.humanized_output,
            "conversation_id": task.diff_data.get('final_conversation_id')
        })
    elif task.status == 'humanization_failed':
        return jsonify({
            "status": "failed",
            "error": task.error_message
        })
    else:
        # Otherwise, just report that it's still processing
        return jsonify({"status": "processing"})

@main_bp.route("/humanizer", methods=['GET'])
@auth_required
def humanizer_page():
    user = User.query.get_or_404(session['user']['uid'])
    if user.is_admin:
        return redirect(url_for('admin_dashboard.dashboard'))
    if not user.wallet:
        db.session.add(Wallet(user=user, balance=0.0))
        db.session.commit()
    username = get_display_name(user)
    firebase_config = {"apiKey": os.getenv("FIREBASE_API_KEY"), "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"), "projectId": os.getenv("FIREBASE_PROJECT_ID"), "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"), "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"), "appId": os.getenv("FIREBASE_APP_ID"), "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")}
    return render_template('dashboard.html', user=user, username=username, wallet_balance=user.wallet.balance, is_admin=user.is_admin, WORDS_PER_UNIT=WORDS_PER_UNIT, PRICE_PER_UNIT=PRICE_PER_UNIT, ESSAY_PRICE_PER_UNIT=ESSAY_PRICE_PER_UNIT, firebase_config=firebase_config)

@main_bp.route("/playground", methods=['GET'])
@auth_required
def playground():
    user = User.query.get_or_404(session['user']['uid'])
    username = get_display_name(user)
    wallet_balance = user.wallet.balance if user.wallet else 0
    
    models = current_app.config['MODELS']
    
    return render_template(
        "playground.html",
        user=user,
        username=username,
        wallet_balance=wallet_balance,
        is_admin=user.is_admin,
        models=models
    )
    
def _initiate_payment_in_background(app, amount, phone_number, transaction_ref):
    with app.app_context():
        try:
            initiate_payhero_payment(amount, phone_number, transaction_ref)
        except Exception as e:
            logger.error(f"Background payment initiation failed for {transaction_ref}: {e}")
            task = Task.query.filter_by(external_reference=transaction_ref).first()
            if task:
                task.status = 'topup_failed'
                task.error_message = "Failed to communicate with payment gateway."
                db.session.commit()

@main_bp.route("/wallet/topup", methods=["POST"])
@auth_required
def wallet_topup():
    data = request.get_json()
    amount, phone_number = data.get("amount"), data.get("phone_number")
    if not all([amount, phone_number, isinstance(amount, (int, float)), amount > 0]):
        return jsonify({"status": "error", "message": "Valid amount and phone number are required."}), 400
    if not KENYAN_PHONE_REGEX.match(phone_number):
        return jsonify({"status": "error", "message": "Invalid Kenyan phone number format."}), 400
    transaction_ref = f"TOPUP-{uuid.uuid4()}"
    temp_task = Task(external_reference=transaction_ref, input_text=f"Top-up of {amount}", phone_number=phone_number,
                     amount_charged=float(amount), status='topup_pending', user_id=session['user']['uid'])
    db.session.add(temp_task)
    db.session.commit()
    app = current_app._get_current_object()
    threading.Thread(target=_initiate_payment_in_background, args=(app, float(amount), phone_number, transaction_ref)).start()
    return jsonify({"status": "payment_initiated", "transaction_id": transaction_ref})

@main_bp.route("/wallet/status/<transaction_id>", methods=["GET"])
@auth_required
def get_topup_status(transaction_id):
    task = Task.query.filter_by(external_reference=transaction_id, user_id=session['user']['uid']).first_or_404()
    if task.status == 'topup_complete':
        return jsonify({"status": "complete", "message": "Top-up successful!"})
    elif task.status == 'topup_failed':
        return jsonify({"status": "failed", "message": task.error_message or "Top-up was cancelled or failed."})
    else:
        return jsonify({"status": "pending", "message": "Awaiting payment confirmation..."})

@main_bp.route("/submit-humanize-task", methods=["POST"])
def submit_humanize_task():
    if 'user' in session:
        return _handle_logged_in_humanization()
    else:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

def _handle_logged_in_humanization():
    user = User.query.get_or_404(session['user']['uid'])
    try:
        data = request.form
        input_text = data.get("input_text", "").strip()
        word_count = count_words(input_text)
        humanizer_mode = data.get("humanizer_mode", "standard")

        if not input_text:
            return jsonify({"status": "error", "message": "Text input is required."}), 400
        
        if humanizer_mode != 'document_formatter' and word_count > MAX_WORDS:
            return jsonify({"status": "error", "message": f"Input exceeds the maximum of {MAX_WORDS} words."}), 413
        
        price = ESSAY_PRICE_PER_UNIT if humanizer_mode == 'essay' else PRICE_PER_UNIT
        amount_to_charge = round((word_count / WORDS_PER_UNIT) * price, 2)
        if user.wallet.balance < amount_to_charge:
            return jsonify({"status": "error", "message": "Insufficient Funds! Please top up your wallet."}), 402
        
        transaction_ref = f"TASK-{uuid.uuid4()}"
        user.wallet.balance -= amount_to_charge
        db.session.add(Transaction(wallet_id=user.wallet.id, amount=-amount_to_charge,
                                     transaction_type='humanize_fee', description=transaction_ref))
        
        new_task = Task(external_reference=transaction_ref, input_text=input_text, phone_number="N/A",
                        amount_charged=amount_to_charge, status='queued', user_id=user.id, # Status is now 'queued'
                        diff_data={key: data.get(key, "") for key in ["output_format", "bibtex_input", "english_dialect", "humanizer_mode"]})
        db.session.add(new_task)
        db.session.commit()
        
        process_humanization_task.delay(new_task.id)
        
        return jsonify({"status": "processing_started", "transaction_id": new_task.external_reference})

    except AllModelsFailedError as e:
        db.session.rollback()  
        flash(e.message, "danger")
        return jsonify({"status": "error", "redirect": url_for('main.home')}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"An unexpected error occurred during humanization for user {user.id}: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
        return jsonify({"status": "error", "redirect": url_for('main.home')}), 500


def _handle_anonymous_humanization():
    data = request.form
    input_text, phone_number = data.get("input_text", "").strip(), data.get("phone_number", "").strip()
    word_count = count_words(input_text)
    humanizer_mode = data.get("humanizer_mode", "standard")
    
    if not all([input_text, phone_number]):
        return jsonify({"status": "error", "message": "Text and phone number are required."}), 400
        
    if humanizer_mode != 'document_formatter' and word_count > MAX_WORDS:
        return jsonify({"status": "error", "message": f"Input exceeds the maximum of {MAX_WORDS} words."}), 413
        
    if not KENYAN_PHONE_REGEX.match(phone_number):
        return jsonify({"status": "error", "message": "Invalid Kenyan phone number format."}), 400
    price = ESSAY_PRICE_PER_UNIT + 10 if humanizer_mode == 'essay' else PRICE_PER_UNIT + 10
    amount_to_charge = round((word_count / WORDS_PER_UNIT) * price, 2)
    transaction_ref = f"HUMANIZE-{uuid.uuid4()}"
    new_task = Task(external_reference=transaction_ref, input_text=input_text, phone_number=phone_number,
                    amount_charged=amount_to_charge, status='payment_pending', user_id=None,
                    diff_data={key: data.get(key, "") for key in ["output_format", "bibtex_input", "english_dialect", "humanizer_mode"]})
    db.session.add(new_task)
    db.session.commit()
    try:
        initiate_payhero_payment(amount_to_charge, phone_number, transaction_ref)
        return jsonify({"status": "payment_initiated", "transaction_id": transaction_ref})
    except Exception as e:
        new_task.status, new_task.error_message = 'payment_failed', str(e)
        db.session.commit()
        logger.error(f"Anonymous payment failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Payment initiation failed."}), 500

@main_bp.route("/payhero-callback", methods=["POST"])
def payhero_callback():
    payload = request.get_json()
    logger.info(f"Received callback: {payload}")
    if not payload: return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400
    response = payload.get('response', {})
    transaction_ref, status = response.get('ExternalReference'), response.get('Status')
    amount = float(response.get('Amount', 0))
    if not transaction_ref: return jsonify({'status': 'success'}), 200
    if transaction_ref.startswith("TOPUP-"):
        task = Task.query.filter_by(external_reference=transaction_ref, status='topup_pending').first()
        if task and task.user:
            if status == 'Success':
                user = task.user
                user.wallet.balance += amount
                db.session.add(Transaction(wallet_id=user.wallet.id, amount=amount,
                                            transaction_type='top-up', description=f"M-Pesa top-up from {task.phone_number}"))
                task.status = 'topup_complete'
            else:
                task.status = 'topup_failed'
                task.error_message = response.get('ResultDesc', 'Top-up was cancelled or failed.')
            db.session.commit()
            logger.info(f"Top-up task {task.id} status updated to {task.status}.")
    elif transaction_ref.startswith("HUMANIZE-"):
        task = Task.query.filter_by(external_reference=transaction_ref, status='payment_pending').first()
        if task:
            if status == 'Success':
                task.status = 'payment_successful'
                db.session.commit()
                app = current_app._get_current_object()
                from .tasks import process_humanization_in_background
                threading.Thread(target=process_humanization_in_background, args=(app, task.id)).start()
                logger.info(f"Anonymous task {task.id} payment successful.")
            else:
                task.status = 'payment_failed'
                task.error_message = response.get('ResultDesc', 'Payment was cancelled or failed.')
                db.session.commit()
                logger.info(f"Anonymous task {task.id} payment failed.")
    return jsonify({'status': 'success'}), 200

@main_bp.route("/get_humanization_status/<transaction_id>", methods=["GET"])
def get_humanization_status(transaction_id):
    task = Task.query.filter_by(external_reference=transaction_id).first_or_404()
    if task.user_id and ('user' not in session or task.user_id != session['user']['uid']):
        abort(403)
    response = {"status": task.status, "message": task.error_message or "Processing..."}
    if task.status == 'humanization_complete':
        diff_data = task.diff_data or {}
        output_format = diff_data.get("output_format", "plain_text")
        if output_format != 'plain_text':
            response.update({"status": "download_ready", "download_url": url_for('main.download_formatted_doc', transaction_id=task.external_reference)})
        else:
            response.update({"status": "complete", "humanized_output": task.humanized_output, "output_word_count": task.output_word_count, "diff_data": diff_data})
    return jsonify(response)

@main_bp.route("/download_formatted_doc/<transaction_id>", methods=["GET"])
def download_formatted_doc(transaction_id):
    task = Task.query.filter_by(external_reference=transaction_id).first_or_404()
    if task.user_id and ('user' not in session or task.user_id != session['user']['uid']):
        abort(403)
    if task.status != 'humanization_complete':
        flash("Document is not yet ready for download.", "danger")
        return redirect(url_for('main.home'))
    
    output_dir = "/tmp" if os.environ.get("FLASK_ENV") == "production" else "output_docs"
    os.makedirs(output_dir, exist_ok=True)
    
    diff_data = task.diff_data or {}
    title = diff_data.get('generated_title') or "Processed document"
    filename = f"{sanitize_filename(title)}.docx"
    filepath = os.path.join(output_dir, filename)
    
    metadata = {'title': title, 'author': "Name", 'date': datetime.now(NAIROBI_TZ).strftime("%d %B %Y")}
    references = diff_data.get('formatted_references', [])
    
    if create_formatted_document(diff_data.get('output_format'), task.humanized_output, filepath, metadata, references):
        return send_file(filepath, as_attachment=True)
    
    flash("Failed to generate the document.", "danger")
    return redirect(url_for('main.home'))

@main_bp.route("/task/details/<transaction_id>")
@auth_required
def view_task_details(transaction_id):
    logger.info(f"--- Entering view_task_details for transaction_id: {transaction_id} ---")
    task = Task.query.filter_by(external_reference=transaction_id).first_or_404()
    user = User.query.get_or_404(session['user']['uid'])
    if not user.is_admin and (task.user_id != user.id):
        logger.warning(f"User {user.id} attempting to access unauthorized task {task.id}.")
        abort(403)

    html_output = "Error: Could not render task output."
    diff_data = task.diff_data or {}
    logger.debug(f"Task {task.id} diff_data loaded: {diff_data}")

    try:
        if task.status != 'humanization_complete':
            logger.warning(f"Task {task.id} is not complete. Status is '{task.status}'. Redirecting.")
            flash("This task is not yet complete.", "danger")
            return redirect(request.referrer or url_for('main.home'))
        
        output_format = diff_data.get('output_format')
        logger.debug(f"Task {task.id} output_format is '{output_format}'.")

        if output_format != 'plain_text':
            logger.warning(f"Task {task.id} has a non-HTML output format ('{output_format}'). Redirecting.")
            flash("This task result is not available for HTML viewing.", "danger")
            return redirect(request.referrer or url_for('main.home'))

        word_diff = diff_data.get('word_diff')
        logger.debug(f"Task {task.id} word_diff data: {word_diff}")

        if isinstance(word_diff, list):
            final_html_parts = []
            current_paragraph_spans = []

            for d in word_diff:
                text_segment = d.get("text", "")
                diff_type = d.get("type", "equal")
                css_class = "word-added" if diff_type == "added" else "word-equal"
                
                parts = text_segment.split("[[PARAGRAPH_BREAK]]")
                
                if parts[0].strip():
                    current_paragraph_spans.append(f'<span class="{css_class}">{parts[0].strip()}</span>')

                if len(parts) > 1:
                    for i in range(1, len(parts)):
                        if current_paragraph_spans:
                            final_html_parts.append(f'<p style="text-indent: 0;">{" ".join(current_paragraph_spans)}</p>')
                        
                        current_paragraph_spans = []
                        if parts[i].strip():
                            current_paragraph_spans.append(f'<span class="{css_class}">{parts[i].strip()}</span>')

            if current_paragraph_spans:
                final_html_parts.append(f'<p style="text-indent: 0;">{" ".join(current_paragraph_spans)}</p>')
            
            html_output = "".join(final_html_parts)
            logger.info("Successfully generated HTML from word_diff with robust paragraph construction.")
        elif task.humanized_output:
            logger.info(f"Task {task.id} has no word_diff, falling back to raw humanized_output.")
            paragraphs = task.humanized_output.split('\n\n')
            final_paragraphs = []
            for p in paragraphs:
                p_with_br = p.replace("\n", "<br>")
                final_paragraphs.append(f'<p style="text-indent: 0;">{p_with_br}</p>')
            html_output = "".join(final_paragraphs)

        else:
            logger.error(f"Task {task.id} has no word_diff and no humanized_output.")
            html_output = "Error: No output data found for this task."

    except Exception as e:
        logger.error(f"FATAL: Could not render HTML for task {transaction_id}. Error: {e}", exc_info=True)
        flash("An unexpected error occurred while trying to display this task.", "danger")
        return redirect(request.referrer or url_for('main.home'))

    username = get_display_name(user)
    back_url = url_for('main.transaction_history')
    humanizer_mode = diff_data.get('humanizer_mode', 'N/A').replace('_', ' ').title()

    logger.info(f"--- Rendering template 'view_task.html' for task {transaction_id} ---")
    return render_template("view_task.html", task=task, username=username, html_output=html_output, back_url=back_url, humanizer_mode=humanizer_mode)

@main_bp.route("/instructions")
def instructions():
    user = User.query.get(session['user']['uid']) if 'user' in session else None
    username = get_display_name(user) if user else None
    wallet_balance = user.wallet.balance if user and user.wallet else 0
    is_admin = user.is_admin if user else False
    return render_template("instructions.html", 
                           user=user,
                           username=username, 
                           wallet_balance=wallet_balance,
                           is_admin=is_admin)

@main_bp.route("/admin/topup", methods=["POST"])
@auth_required
def admin_self_topup():
    user = User.query.get(session['user']['uid'])
    if not user or not user.is_admin:
        abort(403)

    data = request.get_json()
    amount = data.get("amount")

    if not isinstance(amount, (int, float)) or not (0 < amount <= 10000):
        return jsonify({"status": "error", "message": "Invalid amount. Must be between 0.01 and 10,000."}), 400

    user.wallet.balance += amount
    db.session.add(Transaction(
        wallet_id=user.wallet.id,
        amount=amount,
        transaction_type='admin_self_topup',
        description=f'Admin self top-up by {user.email}'
    ))
    db.session.commit()

    flash(f"Successfully added KSh {amount:.2f} to your wallet.", "success")
    return jsonify({"status": "success", "new_balance": user.wallet.balance})

@main_bp.route("/contact")
def contact():
    user = User.query.get(session['user']['uid']) if 'user' in session else None
    username = get_display_name(user) if user else None
    wallet_balance = user.wallet.balance if user and user.wallet else 0
    is_admin = user.is_admin if user else False
    
    return render_template("contact.html", 
                           user=user, 
                           whatsapp_number=WHATSAPP_NUMBER, 
                           username=username,
                           wallet_balance=wallet_balance,
                           is_admin=is_admin)
    
@main_bp.route("/get_conversations", methods=['GET'])
@auth_required
def get_conversations():
    user = User.query.get_or_404(session['user']['uid'])
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 7

    base_query = Conversation.query.filter_by(user_id=user.id)

    if query:
        base_query = base_query.filter(Conversation.title.ilike(f'%{query}%'))
        
    paginated_convs = base_query.order_by(Conversation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    conversations_data = [
        {"id": conv.id, "title": conv.title} 
        for conv in paginated_convs.items
    ]
    
    return jsonify({
    'conversations': conversations_data,
    'total_pages': paginated_convs.pages,
    'current_page': paginated_convs.page,
    'has_next': paginated_convs.has_next,
    'has_prev': paginated_convs.has_prev
    })

@main_bp.route("/conversation/<int:conv_id>", methods=['GET'])
@auth_required
def get_conversation_messages(conv_id):
    user = User.query.get_or_404(session['user']['uid'])
    conversation = Conversation.query.filter_by(id=conv_id, user_id=user.id).first_or_404()
    messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
    message_list = [{"role": msg.role, "content": msg.content} for msg in messages]
    return jsonify(message_list)

@main_bp.route("/conversation/<int:conv_id>", methods=['DELETE'])
@auth_required
def delete_conversation(conv_id):
    user = User.query.get_or_404(session['user']['uid'])
    conversation = Conversation.query.filter_by(id=conv_id, user_id=user.id).first()
    if conversation:
        db.session.delete(conversation)
        db.session.commit()
        return jsonify({"status": "success", "message": "Conversation deleted."}), 200
    return jsonify({"status": "error", "message": "Conversation not found or you do not have permission to delete it."}), 404

@main_bp.route('/extract_text_from_file', methods=['POST'])
@auth_required
def extract_text_from_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    extracted_text = ""
    try:
        if file.filename.lower().endswith('.docx'):
            doc = docx.Document(io.BytesIO(file.read()))
            for para in doc.paragraphs:
                extracted_text += para.text + "\n"
        
        elif file.filename.lower().endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
        
        else:
            return jsonify({"error": "Unsupported file type"}), 400
            
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}", exc_info=True)
        return jsonify({"error": "Failed to process file."}), 500

    return jsonify({"text": extracted_text})
