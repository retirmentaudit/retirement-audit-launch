import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth

# Make sidebar always open
st.set_page_config(initial_sidebar_state="expanded")

# Initialize Firebase (only once)
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-service-account.json")
    firebase_admin.initialize_app(cred)

# --- Session State for User ---
if 'user' not in st.session_state:
    st.session_state.user = None

# --- Sidebar: Login / Sign Up ---
st.sidebar.title("Account")

choice = st.sidebar.radio("Login or Sign Up", ["Login", "Sign Up"])

if choice == "Sign Up":
    st.sidebar.subheader("Create a new account")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Sign Up"):
        if email and password:
            try:
                user = auth.create_user(email=email, password=password)
                st.sidebar.success(f"Account created! You are logged in as {email}")
                st.session_state.user = user
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Sign up failed: {str(e)}")
        else:
            st.sidebar.warning("Please fill in both fields")

if choice == "Login":
    st.sidebar.subheader("Log in to your account")
    email = st.sidebar.text_input("Email ", key="login_email")
    password = st.sidebar.text_input("Password ", type="password", key="login_password")
    if st.sidebar.button("Login"):
        if email and password:
            try:
                # For login, we use the email to get user (Firebase Admin doesn't verify password directly for security)
                user = auth.get_user_by_email(email)
                st.session_state.user = user
                st.sidebar.success("Welcome back!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Login failed: {str(e)}")
        else:
            st.sidebar.warning("Please fill in both fields")

# --- Main App ---
st.title("Retirement Audit App 🚀")

if st.session_state.user:
    st.write(f"Hello, {st.session_state.user.email}! You're logged in.")
    if st.button("Log out"):
        st.session_state.user = None
        st.rerun()
else:
    st.write("Welcome! This is your app running locally.")
    st.write("If you can see this page, everything is working perfectly!")

# Fun test stuff (keep the balloons!)
st.write("What's your name?")
name = st.text_input("Enter here")
if name:
    st.write(f"Hello, {name}! You're building something awesome.")

if st.button("Click me for encouragement"):
    st.balloons()
    