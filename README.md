# MSE-Analyzer
MSE Analyzer is a responsive and user-friendly web application developed using Django and styled with Bootstrap. It provides comprehensive tools for analyzing the Macedonian Stock Exchange (MSE), including technical indicators, fundamental insights, and LSTM-based stock price predictions. The Bootstrap-powered interface ensures a clean, modern look with seamless usability across devices, while Django handles the backend logic, data processing, and integration with external sources. Whether you're exploring market trends or generating investment signals, MSE Analyzer delivers a complete and accessible solution for financial analysis.

# ⚙️ How to Run the App Locally
### 1. 📥 Clone the Repository
git clone https://github.com/ardit203/MSE-Analyzer.git 

cd MSE-Analyzer
### 2. 🐍 Create a Virtual Environment
You can do this manually or with the help of these commands:

python -m venv venv 

Activate it: 

On Windows: venv\Scripts\activate 

On macOS/Linux: source venv/bin/activate 


### 3. 📦 Install Dependencies
pip install -r requirements.txt


### 4. Make Migrations
python manage.py makemigrations


### 5. 🧱 Run Migrations
python manage.py migrate


### 5. 👤 Create a Superuser (for Admin Panel Access)
python manage.py createsuperuser


### 6. ▶️ Run the Development Server
python manage.py runserver
