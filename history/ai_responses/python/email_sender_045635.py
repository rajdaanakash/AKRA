import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(subject, message, from_addr, to_addr, password):
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject

    body = message
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_addr, password)
    text = msg.as_string()
    server.sendmail(from_addr, to_addr, text)
    server.quit()

# Replace with your Gmail address and App Password
from_addr = 'your_email@gmail.com'
password = 'your_app_password'
to_addr = 'recipient_email@gmail.com'
subject = 'Test Email'
message = 'Hello, this is a test email sent from Python'

send_email(subject, message, from_addr, to_addr, password)