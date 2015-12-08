import os
import StringIO

from datetime import datetime
from collections import defaultdict, OrderedDict
from xhtml2pdf import pisa

from django import http
from django.db import connection
from django.db.models import Sum
from django.conf import settings
from django.views.static import serve
from django.template.loader import render_to_string
from rest_framework import viewsets, permissions, decorators, exceptions, status
from rest_framework.response import Response

from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.structure.filters import GenericRoleFilter

from .backend import KillBillError
from .filters import InvoiceFilter
from .models import Invoice
from .serializers import InvoiceSerializer


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.all()
    filter_class = InvoiceFilter
    filter_backends = (GenericRoleFilter, DjangoMappingFilterBackend)
    lookup_field = 'uuid'
    permission_classes = (
        permissions.IsAuthenticated,
        permissions.DjangoObjectPermissions,
    )
    serializer_class = InvoiceSerializer

    def _serve_pdf(self, request, pdf):
        if not pdf:
            raise exceptions.NotFound("There's no PDF for this invoice")

        response = serve(request, pdf.name, document_root=settings.MEDIA_ROOT)
        if request.query_params.get('download'):
            filename = pdf.name.split('/')[-1]
            response['Content-Type'] = 'application/pdf'
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        return response

    @decorators.detail_route()
    def pdf(self, request, uuid=None):
        return self._serve_pdf(request, self.get_object().pdf)

    @decorators.detail_route()
    def usage_pdf(self, request, uuid=None):
        return self._serve_pdf(request, self.get_object().usage_pdf)

    @decorators.detail_route()
    def items(self, request, uuid=None):
        try:
            return Response(self.get_object().get_items())
        except KillBillError:
            return Response(
                {'Detail': 'Cannot retrieve data from invoice backend'}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.list_route()
    def annual_report(self, request):
        group_by = request.query_params.get('group_by', 'customer')
        if group_by not in ('customer', 'month'):
            return Response(
                {'Detail': 'group_by parameter can be only `month` or `customer`'},
                status=status.HTTP_400_BAD_REQUEST)

        truncate_date = connection.ops.date_trunc_sql('month', 'date')
        invoices = Invoice.objects.all()
        invoices_values = (
            invoices
            .extra({'month': truncate_date})
            .values('month', 'customer__name')
            .annotate(Sum('amount'))
        )

        formatted_data = defaultdict(list)
        if group_by == 'customer':
            for invoice in invoices_values:
                month = invoice['month']
                if isinstance(month, basestring):
                    month = datetime.strptime(invoice['month'], '%Y-%m-%d')
                formatted_data[invoice['customer__name']].append((month, invoice['amount__sum']))
            formatted_data.default_factory = None
            global_data = {}
            for customer_name, month_data in formatted_data.items():
                formatted_data[customer_name] = sorted(month_data, key=lambda x: x[0], reverse=True)

                year_data = defaultdict(lambda: 0)
                for month, value in month_data:
                    year_data[month.year] += value
                year_data.default_factory = None
                global_data[customer_name] = sorted(year_data.items(), key=lambda x: x[0], reverse=True)

            global_partial_sums = [sum([el[1] for el in v]) for v in formatted_data.values()]
        else:
            for invoice in invoices_values:
                month = invoice['month']
                if isinstance(month, basestring):
                    month = datetime.strptime(invoice['month'], '%Y-%m-%d')
                formatted_data[month].append((invoice['customer__name'], invoice['amount__sum']))
            formatted_data.default_factory = None

            global_data = defaultdict(lambda: defaultdict(lambda: 0))
            for month, customer_data in formatted_data.items():
                for customer_name, value in customer_data:
                    global_data[month.year][customer_name] += value
            for value in global_data.values():
                value.default_factory = None
            global_data.default_factory = None
            global_data = OrderedDict(sorted(global_data.items(), key=lambda x: x[0], reverse=True))
            global_partial_sums = [sum([el[1] for el in v.items()]) for v in global_data.values()]

        formatted_data = OrderedDict(sorted(formatted_data.items(), key=lambda x: x[0], reverse=True))
        global_data = OrderedDict(sorted(global_data.items(), key=lambda x: x[0], reverse=True))
        partial_sums = [sum([el[1] for el in v]) for v in formatted_data.values()]
        total_sum = sum(partial_sums)

        info = settings.NODECONDUCTOR_KILLBILL.get('INVOICE', {})
        logo = info.get('logo', None)
        if logo and not logo.startswith('/'):
            logo = os.path.join(settings.BASE_DIR, logo)

        context = {
            'formatted_data': formatted_data,
            'global_data': global_data,
            'group_by': group_by,
            'partial_sums': iter(partial_sums),
            'global_partial_sums': iter(global_partial_sums),
            'total_sum': total_sum,
            'currency': settings.NODECONDUCTOR_KILLBILL.get('BACKEND').get('currency', ''),
            'logo': logo,
        }

        result = StringIO.StringIO()
        pisa.pisaDocument(
            StringIO.StringIO(render_to_string('nodeconductor_killbill/annual_report.html', context)),
            result
        )

        response = http.HttpResponse(result.getvalue(), content_type='application/pdf')

        if request.query_params.get('download'):
            download_name = 'cost_report_by_%s.pdf' % group_by
            response['Content-Disposition'] = 'attachment; filename="%s"' % download_name

        return response
