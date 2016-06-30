import logging

from celery import shared_task
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from nodeconductor.cost_tracking import CostTrackingRegister
from nodeconductor.cost_tracking.models import DefaultPriceListItem, PayableMixin
from nodeconductor.structure.models import Resource

from .backend import KillBillBackend, KillBillError


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.killbill.sync_pricelist')
def sync_pricelist():
    backend = KillBillBackend()
    try:
        backend.propagate_pricelist()
    except KillBillError as e:
        logger.error("Can't propagate pricelist to %s: %s", backend, e)


@shared_task(name='nodeconductor.killbill.sync_invoices')
def sync_invoices():
    customers = set()
    for model in PayableMixin.get_all_models():
        for resource in model.objects.exclude(billing_backend_id=''):
            customers.add(resource.customer)

    for customer in customers:
        try:
            backend = KillBillBackend(customer)
            backend.sync_invoices()
        except KillBillError as e:
            logger.error("Can't sync invoices for customer with %s: %s", customer, e)


@shared_task(name='nodeconductor.killbill.update_today_usage')
def update_today_usage():
    """
    Calculate usage for all paid resources.

    Task counts exact usage amount for numerical options and boolean value for the rest.
    Example:
        2015-08-20 13:00    storage-1Gb         20
        2015-08-20 13:00    flavor-g1.small1    1
        2015-08-20 13:00    license-os-centos7  1
        2015-08-20 13:00    support-basic       1
    """

    for model in PayableMixin.get_all_models():
        for resource in model.objects.exclude(state=model.States.ERRED):
            update_today_usage_of_resource.delay(resource.to_string())


@shared_task
def update_today_usage_of_resource(resource_str):
    # XXX: this method does ignores cases then VM was offline or online for small periods of time.
    # It could to be rewritten if more accurate calculation will be needed
    with transaction.atomic():
        resource = next(Resource.from_string(resource_str))
        cs_backend = CostTrackingRegister.get_resource_backend(resource)
        used_items = cs_backend.get_used_items(resource)

        if not resource.billing_backend_id:
            logger.warning(
                "Can't update usage for resource %s which is not subscribed to backend", resource_str)
            return

        numerical = cs_backend.NUMERICAL
        content_type = ContentType.objects.get_for_model(resource)

        units = {
            (item.item_type, None if item.item_type in numerical else item.key): item.units
            for item in DefaultPriceListItem.objects.filter(resource_content_type=content_type)}

        now = timezone.now()
        last_update_time = resource.last_usage_update_time or resource.created
        minutes_from_last_usage_update = (now - last_update_time).total_seconds() / 60

        usage = {}
        for item_type, key, val in used_items:
            if val:
                try:
                    unit = units[item_type, None if item_type in numerical else key]
                    usage_per_min = int(round(val * minutes_from_last_usage_update))
                    if usage_per_min:
                        usage[unit] = usage_per_min
                except KeyError:
                    logger.error("Can't find price for usage item %s:%s", key, val)

        try:
            kb_backend = KillBillBackend()
            kb_backend.add_usage_data(resource, usage)
        except KillBillError as e:
            logger.error("Can't add usage for resource %s: %s", resource, e)

        resource.last_usage_update_time = timezone.now()
        resource.save(update_fields=['last_usage_update_time'])
