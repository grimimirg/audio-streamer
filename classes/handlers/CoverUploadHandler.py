import os
import uuid
from flask import jsonify, send_from_directory
from werkzeug.utils import secure_filename

from utilities.Logger import Logger


class CoverUploadHandler:
    """Handles album cover image upload and serving."""

    def __init__(self, upload_folder: str):
        """Initialize the cover upload handler.
        
        Args:
            upload_folder: Directory path where cover images are stored
        """
        self.upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)

    def clear_upload_folder(self):
        """Clear all files from the upload folder."""
        if os.path.exists(self.upload_folder):
            for filename in os.listdir(self.upload_folder):
                file_path = os.path.join(self.upload_folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        Logger.info(f"Deleted old upload: {file_path}")
                except Exception as e:
                    Logger.error(f"Error deleting file {file_path}: {e}")
            Logger.info("Upload folder cleared at application startup")

    def upload_cover(self, file):
        """Handle album cover image upload.
        
        Args:
            file: File object from request.files
            
        Returns:
            dict: JSON response with the URL of the uploaded image, or error
        """
        try:
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if file:
                # Generate unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(self.upload_folder, unique_filename)

                # Save file
                file.save(filepath)

                # Return URL
                url = f"/uploads/covers/{unique_filename}"
                Logger.info(f"Cover image uploaded: {url}")
                return jsonify({'url': url})

        except Exception as e:
            Logger.error(f"Error uploading cover: {e}")
            return jsonify({'error': 'Failed to upload file'}), 500

    def serve_cover(self, filename):
        """Serve uploaded cover images.
        
        Args:
            filename: Name of the file to serve
            
        Returns:
            File: The requested image file, or error response
        """
        try:
            return send_from_directory(self.upload_folder, filename)
        except Exception as e:
            Logger.error(f"Error serving cover {filename}: {e}")
            return jsonify({'error': 'File not found'}), 404
