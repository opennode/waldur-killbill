import logging

from nodeconductor.cost_tracking.models import PayableMixin
from nodeconductor.structure import SupportedServices

from .backend import KillBillBackend, KillBillError
from .log import event_logger


logger = logging.getLogger(__name__)
paid_models = PayableMixin.get_all_models()


def update_subscription_fields(model, queryargs=None, fields=None):
    backend = KillBillBackend()
    for resource in model.objects.exclude(billing_backend_id=None).filter(**queryargs):
        try:
            args = {k: reduce(getattr, v.split('__'), resource) for k, v in fields.items()}
            backend.update_subscription_fields(resource.billing_backend_id, **args)
        except KillBillError as e:
            logger.error(
                "Failed to update KillBill fields for resource %s: %s", resource, e)


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
            instance.billing_backend_id, resource_name=instance.full_name)


def update_project_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        for model in paid_models:
            update_subscription_fields(
                model,
                queryargs={'project': instance},
                fields={'project_name': 'project__full_name'})


def update_project_group_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        for model in paid_models:
            update_subscription_fields(
                model,
                queryargs={'project__project_groups': instance},
                fields={'project_name': 'project__full_name'})


def update_service_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        resources = SupportedServices.get_related_models(instance)['resources']
        for model in resources:
            if model in paid_models:
                update_subscription_fields(
                    model,
                    queryargs={'service_project_link__service': instance},
                    fields={'service_name': 'service_project_link__service__full_name'})


def update_service_settings_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        resources = SupportedServices.get_related_models(instance)['resources']
        for model in resources:
            if model in paid_models:
                update_subscription_fields(
                    model,
                    queryargs={'service_project_link__service__settings': instance},
                    fields={'service_name': 'service_project_link__service__full_name'})

        backend = KillBillBackend()
