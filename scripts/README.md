# Setup and maintenance scripts

`development/create_secrets.py` generates local ignored development credentials without printing or overwriting them. Database role provisioning lives in `infrastructure/deployment/database/`, not runtime API logic. Scripts must not embed production configuration or credentials.
