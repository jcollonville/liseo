import os

os.environ.setdefault("LISEO_ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("LISEO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("LISEO_DATA_DIR", "/tmp/liseo-tests-unused")
os.environ.setdefault("LISEO_ALLOWED_OPERATORS", "acs4.edenlivres.fr")
os.environ.setdefault("LISEO_PUBLIC_URL", "http://localhost:8080")
