from nodeconductor.logging.loggers import EventLogger, event_logger

from .models import Invoice


class InvoiceEventLogger(EventLogger):
    invoice = Invoice

    class Meta:
        event_types = ('invoice_deletion_succeeded',
                       'invoice_update_succeeded',
                       'invoice_creation_succeeded')


event_logger.register('killbill_invoice', InvoiceEventLogger)
