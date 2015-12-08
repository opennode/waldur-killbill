from django.contrib import admin, messages
from django.conf.urls import patterns, url
from django.core.urlresolvers import reverse
from django.shortcuts import redirect

from nodeconductor.core.tasks import send_task
from nodeconductor.structure.models import PaidResource

from .backend import KillBillBackend
from .models import Invoice
from .tasks import update_today_usage_of_resource


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'amount',)

    def get_urls(self):
        my_urls = patterns(
            '',
            url(r'^sync/$', self.admin_site.admin_view(self.sync)),
            url(r'^move_date/$', self.admin_site.admin_view(self.move_date)),
        )
        return my_urls + super(InvoiceAdmin, self).get_urls()

    def move_date(self, request):
        for model in PaidResource.get_all_models():
            for resource in model.objects.all():
                try:
                    update_today_usage_of_resource(resource.to_string())
                except Exception as e:
                    self.message_user(
                        request,
                        "Can't post usage for %s: %s" % (resource, e),
                        level=messages.ERROR)

        backend = KillBillBackend()
        backend.api.test.move_days(31)

        send_task('killbill', 'sync_invoices')()

        self.message_user(request, "KillBill invoices generated and scheduled for sync from backend.")

        return redirect(reverse('admin:nodeconductor_killbill_invoice_changelist'))

    def sync(self, request):
        send_task('killbill', 'sync_invoices')()

        self.message_user(request, "KillBill invoices scheduled for sync from backend.")

        return redirect(reverse('admin:nodeconductor_killbill_invoice_changelist'))


admin.site.register(Invoice, InvoiceAdmin)
