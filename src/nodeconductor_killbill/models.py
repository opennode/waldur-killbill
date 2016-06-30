from __future__ import unicode_literals

import os
import logging
import collections
import StringIO
import xhtml2pdf.pisa as pisa

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils.encoding import python_2_unicode_compatible

from nodeconductor.core import models as core_models
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.structure.models import Customer

from .backend import UNIT_PREFIX, KillBillBackend


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Invoice(LoggableMixin, core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    customer = models.ForeignKey(Customer, related_name='killbill_invoices')
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    date = models.DateField()
    pdf = models.FileField(upload_to='invoices', blank=True, null=True)
    usage_pdf = models.FileField(upload_to='invoices', blank=True, null=True)

    backend_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s %.2f %s" % (self.date, self.amount, self.customer.name)

    def get_log_fields(self):
        return ('uuid', 'customer', 'amount', 'date', 'status')

    def get_billing_backend(self):
        return KillBillBackend(self.customer)

    def get_items(self):
        # TODO: create separate model for items
        if self.backend_id:
            backend = self.get_billing_backend()
            return backend.get_invoice_items(self.backend_id)
        else:
            # Dummy items
            return [
                {
                    "amount": "100",
                    "name": "storage-1GB"
                },
                {
                    "amount": "7.95",
                    "name": "flavor-g1.small1"
                }
            ]

    def generate_invoice_file_name(self, usage=False):
        name = '{}-invoice-{}'.format(self.date.strftime('%Y-%m-%d'), self.pk)
        if usage:
            name += '-usage'
        return name + '.pdf'

    def generate_pdf(self, invoice):
        projects = {}
        for item in invoice['items']:
            project = item['project']
            resource = '%s (%s)' % (item['resource'], item['service'])
            projects.setdefault(project, {'items': {}, 'amount': 0})
            projects[project]['amount'] += item['amount']
            projects[project]['items'].setdefault(resource, 0)
            projects[project]['items'][resource] += item['amount']

        number = 0
        projects = collections.OrderedDict(sorted(projects.items()))
        for project in projects:
            resources = []
            for resource, amount in sorted(projects[project]['items'].items()):
                number += 1
                resources.append((resource, {'amount': amount, 'number': number}))
            projects[project]['items'] = collections.OrderedDict(resources)

        # cleanup if pdf already existed
        if self.pdf is not None:
            self.pdf.delete()

        info = settings.NODECONDUCTOR_KILLBILL.get('INVOICE', {})
        logo = info.get('logo', None)
        if logo and not logo.startswith('/'):
            logo = os.path.join(settings.BASE_DIR, logo)

        result = StringIO.StringIO()
        pdf = pisa.pisaDocument(
            StringIO.StringIO(render_to_string('nodeconductor_killbill/invoice.html', {
                'customer': self.customer,
                'invoice': invoice,
                'projects': projects,
                'info': info,
                'logo': logo,
            })), result)

        # generate a new file
        if not pdf.err:
            self.pdf.save(self.generate_invoice_file_name(), ContentFile(result.getvalue()))
            self.save(update_fields=['pdf'])
        else:
            logger.error(pdf.err)

    def generate_usage_pdf(self, invoice):
        resources = {}
        pricelist = {p.units.replace(UNIT_PREFIX, ''): p for p in DefaultPriceListItem.objects.all()}

        for item in invoice['items']:
            price_item = pricelist.get(item['name'])
            if price_item:
                usage = item['amount'] / float(price_item.value)
                unit = ('GB/hour' if price_item.item_type == 'storage' else 'hour') + (
                    's' if usage > 1 else '')

                # XXX: black magic need to replace MBs to GBs for display of storage values
                if price_item.item_type == 'storage' and 'MB' in price_item.name:
                    from decimal import Decimal
                    item['name'] = price_item.name.replace('MB', 'GB')
                    usage /= 1024.0
                    value = price_item.value * Decimal('1024.0')
                else:
                    item['name'] = price_item.name
                    value = price_item.value
                item['usage'] = "{:.3f} {} x {:.3f} {}".format(
                    usage, unit, value, item['currency'])

            resource = '%s (%s)' % (item['resource'], item['service'])
            resources.setdefault(resource, {'items': [], 'amount': 0})
            resources[resource]['amount'] += item['amount']
            resources[resource]['items'].append(item)

        resources = collections.OrderedDict(sorted(resources.items()))

        # cleanup if pdf already existed
        if self.usage_pdf is not None:
            self.usage_pdf.delete()

        info = settings.NODECONDUCTOR_KILLBILL.get('INVOICE', {})
        logo = info.get('logo', None)
        if logo and not logo.startswith('/'):
            logo = os.path.join(settings.BASE_DIR, logo)

        result = StringIO.StringIO()
        pdf = pisa.pisaDocument(
            StringIO.StringIO(render_to_string('nodeconductor_killbill/usage_invoice.html', {
                'customer': self.customer,
                'invoice': invoice,
                'resources': resources,
                'logo': logo,
            })), result)

        # generate a new file
        if not pdf.err:
            self.usage_pdf.save(self.generate_invoice_file_name(usage=True), ContentFile(result.getvalue()))
            self.save(update_fields=['usage_pdf'])
        else:
            logger.error(pdf.err)
