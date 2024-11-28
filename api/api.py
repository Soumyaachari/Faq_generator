import os
from ninja import NinjaAPI, File
from ninja.errors import HttpError
from ninja.files import UploadedFile
from django.contrib.auth.models import User
from transformers import pipeline
from .models import Document, FAQ
from ninja.security import django_auth
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse

# Initialize the Ninja API
api = NinjaAPI(csrf=True)

# Set the Hugging Face API key (replace with your actual key)
os.environ["HUGGINGFACE_API_KEY"] = "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"

# Initialize the Hugging Face model pipeline
faq_generator = pipeline("text2text-generation", model="google/flan-t5-large")

# Allowed content types for document uploads
ALLOWED_CONTENT_TYPES = ["text/plain"]

# Function to generate FAQs from document content
def generate_faqs(content):
    prompt = f"Generate 5 FAQs based on the following text:\n\n{content}"
    try:
        # Using beam search to enable multiple outputs
        faqs = faq_generator(
            prompt,
            max_length=256,
            num_return_sequences=5,
            num_beams=5  # Enable beam search with 5 beams
        )
        return [{"question": faq["generated_text"]} for faq in faqs if faq["generated_text"].strip()]
    except Exception as e:
        raise ValueError(f"FAQ generation failed: {str(e)}")

# Endpoint to upload a document and generate FAQs
@csrf_exempt
@method_decorator(csrf_exempt, name="dispatch")
@api.post("/upload_document/")
def upload_document(request, title: str, description: str, file: UploadedFile = File(...)):
    """
    Uploads a document, stores it in the database, and generates FAQs for the document.
    """
    try:
        # Validate file content type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HttpError(
                400, f"Invalid file type. Only the following types are allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
            )

        # Decode file content
        content = file.read().decode("utf-8").strip()
        if not content:
            raise HttpError(400, "The uploaded document is empty.")

        # Validate document metadata
        if not title.strip():
            raise HttpError(400, "Document title cannot be empty.")
        if not description.strip():
            raise HttpError(400, "Document description cannot be empty.")

        # Save document to database
        user = request.user  # Ensure user authentication
        document = Document.objects.create(
            title=title, description=description, content=content, uploaded_by=user
        )

        # Generate FAQs
        faqs = generate_faqs(content)
        if not faqs:
            raise HttpError(400, "Failed to generate any FAQs from the provided document.")

        created_questions = set()  # Track unique questions to avoid duplicates
        for faq in faqs:
            question = faq["question"]
            if question not in created_questions:
                generated = faq_generator(
                    f"Answer the question '{question}' based on the text: {content}",
                    max_length=256,
                )
                answer = generated[0]["generated_text"] if generated else "No answer available."
                FAQ.objects.create(document=document, question=question, answer=answer)
                created_questions.add(question)

        return JsonResponse({"success": True, "document_id": document.id})
    except HttpError as e:
        raise e  # Re-raise HTTP errors for proper response
    except Exception as e:
        return JsonResponse({"success": False, "error": f"An unexpected error occurred: {str(e)}"})

# Endpoint to update document title or description

@api.put("/update_document/{document_id}/", auth=django_auth)
def update_document(request, document_id: int, title: str = None, description: str = None):
    """
    Updates the title or description of a specific document.
    """
    try:
        document = Document.objects.get(id=document_id)
        if title:
            document.title = title.strip()
        if description:
            document.description = description.strip()
        if not title and not description:
            raise HttpError(400, "No fields provided to update.")
        document.save()
        return {"success": True, "document_id": document.id, "message": "Document updated successfully."}
    except Document.DoesNotExist:
        raise HttpError(404, f"Document with ID {document_id} not found.")
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}


# Endpoint to delete a document and its associated FAQs
@csrf_exempt
@api.delete("/delete_document/{document_id}/", auth=django_auth)
def delete_document(request, document_id: int):
    """
    Deletes a specific document and its associated FAQs.
    """
    try:
        document = Document.objects.get(id=document_id)
        # Delete associated FAQs
        FAQ.objects.filter(document=document).delete()
        # Delete the document
        document.delete()
        return {"success": True, "message": "Document and associated FAQs deleted successfully."}
    except Document.DoesNotExist:
        raise HttpError(404, f"Document with ID {document_id} not found.")
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}

# Endpoint to list all documents
@api.get("/documents/")
def list_documents(request):
    """
    Lists all documents stored in the database with their details.
    """
    try:
        documents = Document.objects.all()
        return [
            {
                "id": doc.id,
                "title": doc.title,
                "description": doc.description,
                "content": doc.content,
                "uploaded_by": doc.uploaded_by.username,  # Include username of uploader
                "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),  # Format date
            }
            for doc in documents
        ]
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}


# Endpoint to list FAQs for a specific document
@api.get("/faqs/{document_id}/")
def list_faqs(request, document_id: int):
    """
    Lists all FAQs associated with a specific document by its ID and includes document details.
    """
    try:
        # Fetch the document
        document = Document.objects.get(id=document_id)
        
        # Fetch FAQs associated with the document
        faqs = document.faqs.all()  # Use the `related_name` to fetch related FAQs

        # Construct the response
        response = {
            "document": {
                "id": document.id,
                "title": document.title,
                "description": document.description,
                "content": document.content,
                "uploaded_by": document.uploaded_by.username,
                "upload_date": document.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "faqs": [
                {"question": faq.question, "answer": faq.answer}
                for faq in faqs
            ]
        }

        return response
    except Document.DoesNotExist:
        raise HttpError(404, f"Document with ID {document_id} not found.")
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}


