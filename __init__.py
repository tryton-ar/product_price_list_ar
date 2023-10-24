# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import Pool
from . import price_list
from . import product
from . import invoice
from . import sale


def register():
    Pool.register(
        price_list.PriceList,
        price_list.PriceListLine,
        price_list.Currency,
        product.Product,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.InvoiceUpdateLinePriceStart,
        sale.Sale,
        sale.Line,
        module='product_price_list_ar', type_='model')
    Pool.register(
        invoice.InvoiceUpdateLinePrice,
        module='product_price_list_ar', type_='wizard')
