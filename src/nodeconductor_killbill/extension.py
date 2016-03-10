from __future__ import absolute_import

from nodeconductor.core import NodeConductorExtension


class KillBillExtension(NodeConductorExtension):

    class Settings:
        NODECONDUCTOR_KILLBILL = {
            'BACKEND': {
                # url of billing API
                'api_url': 'http://killbill.example.com/1.0/kb/',
                # credentials
                'username': 'admin',
                'password': 'password',
                # tenant credentials
                'api_key': 'bob',
                'api_secret': 'lazar',
                # extra options
                'currency': 'USD',
            },
            'INVOICE': {
                'logo': 'gcloud-logo.png',
                'company': 'OpenNode',
                'address': 'Lille 4-205',
                'country': 'Estonia',
                'email': 'info@opennodecloud.com',
                'postal': '80041',
                'phone': '(+372) 555-55-55',
                'bank': 'American Bank',
                'account': '123456789',
            },
        }

    @staticmethod
    def django_app():
        return 'nodeconductor_killbill'

    @staticmethod
    def rest_urls():
        from .urls import register_in
        return register_in

    @staticmethod
    def celery_tasks():
        from celery.schedules import crontab
        return {
            'update-today-usage': {
                'task': 'nodeconductor.killbill.update_today_usage',
                'schedule': crontab(minute=10),
                'args': (),
            },
        }
