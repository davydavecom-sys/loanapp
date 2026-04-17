@app.route('/apply-loan', methods=['GET', 'POST'])
@roles_allowed('admin', 'marketer')
def apply_loan():
    # 1. Fetch all customers for the dropdown
    customers = db.get_all_customers() 
    # 2. Fetch the active loan rate (e.g., 10%)
    current_rate = db.get_active_rate()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        amount = float(request.form.get('amount'))
        return_date = request.form.get('return_date')
        
        # Logic Check: Does the customer have wallet credit?
        wallet_balance = db.get_wallet_balance(customer_id)
        
        # Subtract credit from the amount requested
        # If they have 50 bob, and ask for 1000, the loan record becomes 950
        actual_loan_principal = amount - wallet_balance
        
        # Calculate Interest and Total
        interest_amt = actual_loan_principal * (current_rate['percentage'] / 100)
        total_to_pay = actual_loan_principal + interest_amt

        # Save to Database (this triggers the L_0000001 ID)
        loan_app_id = db.apply_for_loan(
            customer_id=customer_id,
            amount=actual_loan_principal,
            interest=interest_amt,
            total=total_to_pay,
            return_date=return_date,
            rate_id=current_rate['id']
        )
        
        # If credit was used, clear the wallet
        if wallet_balance > 0:
            db.clear_wallet(customer_id, loan_app_id)

        flash(f"Application {loan_app_id} submitted as PENDING.")
        return redirect(url_for('dashboard'))

    return render_template('apply_loan.html', customers=customers, rate=current_rate)
