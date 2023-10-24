# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from sql import Table

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class PriceList(metaclass=PoolMeta):
    'Price List'
    __name__ = 'product.price_list'

    currency = fields.Many2One('currency.currency', 'Currency',
        required=True)

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    def product_defined(self, product):
        '''
        If the product is defined in the list
        or in the parent list, then return True
        '''
        cursor = Transaction().connection.cursor()
        lines = Table('product_price_list_line')

        cursor.execute(*lines.select(lines.id,
            where=(lines.product == product.id) &
                (lines.price_list == self.id)))
        if cursor.fetchall():
            return True
        return False

    def compute(self, party, product, unit_price, quantity, uom,
            pattern=None):
        'Compute price based price list currency'
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Currency = pool.get('currency.currency')
        Company = pool.get('company.company')

        context = Transaction().context
        unit_price = super().compute(party, product, unit_price, quantity,
            uom, pattern=None)
        if context.get('price_list') and context.get('currency'):
            price_list = PriceList(context.get('price_list'))
            currency = Currency(context.get('currency'))
            if price_list.currency != currency.id:
                rate = 1
                if context.get('currency_rate'):
                    if int(context.get('currency_rate')) == 1:
                        rate = currency.rate / price_list.currency.rate
                else:
                    company = Company(context.get('company'))
                    if company.currency.id == currency.id:
                        rate = currency.rate / price_list.currency.rate
                    else:
                        rate = company.currency.rate / currency.rate
                unit_price *= rate

        return unit_price


class PriceListLine(metaclass=PoolMeta):
    'Price List Line'
    __name__ = 'product.price_list.line'

    @classmethod
    def compute_currency(cls, from_currency, amount, to_currency,
            currency_rate, round=True):
        pool = Pool()
        Company = pool.get('company.company')

        if to_currency == from_currency:
            if round:
                return to_currency.round(amount)
            else:
                return amount

        company = Company(Transaction().context['company'])
        if from_currency == company.currency:
            from_currency_rate = currency_rate
            currency_rate = Decimal('1.0')
        else:
            from_currency_rate = Decimal('1.0')

        if round:
            return to_currency.round(
                amount * currency_rate / from_currency_rate)
        else:
            return amount * currency_rate / from_currency_rate


class Currency(metaclass=PoolMeta):
    __name__ = 'currency.currency'

    @classmethod
    def compute(cls, from_currency, amount, to_currency, round=True):
        pool = Pool()
        PriceListLine = pool.get('product.price_list.line')

        currency_rate = Transaction().context.get('currency_rate')
        if currency_rate:
            return PriceListLine.compute_currency(from_currency, amount,
                to_currency, currency_rate, round)
        return super().compute(from_currency, amount, to_currency, round)