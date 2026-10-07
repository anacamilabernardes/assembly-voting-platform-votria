from django.conf import settings
from django.db import connection, DatabaseError
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    page = settings.FRONTEND_DIST / 'index.html'
    if not page.exists():
        return JsonResponse({'detail': 'Interface ainda não foi compilada.'}, status=503)
    response = FileResponse(page.open('rb'), content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        from governance.models import Assembly
        ready = (settings.FRONTEND_DIST / 'index.html').exists()
        if settings.DEMO_MODE:
            ready = ready and Assembly.objects.filter(code='SIM-001', is_demo=True).exists()
    except DatabaseError:
        ready = False
    return JsonResponse({'status': 'ok' if ready else 'unavailable', 'official_ready': False}, status=200 if ready else 503)
