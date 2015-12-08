from . import views


def register_in(router):
    router.register(r'killbill-invoices', views.InvoiceViewSet)
