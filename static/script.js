// Function to switch between menu sections
function showSection(sectionId) {
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
    
    if(sectionId === 'verify') loadPendingForVerification();
}

// 1. ADD CUSTOMER
document.getElementById('customerForm').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
        id_num: document.getElementById('cust_id_num').value,
        first: document.getElementById('first_name').value,
        last: document.getElementById('last_name').value,
        nat_id: document.getElementById('nat_id').value,
        phone: document.getElementById('phone').value
    };
    const res = await fetch('/customer/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    const result = await res.json();
    alert(result.message + " ID: " + result.id);
    e.target.reset();
};

// 2. APPLY LOAN
document.getElementById('loanForm').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
        customer_id: document.getElementById('loan_cust_id').value,
        amount: document.getElementById('amount').value,
        period: document.getElementById('period').value,
        interest: document.getElementById('interest').value
    };
    const res = await fetch('/loan/apply', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    const result = await res.json();
    alert(result.message);
    e.target.reset();
};

// 3. LOAD PENDING FOR VERIFICATION
async function loadPendingForVerification() {
    const res = await fetch('/reports/unpaid'); // Reusing the unpaid report for demo
    const data = await res.json();
    const container = document.getElementById('pendingList');
    container.innerHTML = data.map(loan => `
        <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 10px;">
            <p><strong>Loan ID:</strong> ${loan.loan_id} | <strong>User:</strong> ${loan.customer_name}</p>
            <p><strong>Amount:</strong> ${loan.loan_amount} KES</p>
            <button onclick="verifyLoan(${loan.loan_id}, 'granted')" style="width: 100px; display: inline;">Grant</button>
            <button onclick="verifyLoan(${loan.loan_id}, 'rejected')" style="width: 100px; display: inline; background: #e74c3c;">Deny</button>
        </div>
    `).join('');
}

async function verifyLoan(id, status) {
    await fetch('/loan/review', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({loan_id: id, status: status})
    });
    alert(`Loan ${id} ${status}`);
    loadPendingForVerification();
}