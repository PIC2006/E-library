from django.conf import settings

from cloudinary_storage.storage import RawMediaCloudinaryStorage

import cloudinary.uploader


class ThesisPDFCloudinaryStorage(RawMediaCloudinaryStorage):
    """Use chunked Cloudinary upload for large thesis PDFs."""

    def _upload(self, name, content):
        options = {
            "use_filename": True,
            "resource_type": self._get_resource_type(name),
            "tags": self.TAG,
        }
        folder = name.rsplit("/", 1)[0] if "/" in name else ""
        if folder:
            options["folder"] = folder

        chunk_threshold_mb = float(getattr(settings, "PDF_CHUNKED_UPLOAD_THRESHOLD_MB", 8) or 0)
        chunk_size_mb = float(getattr(settings, "PDF_CHUNK_SIZE_MB", 20) or 20)
        chunk_threshold_bytes = int(max(0.0, chunk_threshold_mb) * 1024 * 1024)
        chunk_size_bytes = int(max(5.0, chunk_size_mb) * 1024 * 1024)

        content_size = getattr(content, "size", None)
        if content_size is not None and content_size >= chunk_threshold_bytes:
            return cloudinary.uploader.upload_large(content, chunk_size=chunk_size_bytes, **options)

        return cloudinary.uploader.upload(content, **options)
