@app.route('/dashboard')
def dashboard():
    # Check if user is in session
    is_logged_in = 'user' in session
    
    return render_template(
        'dashboard.html',
        is_logged_in=is_logged_in,
        sign_in_url=url_for('auth.login')
    )
