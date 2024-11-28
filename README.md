# Faq_generator

This project provides an API for uploading text documents, generating FAQs (Frequently Asked Questions), and managing the uploaded documents. The application leverages the Hugging Face `google/flan-t5-large` model to process text and generate meaningful FAQs.

---

## Features

- **Upload Documents**: Upload text documents via the API.
- **Generate FAQs**: Automatically generate FAQs from the document content using AI.
- **Retrieve FAQs**: Get the list of FAQs for a specific document by its ID.
- **Update Documents**: Update the title and description of an uploaded document.
- **Delete Documents**: Delete documents and their associated FAQs.

---

## Requirements

- Python 3.8+
- Django 4.0+
- Ninja Framework
- Hugging Face Transformers
