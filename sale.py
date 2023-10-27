# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    currency_rate = fields.Numeric('Currency rate', digits=(12, 6),
        states={
            'readonly': Eval('state') != 'draft',
            })

    @fields.depends('currency', 'company')
    def on_change_currency(self):
        if self.currency and self.currency.rate != 0:
            self.currency_rate = (
                self.company.currency.rate / self.currency.rate)
        else:
            self.currency_rate = Decimal('1.0')

    def create_invoice(self):
        invoice = super().create_invoice()
        if invoice:
            invoice.currency_rate = self.currency_rate
            invoice.price_list = self.price_list
        return invoice


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['currency_rate'] = Eval(
            '_parent_sale', {}).get('currency_rate')

    @fields.depends('sale', '_parent_sale.price_list',
        '_parent_sale.currency')
    def _get_context_sale_price(self):
        context = super()._get_context_sale_price()
        if self.sale:
            if getattr(self.sale, 'price_list', None):
                context['price_list_currency'] = (
                    self.sale.price_list.currency.id)
            if getattr(self.sale, 'currency', None):
                context['currency_rate'] = self.sale.currency_rate
        return context

    @fields.depends('_parent_sale.price_list', '_parent_sale.currency_rate')
    def on_change_product(self):
        super().on_change_product()

    @fields.depends('_parent_sale.price_list', '_parent_sale.currency_rate')
    def on_change_quantity(self):
        super().on_change_quantity()

    @fields.depends('_parent_sale.price_list', '_parent_sale.currency_rate')
    def on_change_unit(self):
        super().on_change_unit()
