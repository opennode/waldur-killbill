import logging

from nodeconductor.structure.models import PaidResource

from .backend import KillBillBackend, KillBillError
from .log import event_logger


logger = logging.getLogger(__name__)


def log_invoice_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.killbill_invoice.info(
            '{invoice_date}. Invoice for customer {customer_name} has been created.',
            event_type='invoice_creation_succeeded',
            event_context={
                'invoice': instance,
            })
    else:
        event_logger.killbill_invoice.info(
            '{invoice_date}. Invoice for customer {customer_name} has been updated.',
            event_type='invoice_update_succeeded',
            event_context={
                'invoice': instance,
            })


def log_invoice_delete(sender, instance, **kwargs):
    event_logger.killbill_invoice.info(
        '{invoice_date}. Invoice for customer {customer_name} has been deleted.',
        event_type='invoice_deletion_succeeded',
        event_context={
            'invoice': instance,
        })


def subscribe(sender, instance, name=None, source=None, **kwargs):
    if source == instance.States.PROVISIONING and name == instance.set_online.__name__:
        try:
            backend = KillBillBackend(instance.customer)
            backend.subscribe(instance)
        except KillBillError as e:
            logger.error(
                "Failed to subscribe resource %s to KillBill: %s", instance.to_string(), e)


def unsubscribe(sender, instance=None, **kwargs):
    try:
        backend = KillBillBackend(instance.customer)
        backend.terminate(instance)
    except KillBillError as e:
        logger.error(
            "Failed to unsubscribe resource %s from KillBill: %s", instance.to_string(), e)


def update_resource_name(sender, instance, created=False, **kwargs):
    if not created and instance.billing_backend_id and instance.name != instance._old_values['name']:
        backend = KillBillBackend()
        backend.update_subscription_fields(
            instance.billing_backend_id, resource_name=backend.get_resource_name(instance))


def update_project_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        backend = KillBillBackend()
        for model in PaidResource.get_all_models():
            for resource in model.objects.exclude(billing_backend_id=None).filter(project=instance):
                try:
                    backend.update_subscription_fields(
                        resource.billing_backend_id, project_name=resource.project.full_name)
                except KillBillError as e:
                    logger.error(
                        "Failed to update project name in KillBill for resource %s: %s",
                        resource, instance.to_string(), e)


def update_project_group_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        backend = KillBillBackend()
        for model in PaidResource.get_all_models():
            for resource in model.objects.exclude(billing_backend_id=None).filter(project__project_groups=instance):
                try:
                    backend.update_subscription_fields(
                        resource.billing_backend_id, project_name=resource.project.full_name)
                except KillBillError as e:
                    logger.error(
                        "Failed to update project group name in KillBill for resource %s: %s",
                        resource, instance.to_string(), e)
