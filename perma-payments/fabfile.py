# set up Django
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
try:
    django.setup()
except Exception as e:
    print("WARNING: Can't configure Django -- tasks depending on Django will fail:\n%s" % e)

from fabric.api import local
from fabric.decorators import task
from django.conf import settings

@task(alias='run')
def run_django():
    local("python3 manage.py runserver 0.0.0.0:80")

@task
def test():
    local("pytest --cov --cov-report= --ds=config.settings.settings_testing")


@task
def init_db():
    """
    Set up a new dev database.
    """
    local("python3 manage.py migrate")
    if settings.ADMIN_ENABLED:
        print("Creating dev admin user.")
        from django.contrib.auth.models import User #noqa
        User.objects.create_superuser('admin', 'admin@example.com', 'admin')


@task
def find_pending_cancellation_requests():
    """
    Report pending cancellation requests.

    This is just a draft; once we know how we want to schedule this task,
    we can adapt appropriately (output format, code location, etc.)
    """
    from perma_payments.constants import CS_SUBSCRIPTION_SEARCH_URL #noqa
    from perma_payments.email import send_admin_email #noqa
    from perma_payments.models import SubscriptionAgreement #noqa
    from django.test.client import RequestFactory #noqa
    import json #noqa

    sas = SubscriptionAgreement.objects.filter(cancellation_requested=True).exclude(status='Cancelled')
    data = [
        {
            'registrar': sa.registrar,
            'merchant_reference_number': sa.subscription_request.reference_number,
            'status': sa.status
        } for sa in sas
    ]
    send_admin_email(
        'ACTION REQUIRED: cancellation requests pending',
        settings.DEFAULT_FROM_EMAIL,
        RequestFactory().get('this-is-a-placeholder-request'),
        template="email/cancellation_report.txt",
        context={
            'search_url': CS_SUBSCRIPTION_SEARCH_URL[settings.CS_MODE],
            'perma_url': settings.PERMA_URL,
            'registrar_detail_path': settings.REGISTRAR_DETAIL_PATH,
            'registrar_users_path': settings.REGISTRAR_USERS_PATH,
            'total': len(data),
            'requests': data
        }
    )
    response = {
        'total': len(data),
        'requests': data
    }
    print(json.dumps(response))
    return json.dumps(response)
