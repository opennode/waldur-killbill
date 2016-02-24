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
                'bank': 'American Bank',
                'account': '123456789',
            },
        }
        # mapping of resource types to human friendly titles in invoices
        NODECONDUCTOR_KILLBILL_RESOURCE_NAMES = {
            'IaaS.Instance': 'OpenStack Instance',
            'OpenStack.Instance': 'OpenStack Instance',
            'SaltStack.ExchangeTenant': 'MS Exchange tenant',
            'SaltStack.SharepointTenant': 'MS SharePoint tenant',
            'SugarCRM.CRM': 'SugarCRM Instance',
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
