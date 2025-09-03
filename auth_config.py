# auth_config.py
import streamlit_authenticator as stauth


# Generate hashed passwords (do this once locally)
def generate_hashed_passwords():
    """Run this locally once to generate hashed passwords"""
    passwords = ['your_password_here']
    hashed_passwords = stauth.Hasher(passwords).generate()
    print(hashed_passwords)
    # Copy the output to your secrets


# Authentication configuration
def get_auth_config():
    """Get authentication config from secrets"""
    import streamlit as st

    # Store these in .streamlit/secrets.toml locally
    # and in Streamlit Cloud secrets
    return {
        'credentials': {
            'usernames': {
                st.secrets.auth.username: {
                    'email': st.secrets.auth.email,
                    'name': st.secrets.auth.name,
                    'password': st.secrets.auth.password  # hashed password
                }
            }
        },
        'cookie': {
            'name': st.secrets.cookie.name,
            'key': st.secrets.cookie.key,
            'expiry_days': st.secrets.cookie.expiry_days
        }
    }
