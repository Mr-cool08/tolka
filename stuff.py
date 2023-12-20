from flask import Flask, render_template, request
app = Flask(__name__)
@app.route('/')
def home():
    return render_template('index.html')
@app.route('/billing', methods=['POST', 'GET'])
def billing():
    if request.method == 'GET':
        return render_template('billing.html')
    else:
    # Retrieve form data
        avtals_kund = request.form.get('avtals_kund')
        organization_number = request.form.get('organization_number')
        billing_address = request.form.get('billing_address')
        email_billing_address = request.form.get('email_billing_address')
        marking = request.form.get('marking')
        reference = request.form.get('reference')

        # Perform any necessary processing or validation

        # Return a response or redirect to another page
        return 'Form submitted successfully!'


if __name__ == '__main__':
    app.run()