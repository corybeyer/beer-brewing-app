# Configuration

Owns environment parsing and secret-file loading in Python package `brewery_config`. It must not import API, UI, domain workflows, or deployment code. No real credentials belong in this package. Browser configuration must never expose database passwords.
