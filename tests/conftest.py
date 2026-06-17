import os

# Set standard test environment variables before any application code is imported
os.environ["ENVIRONMENT"] = "test"
os.environ["APP_NAME"] = "Memory With Receipts"
os.environ["EMBEDDING_DIMENSION"] = "384"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
