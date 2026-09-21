"""Read a freshly uploaded document with Claude and suggest its title, category
and issue/expiry dates, so the upload form can be pre-filled.

Everything here is best-effort: any failure (no API key, unsupported file,
API error, refusal) just means "no suggestion" and the user fills the form by hand.
"""
import base64
import io
import json
import logging
from datetime import date

import anthropic
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

IMAGE_MAX_SIDE = 1568  # larger images are downscaled server-side anyway; this keeps uploads small
PDF_MAGIC = b'%PDF'

SYSTEM_PROMPT = (
    'You read scanned or photographed personal and business documents (IDs, passports, '
    'licenses, insurance, contracts, certificates, registrations) in Arabic or English '
    'and report the key details for a document-vault form. Report only what is printed '
    'on the document. If a value is missing, unclear, or you would have to guess, return '
    'null for it. Dates must be Gregorian and formatted YYYY-MM-DD; if a date appears only '
    'as a Hijri date, return null for it. "expiry_date" is the date the document stops '
    'being valid, and must not be earlier than "issue_date".'
)

RESULT_SCHEMA = {
    'type': 'object',
    'properties': {
        'title': {
            'anyOf': [{'type': 'string'}, {'type': 'null'}],
            'description': 'Short descriptive title in the document\'s own language, e.g. "Passport - Ahmed Ali".',
        },
        'category_id': {
            'anyOf': [{'type': 'integer'}, {'type': 'null'}],
            'description': 'The id of the best-matching category from the provided list, or null.',
        },
        'issue_date': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
        'expiry_date': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
    },
    'required': ['title', 'category_id', 'issue_date', 'expiry_date'],
    'additionalProperties': False,
}


class ExtractionUnavailable(Exception):
    """The feature is off (no API key configured)."""


class ExtractionSkipped(Exception):
    """This particular file can't be read (type/size). The message is safe to show the user."""


def _content_block(uploaded_file):
    """Build the Claude content block for an uploaded image or PDF."""
    uploaded_file.seek(0)
    raw = uploaded_file.read(settings.AI_EXTRACTION_MAX_BYTES + 1)
    uploaded_file.seek(0)
    if len(raw) > settings.AI_EXTRACTION_MAX_BYTES:
        raise ExtractionSkipped('file too large')

    if raw.startswith(PDF_MAGIC):
        data = base64.standard_b64encode(raw).decode('ascii')
        return {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': data}}

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
        out = io.BytesIO()
        image.convert('RGB').save(out, format='JPEG', quality=85)
    except Exception as exc:  # Pillow raises many things for corrupt/unsupported images
        raise ExtractionSkipped('unsupported file') from exc
    data = base64.standard_b64encode(out.getvalue()).decode('ascii')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': data}}


def _valid_date(value):
    try:
        return date.fromisoformat(value).isoformat() if value else None
    except (TypeError, ValueError):
        return None


def extract_document_details(uploaded_file, categories):
    """Return {'title', 'category_id', 'issue_date', 'expiry_date'} (each possibly None).

    `categories` is an iterable of Category objects the user may choose from.
    """
    if not settings.AI_EXTRACTION_ENABLED:
        raise ExtractionUnavailable()

    block = _content_block(uploaded_file)
    category_lines = '\n'.join(f'{c.pk}: {c.name_en} / {c.name_ar}' for c in categories)
    prompt = (
        f'Today is {timezone.localdate().isoformat()}.\n'
        f'Categories to choose from (id: English / Arabic):\n{category_lines}\n\n'
        'Extract the details of the attached document.'
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': [block, {'type': 'text', 'text': prompt}]}],
        output_config={
            'effort': 'low',
            'format': {'type': 'json_schema', 'schema': RESULT_SCHEMA},
        },
    )
    if response.stop_reason != 'end_turn':
        logger.info('Document extraction stopped early: %s', response.stop_reason)
        return {}

    text = next((b.text for b in response.content if b.type == 'text'), '')
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning('Document extraction returned non-JSON output (request %s)', response._request_id)
        return {}

    valid_ids = {c.pk for c in categories}
    issue, expiry = _valid_date(data.get('issue_date')), _valid_date(data.get('expiry_date'))
    if issue and expiry and expiry < issue:
        expiry = None  # contradictory reading — better to leave it for the user than to guess
    category_id = data.get('category_id')
    return {
        'title': (data.get('title') or '').strip()[:200] or None,
        'category_id': category_id if category_id in valid_ids else None,
        'issue_date': issue,
        'expiry_date': expiry,
    }


def extract_for_user(user, uploaded_file):
    """Rate-limited entry point shared by the web view and the API.

    Returns (payload, http_status). `payload` is either the suggested fields or
    {'error': <code>} where code is one of: disabled, no_file, rate_limited,
    unsupported, failed.
    """
    from django.core.cache import cache
    from django.db.models import Q

    from .models import Category

    if not settings.AI_EXTRACTION_ENABLED:
        return {'error': 'disabled'}, 503
    if uploaded_file is None:
        return {'error': 'no_file'}, 400

    key = f'ai-extract:{user.pk}:{timezone.now():%Y%m%d%H}'
    cache.add(key, 0, 3600)
    if cache.incr(key) > settings.AI_EXTRACTION_HOURLY_LIMIT:
        return {'error': 'rate_limited'}, 429

    categories = list(Category.objects.filter(Q(owner__isnull=True) | Q(owner=user)))
    try:
        return extract_document_details(uploaded_file, categories), 200
    except ExtractionSkipped:
        return {'error': 'unsupported'}, 422
    except anthropic.APIError:
        logger.exception('Claude API error during document extraction')
        return {'error': 'failed'}, 502
    except Exception:
        logger.exception('Unexpected error during document extraction')
        return {'error': 'failed'}, 502
