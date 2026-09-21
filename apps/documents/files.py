"""Serving of uploaded files.

Uploads are never exposed under MEDIA_URL. Every download goes through one of
the views below, each of which checks who is asking:

  * the owner, logged in         -> documents:file / documents:version_file
  * anyone with a live share link -> documents:shared_file
  * an API client                -> documents:signed_file (short-lived signed URL,
                                    so image/PDF widgets can load it without headers)
"""
import mimetypes

from django.core import signing
from django.http import FileResponse, Http404
from django.urls import reverse
from django.utils.cache import patch_cache_control

SIGNED_URL_MAX_AGE = 60 * 60  # seconds
_SALT = 'mybox.signed-file'
_INLINE_KINDS = {'image', 'pdf'}  # everything else is always a download (never rendered by the browser)


def serve_file(fieldfile, kind, download=False):
    """Stream `fieldfile`. Only images and PDFs may display inline; any other
    type (e.g. an uploaded .html or .svg) is forced to download so it can't run
    script on our origin."""
    if not fieldfile:
        raise Http404
    try:
        handle = fieldfile.storage.open(fieldfile.name, 'rb')
    except FileNotFoundError:
        raise Http404 from None

    name = fieldfile.name.rsplit('/', 1)[-1]
    content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    inline = kind in _INLINE_KINDS and not download
    response = FileResponse(handle, content_type=content_type, as_attachment=not inline, filename=name)
    response['X-Content-Type-Options'] = 'nosniff'
    # no-store also tells our service worker not to keep a copy in the browser's cache.
    patch_cache_control(response, private=True, no_store=True)
    return response


def signed_file_url(request, kind, pk):
    """Absolute, expiring URL for API clients. `kind` is 'doc' or 'ver'."""
    token = signing.dumps({'k': kind, 'id': pk}, salt=_SALT)
    return request.build_absolute_uri(reverse('documents:signed_file', args=[token]))


def read_signed_token(token):
    """Return (kind, pk) for a valid, unexpired token, else None."""
    try:
        data = signing.loads(token, salt=_SALT, max_age=SIGNED_URL_MAX_AGE)
        return data['k'], int(data['id'])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return None
