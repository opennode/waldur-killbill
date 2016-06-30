from django.contrib import admin, messages
from django.conf.urls import patterns, url
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import gettext

from nodeconductor.core.admin import AdminActionsRegister
from nodeconductor.core.tasks import send_task
from nodeconductor.cost_tracking.admin import DefaultPriceListItemAdmin
from nodeconductor.cost_tracking.models import PayableMixin

from .backend import KillBillBackend, KillBillError
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
        for model in PayableMixin.get_all_models():
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


def sync(request):
    send_task('killbill', 'sync_pricelist')()
    messages.add_message(request, messages.INFO, "Price lists scheduled for sync")
    return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


def subscribe_resources(request):
    erred_resources = {}
    subscribed_resources = []
    existing_resources = []
    for model in PayableMixin.get_all_models():
        for resource in model.objects.exclude(state=model.States.ERRED):
            try:
                backend = KillBillBackend(resource.customer)
                is_newly_subscribed = backend.subscribe(resource)
            except KillBillError as e:
                erred_resources[resource] = str(e)
            else:
                resource.last_usage_update_time = None
                resource.save(update_fields=['last_usage_update_time'])
                if is_newly_subscribed:
                    subscribed_resources.append(resource)
                else:
                    existing_resources.append(resource)

    if subscribed_resources:
        message = gettext('Successfully subscribed %s resources: %s')
        message = message % (len(subscribed_resources), ', '.join(r.name for r in subscribed_resources))
        messages.add_message(request, messages.INFO, message)

    if existing_resources:
        message = gettext('%s resources were already subscribed: %s')
        message = message % (len(existing_resources), ', '.join(r.name for r in existing_resources))
        messages.add_message(request, messages.INFO, message)

    if erred_resources:
        message = gettext('Failed to subscribe resources: %(erred_resources)s')
        erred_resources_message = ', '.join(['%s (error: %s)' % (r.name, e) for r, e in erred_resources.items()])
        message = message % {'erred_resources': erred_resources_message}
        messages.add_message(request, messages.ERROR, message)

    return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


AdminActionsRegister.register(DefaultPriceListItemAdmin, sync, 'Sync price lists with backend')
AdminActionsRegister.register(DefaultPriceListItemAdmin, subscribe_resources, 'Subscribe missed resources')
